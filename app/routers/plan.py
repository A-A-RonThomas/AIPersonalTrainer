import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.claude_layer.trainer import explain_plan, select_exercises
from app.templating import templates
from app.config import settings
from app.database import get_db
from app.engine.evaluation import build_eval_map
from app.engine.split import labeled_split
from app.hevy.adapter import HevyClient
from app.models import ExerciseHistory, ExerciseTemplate, ProgramState, WeeklyPlan

router = APIRouter()


def _get_state(db: Session) -> ProgramState:
    state = db.query(ProgramState).first()
    if not state:
        raise HTTPException(status_code=400, detail="Program not initialized. Run /init first.")
    return state


def _next_monday() -> date:
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


def _build_plan_shell(state: ProgramState, week_number: int, start_date: date) -> dict:
    """Build a plan with days/types but no exercises — Claude fills those in."""
    split = labeled_split(state.training_days_per_week)
    return {
        "week_number": week_number,
        "start_date": start_date.isoformat(),
        "goal": state.goal,
        "days": [
            {"day_of_week": d["day_of_week"], "type": d["type"], "exercises": []}
            for d in split
        ],
    }


def _default_sets_for_goal(goal: str, slot: str) -> list[dict]:
    """Default set/rep scheme by goal. Leaner volume on a cut."""
    is_compound = slot.endswith("_compound") or slot in ("hip_hinge", "vertical_pull", "horizontal_pull")

    if goal == "preserve":
        sets = 3 if is_compound else 2
        reps = 8
    else:  # build
        sets = 4 if is_compound else 3
        reps = 10

    return [{"set_number": i + 1, "reps": reps, "load_lbs": 0, "rpe_target": 8} for i in range(sets)]


def _fill_sets(plan: dict, id_map: dict, slot_map: dict) -> dict:
    """Apply progression decisions to set prescriptions."""
    for day in plan["days"]:
        if day["type"] == "rest":
            continue
        exercises = []
        for ex in day["exercises"]:
            tid = ex.get("exercise_template_id", "")
            slot = ex.get("slot", "")

            decision = id_map.get(tid) or slot_map.get(slot)
            if decision and decision.new_load_lbs > 0:
                sets = _default_sets_for_goal(plan["goal"], slot)
                for s in sets:
                    s["load_lbs"] = decision.new_load_lbs
                ex["sets"] = sets
                ex["_progression"] = {"action": decision.action, "reason": decision.reason}
            else:
                ex["sets"] = _default_sets_for_goal(plan["goal"], slot)

            exercises.append(ex)
        day["exercises"] = exercises
    return plan


def _previous_exercises(db: Session) -> dict[str, str]:
    """Get last week's exercise choices per slot."""
    last_plan = db.query(WeeklyPlan).filter(
        WeeklyPlan.status == "approved"
    ).order_by(desc(WeeklyPlan.week_number)).first()

    if not last_plan:
        return {}

    result = {}
    for day in last_plan.plan_json.get("days", []):
        for ex in day.get("exercises", []):
            result[ex["slot"]] = ex["name"]
    return result


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    latest_plan = db.query(WeeklyPlan).order_by(desc(WeeklyPlan.week_number)).first()
    state = db.query(ProgramState).first()
    return templates.TemplateResponse(request, "index.html", {
        "plan": latest_plan,
        "state": state,
    })


@router.post("/generate", response_class=HTMLResponse)
async def generate_plan(request: Request, db: Session = Depends(get_db)):
    state = _get_state(db)
    form = await request.form()
    notes = form.get("notes", "")

    week_number = state.current_week
    start_date = _next_monday()

    # Get rolling history for eval
    history = db.query(ExerciseHistory).filter(
        ExerciseHistory.week_number >= week_number - 4
    ).all()
    id_map, slot_map = build_eval_map(history, state.goal)

    # Build slot_exercises from DB templates
    db_templates = db.query(ExerciseTemplate).all()
    slot_exercises: dict[str, list[dict]] = {}
    for t in db_templates:
        slot_exercises.setdefault(t.slot, []).append({"name": t.name, "template_id": t.template_id})

    # Build plan: shell → Claude selects exercises → fill sets
    shell = _build_plan_shell(state, week_number, start_date)
    prev_exercises = _previous_exercises(db)

    plan_with_exercises = select_exercises(shell, slot_exercises, prev_exercises, notes)
    plan = _fill_sets(plan_with_exercises, id_map, slot_map)

    trainer_notes = explain_plan(plan, {k: v.__dict__ for k, v in id_map.items()}, notes)

    weekly_plan = WeeklyPlan(
        week_number=week_number,
        start_date=start_date,
        goal=state.goal,
        status="draft",
        plan_json=plan,
        trainer_notes=trainer_notes,
    )
    db.add(weekly_plan)
    db.commit()
    db.refresh(weekly_plan)

    return templates.TemplateResponse(request, "week.html", {
        "plan": weekly_plan,
        "messages": [],
    })


@router.get("/plan/{plan_id}", response_class=HTMLResponse)
async def view_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404)

    prev_plan = db.query(WeeklyPlan).filter(
        WeeklyPlan.week_number == plan.week_number - 1,
        WeeklyPlan.status == "approved",
    ).first()

    return templates.TemplateResponse(request, "week.html", {
        "plan": plan,
        "prev_plan": prev_plan,
        "messages": plan.chat_messages,
    })


@router.post("/plan/{plan_id}/approve")
async def approve_plan(plan_id: int, request: Request, db: Session = Depends(get_db)):
    from datetime import datetime
    from fastapi.responses import RedirectResponse

    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404)
    if plan.status == "approved":
        raise HTTPException(status_code=400, detail="Already approved")

    from sqlalchemy.orm.attributes import flag_modified

    hevy = HevyClient(settings.hevy_api_key)
    existing_ids = plan.plan_json.get("hevy_routine_ids", {})
    results = hevy.push_plan(plan.plan_json, routine_ids=existing_ids)

    plan.status = "approved"
    plan.approved_at = datetime.utcnow()

    # Store routine IDs keyed by day_of_week for future updates
    routine_ids = {
        r["day"]: r["result"]["routine"][0]["id"]
        for r in results
        if r["result"].get("routine")
    }
    updated = dict(plan.plan_json)
    updated["hevy_routine_ids"] = routine_ids
    plan.plan_json = updated
    flag_modified(plan, "plan_json")

    # Delete previous week's Hevy routines if they exist
    prev_plan = db.query(WeeklyPlan).filter(
        WeeklyPlan.week_number == plan.week_number - 1,
        WeeklyPlan.status == "approved",
    ).first()
    if prev_plan and prev_plan.plan_json:
        for rid in prev_plan.plan_json.get("hevy_routine_ids", {}).values():
            if rid:
                try:
                    hevy.delete_routine(rid)
                except ValueError:
                    pass  # already deleted or not found — don't block approval

    state = _get_state(db)
    state.current_week += 1
    if state.is_cold_start and state.current_week > 2:
        state.is_cold_start = False

    db.commit()

    return RedirectResponse(url=f"/plan/{plan_id}", status_code=303)
