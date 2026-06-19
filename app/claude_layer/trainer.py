"""
Claude layer — qualitative decisions only.
- Exercise selection & rotation within slots
- Reading freeform notes
- Trainer-voice explanation of changes
- Chat-based plan edits
"""

import json

import anthropic

from app.config import settings
from app.engine.skeleton import ANCHOR_SLOTS

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an experienced strength coach programming workouts for a single user.
Your job is the qualitative layer: exercise selection, rotation, reading notes, and explaining changes.
All load progression math has already been computed deterministically — do not change loads unless explicitly asked.

Rules:
- Keep the PPL slot structure. Never drop a slot.
- Anchor compounds (marked anchor=true) stay fixed unless a pain note says otherwise.
- For non-anchor slots, pick a different exercise than last week when possible (variety without randomness).
- A pain note ("shoulder twinged", "knee ache") → swap that exercise for something joint-friendly, flag it clearly.
- A boredom note ("bored of X") → rotate to any other option in the slot.
- Respond in JSON only when asked for a plan object. Use plain text for trainer explanations.
- Keep explanations concise and direct — trainer voice, not coach-speak.
"""


def select_exercises(
    plan_shell: dict,
    slot_exercises: dict[str, list[dict]],  # {slot_key: [{name, template_id}]}
    previous_exercises: dict[str, str],  # {slot_key: exercise_name used last week}
    notes: str = "",
) -> dict:
    """
    Given a plan shell and available exercises per slot (from DB),
    ask Claude to fill in the exercise selection with real template IDs.
    """
    # Build per-day slot guide using only slots relevant to that day type
    from app.engine.skeleton import DAY_TYPE_SLOTS
    day_slot_guide: dict[str, dict] = {}
    for day_type, slots in DAY_TYPE_SLOTS.items():
        guide = {}
        for slot in slots:
            options = slot_exercises.get(slot.key, [])
            anchor = " (anchor — keep fixed unless pain note)" if slot.key in ANCHOR_SLOTS else ""
            guide[slot.key + anchor] = [
                {"name": o["name"], "template_id": o["template_id"]}
                for o in options
            ]
        day_slot_guide[day_type] = guide

    prompt = f"""Fill in exercise selection for this week's plan.

Plan days:
{json.dumps([{"day_of_week": d["day_of_week"], "type": d["type"]} for d in plan_shell["days"]], indent=2)}

Available exercises per slot (use ONLY these — pick the exact name and template_id):
{json.dumps(day_slot_guide, indent=2)}

Last week's exercise choices (rotate away from these for non-anchor slots):
{json.dumps(previous_exercises, indent=2)}

User notes for this week:
{notes or "None"}

Return the complete plan JSON with exercises filled in. Each exercise must use this structure:
{{"slot": "slot_key", "exercise_template_id": "<real template_id from above>", "name": "<exact name from above>", "sets": []}}

If a slot has no available exercises, omit it.
The sets arrays will be filled in by the progression engine — leave them empty.
Respond with ONLY the updated plan JSON, no other text."""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    result = json.loads(raw.strip())

    if isinstance(result, list):
        days = result
    else:
        days = result.get("days", result)

    # Always preserve top-level metadata from the shell
    plan_shell["days"] = days
    return plan_shell


def explain_plan(plan: dict, eval_map: dict, notes: str = "") -> str:
    """Generate a plain-text trainer explanation of the week's changes."""
    changes = []
    for day in plan.get("days", []):
        for ex in day.get("exercises", []):
            p = ex.get("_progression")
            if p and p["action"] != "hold":
                changes.append(f"- {ex['name']} ({ex['slot']}): {p['reason']}")

    prompt = f"""Goal this week: {plan['goal']}
Week: {plan['week_number']}
Notes from user: {notes or 'None'}

Progression changes made:
{chr(10).join(changes) if changes else 'No load changes — holding everything.'}

Write a short (3-5 sentence) trainer-voice summary of this week's plan.
Explain the key changes and why. Be direct, not motivational-poster style."""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def chat_edit(
    plan: dict,
    conversation: list[dict],
    user_message: str,
    slot_exercises: dict[str, list[dict]] | None = None,
) -> tuple[dict, str]:
    """
    Process a chat-based plan edit. Returns (updated_plan, assistant_reply).
    assistant_reply is always plain text suitable for the chat log.
    """
    exercises_section = ""
    if slot_exercises:
        exercises_section = f"""
Available exercises by slot (use ONLY these name/template_id pairs when swapping):
{json.dumps(slot_exercises, indent=2)}
"""

    messages = list(conversation) + [
        {
            "role": "user",
            "content": f"""{user_message}

Current plan JSON:
{json.dumps(plan, indent=2, default=str)}
{exercises_section}
If you're making a change to the plan, respond in exactly this format:
EXPLANATION: <one sentence describing what changed>
```json
<complete updated plan JSON>
```

When swapping an exercise, update BOTH the name AND exercise_template_id fields using the exact values from the available exercises list above.
If no plan change is needed, reply with plain text only.""",
        }
    ]

    msg = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    reply = msg.content[0].text.strip()

    # Extract JSON from code fence if present
    if "```" in reply:
        try:
            fence_content = reply.split("```")[1]
            if fence_content.startswith("json"):
                fence_content = fence_content[4:]
            updated_plan = json.loads(fence_content.strip())

            # Always preserve top-level metadata
            if "days" not in updated_plan:
                updated_plan = plan  # bad parse, ignore
            else:
                updated_plan.setdefault("week_number", plan["week_number"])
                updated_plan.setdefault("start_date", plan["start_date"])
                updated_plan.setdefault("goal", plan["goal"])

            # Extract explanation from before the code fence
            explanation = reply.split("```")[0].replace("EXPLANATION:", "").strip()
            return updated_plan, explanation or "Plan updated."
        except (json.JSONDecodeError, IndexError):
            pass

    return plan, reply
