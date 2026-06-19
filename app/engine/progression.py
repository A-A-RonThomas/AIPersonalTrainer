"""
Deterministic load progression. All loads stored and processed in lbs.
Converted to/from kg only at the Hevy API boundary.

Decision per exercise per week:
  progress     – all sets hit all reps → +5 or +10 lbs
  hold         – hit reps but last set failed
  deload       – missed reps on multiple sets
  stall_deload – load flat for STALL_WEEKS → forced deload
"""

from dataclasses import dataclass

UPPER_BODY_INCREMENT_LBS = 5
LOWER_BODY_INCREMENT_LBS = 10
DELOAD_FACTOR = 0.85
STALL_WEEKS = 3
MAX_SINGLE_JUMP_LBS = 20  # hard cap — safety net against bad note-parses

LOWER_BODY_SLOTS = {"quad_compound", "hip_hinge", "glute", "calf"}


def round5(lbs: float) -> int:
    """Round to nearest 5 lb increment."""
    return round(lbs / 5) * 5


@dataclass
class SetResult:
    reps_prescribed: int
    reps_completed: int
    load_lbs: float
    completed: bool


@dataclass
class ProgressionDecision:
    action: str  # "progress" | "hold" | "deload" | "stall_deload"
    new_load_lbs: int
    reason: str


def _is_lower(slot: str) -> bool:
    return slot in LOWER_BODY_SLOTS


def _increment(slot: str) -> int:
    return LOWER_BODY_INCREMENT_LBS if _is_lower(slot) else UPPER_BODY_INCREMENT_LBS


def evaluate_sets(sets: list[SetResult], slot: str, load_lbs: float, stall_weeks: int = 0) -> ProgressionDecision:
    if not sets:
        return ProgressionDecision("hold", round5(load_lbs), "no sets recorded")

    total = len(sets)
    failed = sum(1 for s in sets if s.reps_completed < s.reps_prescribed)

    if stall_weeks >= STALL_WEEKS:
        deload = round5(load_lbs * DELOAD_FACTOR)
        return ProgressionDecision("stall_deload", deload, f"load flat {stall_weeks} weeks — deloading to {deload} lbs")

    if failed == 0:
        inc = _increment(slot)
        new_load = round5(min(load_lbs + inc, load_lbs + MAX_SINGLE_JUMP_LBS))
        return ProgressionDecision("progress", new_load, f"all reps hit → +{inc} lbs")

    if failed == 1 and total >= 3:
        return ProgressionDecision("hold", round5(load_lbs), "last set incomplete — holding load")

    deload = round5(load_lbs * DELOAD_FACTOR)
    return ProgressionDecision("deload", deload, f"{failed}/{total} sets failed → deload to {deload} lbs")
