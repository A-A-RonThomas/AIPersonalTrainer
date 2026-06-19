"""
Setup routes: initialize program state and cold-start from Hevy history.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.engine.classifier import classify_template
from app.hevy.adapter import HevyClient
from app.models import ExerciseHistory, ExerciseTemplate, ProgramState
from app.templating import templates

router = APIRouter()


@router.get("/setup", response_class=HTMLResponse)
async def setup_form(
    request: Request,
    db: Session = Depends(get_db),
    seeded: int | None = None,
    classified: int | None = None,
    unclassified: int | None = None,
):
    state = db.query(ProgramState).first()
    return templates.TemplateResponse(request, "setup.html", {
        "state": state,
        "seeded": seeded,
        "classified": classified,
        "unclassified": unclassified,
    })


@router.post("/setup")
async def setup_save(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    goal = form.get("goal", "preserve")
    training_days = int(form.get("training_days", 4))

    state = db.query(ProgramState).first()
    if state:
        state.goal = goal
        state.training_days_per_week = training_days
    else:
        state = ProgramState(goal=goal, training_days_per_week=training_days, current_week=1, is_cold_start=True)
        db.add(state)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/debug/routines")
async def debug_routines():
    """Fetch existing Hevy routines to inspect the expected payload structure."""
    hevy = HevyClient(settings.hevy_api_key)
    routines = hevy.get_routines()
    return routines


@router.post("/cold-start")
async def cold_start(request: Request, db: Session = Depends(get_db)):
    hevy = HevyClient(settings.hevy_api_key)

    # Step 1: Pull all exercise templates and classify them into slots
    all_templates = hevy.get_all_exercise_templates()
    classified = 0
    unclassified = 0

    for tmpl in all_templates:
        slot = classify_template(tmpl)
        if not slot:
            unclassified += 1
            continue

        existing = db.query(ExerciseTemplate).filter(
            ExerciseTemplate.template_id == tmpl.get("id", "")
        ).first()

        data = dict(
            name=tmpl.get("title", ""),
            slot=slot,
            primary_muscle=tmpl.get("primary_muscle_group"),
            secondary_muscles=tmpl.get("secondary_muscle_groups") or [],
            category=tmpl.get("category"),
        )

        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            db.add(ExerciseTemplate(template_id=tmpl.get("id", ""), **data))
            classified += 1

    db.flush()

    # Build template_id → slot lookup from what we just classified
    template_slot_map: dict[str, str] = {
        row.template_id: row.slot
        for row in db.query(ExerciseTemplate).all()
    }

    # Step 2: Pull all workout history and seed ExerciseHistory using the map
    workouts = hevy.get_all_workouts()
    seeded = 0

    for workout in workouts:
        workout_date_str = workout.get("start_time", "")[:10]
        for ex in workout.get("exercises", []):
            template_id = ex.get("exercise_template_id", "")
            slot = template_slot_map.get(template_id)
            if not slot:
                continue

            sets_data = [
                {
                    "reps": s.get("reps") or 0,
                    "load_lbs": round(((s.get("weight_kg") or 0) * 2.2046) / 5) * 5,
                    "completed": True,
                }
                for s in ex.get("sets", [])
                if s.get("type") == "normal"
            ]

            existing = db.query(ExerciseHistory).filter(
                ExerciseHistory.exercise_template_id == template_id,
                ExerciseHistory.hevy_workout_id == workout.get("id"),
            ).first()

            if not existing:
                db.add(ExerciseHistory(
                    exercise_template_id=template_id,
                    exercise_name=ex.get("title", ""),
                    slot=slot,
                    workout_date=workout_date_str,
                    week_number=0,
                    sets_data=sets_data,
                    hevy_workout_id=workout.get("id"),
                ))
                seeded += 1

    db.commit()
    return RedirectResponse(
        url=f"/setup?seeded={seeded}&classified={classified}&unclassified={unclassified}",
        status_code=303,
    )
