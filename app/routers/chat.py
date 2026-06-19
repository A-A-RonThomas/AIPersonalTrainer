from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.claude_layer.trainer import chat_edit
from app.database import get_db
from app.models import ChatMessage, ExerciseTemplate, WeeklyPlan
from app.templating import templates

router = APIRouter()


def _resolve_template_ids(plan: dict, name_to_id: dict[str, str]) -> dict:
    """After a chat edit, re-resolve exercise_template_id from name in case Claude swapped an exercise."""
    for day in plan.get("days", []):
        for ex in day.get("exercises", []):
            name = ex.get("name", "")
            if name in name_to_id:
                ex["exercise_template_id"] = name_to_id[name]
    return plan


@router.post("/plan/{plan_id}/chat", response_class=HTMLResponse)
async def chat(plan_id: int, request: Request, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404)
    if plan.status == "approved":
        raise HTTPException(status_code=400, detail="Plan is already approved — cannot edit.")

    form = await request.form()
    user_message = form.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty message")

    # Build name→template_id lookup and slot_exercises for Claude
    db_templates = db.query(ExerciseTemplate).all()
    name_to_id = {t.name: t.template_id for t in db_templates}
    slot_exercises: dict[str, list[dict]] = {}
    for t in db_templates:
        slot_exercises.setdefault(t.slot, []).append({"name": t.name, "template_id": t.template_id})

    prior = [{"role": m.role, "content": m.content} for m in plan.chat_messages]
    updated_plan, assistant_reply = chat_edit(plan.plan_json, prior, user_message, slot_exercises)

    # Ensure exercise_template_id is correct after any swap
    updated_plan = _resolve_template_ids(updated_plan, name_to_id)

    db.add(ChatMessage(plan_id=plan_id, role="user", content=user_message))
    db.add(ChatMessage(plan_id=plan_id, role="assistant", content=assistant_reply))

    plan.plan_json = updated_plan
    flag_modified(plan, "plan_json")

    db.commit()
    db.refresh(plan)

    return templates.TemplateResponse(request, "week.html", {
        "plan": plan,
        "messages": plan.chat_messages,
    })
