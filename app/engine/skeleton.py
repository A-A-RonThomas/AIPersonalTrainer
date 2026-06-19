"""
PPL slot definitions. Slots are the invariant — they define which muscle groups
must be covered each session. Exercise options are populated at runtime from the
exercise_templates DB table (seeded from Hevy during cold start).
"""

from dataclasses import dataclass, field


@dataclass
class SlotExercise:
    name: str
    exercise_template_id: str = ""


@dataclass
class Slot:
    key: str
    label: str
    anchor: bool = False  # anchor slots prefer the same exercise week-to-week
    options: list[SlotExercise] = field(default_factory=list)


PUSH_SLOTS: list[Slot] = [
    Slot(key="chest_compound",    label="Chest Compound",    anchor=True),
    Slot(key="shoulder_compound", label="Shoulder Compound", anchor=True),
    Slot(key="chest_isolation",   label="Chest Isolation"),
    Slot(key="tricep_isolation",  label="Tricep Isolation"),
    Slot(key="shoulder_isolation",label="Shoulder Isolation"),
]

PULL_SLOTS: list[Slot] = [
    Slot(key="vertical_pull",   label="Vertical Pull",   anchor=True),
    Slot(key="horizontal_pull", label="Horizontal Pull", anchor=True),
    Slot(key="rear_delt",       label="Rear Delt"),
    Slot(key="bicep",           label="Bicep"),
]

LEGS_SLOTS: list[Slot] = [
    Slot(key="quad_compound", label="Quad Compound", anchor=True),
    Slot(key="hip_hinge",     label="Hip Hinge / Hamstring", anchor=True),
    Slot(key="glute",         label="Glute"),
    Slot(key="calf",          label="Calf"),
    Slot(key="core",          label="Core"),
]

DAY_TYPE_SLOTS: dict[str, list[Slot]] = {
    "push": PUSH_SLOTS,
    "pull": PULL_SLOTS,
    "legs": LEGS_SLOTS,
}

ANCHOR_SLOTS: set[str] = {s.key for slots in DAY_TYPE_SLOTS.values() for s in slots if s.anchor}


def slots_for_day(day_type: str) -> list[Slot]:
    return DAY_TYPE_SLOTS.get(day_type, [])
