"""
Per-exercise weekly evaluation. All loads in lbs.

Evaluation forks on goal:
  build    – flat load for STALL_WEEKS = stall → needs intervention
  preserve – flat load for STALL_WEEKS = win (strength held during cut)
             only triggers deload if reps are actually being missed
"""

from app.engine.progression import (
    STALL_WEEKS,
    ProgressionDecision,
    SetResult,
    evaluate_sets,
    round5,
)
from app.models import ExerciseHistory


def _compute_stall_weeks(history: list[ExerciseHistory]) -> int:
    if len(history) < 2:
        return 0
    sorted_h = sorted(history, key=lambda h: h.week_number, reverse=True)
    reference_load = _max_load(sorted_h[0])
    stall = 0
    for h in sorted_h[1:]:
        if _max_load(h) == reference_load:
            stall += 1
        else:
            break
    return stall


def _max_load(h: ExerciseHistory) -> float:
    if not h.sets_data:
        return 0.0
    return max((s.get("load_lbs") or 0) for s in h.sets_data)


def evaluate_exercise(
    exercise_template_id: str,
    slot: str,
    history: list[ExerciseHistory],
    goal: str,
) -> ProgressionDecision:
    if not history:
        return ProgressionDecision("hold", 0, "no history — cold start, hold load")

    sorted_h = sorted(history, key=lambda h: h.week_number, reverse=True)
    last_week = sorted_h[0]

    sets = [
        SetResult(
            reps_prescribed=s.get("reps") or 0,
            reps_completed=(s.get("reps") or 0) if s.get("completed") else 0,
            load_lbs=s.get("load_lbs") or 0,
            completed=s.get("completed", False),
        )
        for s in last_week.sets_data
    ]

    stall_weeks = _compute_stall_weeks(sorted_h)
    current_load = _max_load(last_week)

    if goal == "preserve":
        failed = sum(1 for s in sets if not s.completed or s.reps_completed < s.reps_prescribed)
        if stall_weeks >= STALL_WEEKS and failed == 0:
            return ProgressionDecision(
                "hold",
                round5(current_load),
                f"load flat {stall_weeks} weeks — strength preserved during cut",
            )
        return evaluate_sets(sets, slot, current_load, stall_weeks if failed > 0 else 0)

    return evaluate_sets(sets, slot, current_load, stall_weeks)


def build_eval_map(
    history_rows: list[ExerciseHistory],
    goal: str,
) -> tuple[dict[str, ProgressionDecision], dict[str, ProgressionDecision]]:
    from collections import defaultdict

    by_id: dict[str, list[ExerciseHistory]] = defaultdict(list)
    by_slot: dict[str, list[ExerciseHistory]] = defaultdict(list)
    id_to_slot: dict[str, str] = {}

    for row in history_rows:
        by_id[row.exercise_template_id].append(row)
        by_slot[row.slot].append(row)
        id_to_slot[row.exercise_template_id] = row.slot

    id_map = {
        eid: evaluate_exercise(eid, id_to_slot[eid], rows, goal)
        for eid, rows in by_id.items()
    }
    slot_map = {
        slot: evaluate_exercise("", slot, rows, goal)
        for slot, rows in by_slot.items()
    }
    return id_map, slot_map
