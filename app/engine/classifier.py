"""
Classifies a Hevy exercise template into a PPL slot using muscle group tags.
Hevy's exact muscle group strings are unknown, so matching is broad/case-insensitive.
"""


def _contains(text: str, *keywords: str) -> bool:
    t = text.lower()
    return any(k in t for k in keywords)


def classify_template(template: dict) -> str | None:
    name = (template.get("title") or "").lower()
    primary = (template.get("primary_muscle_group") or "").lower()
    secondary = [s.lower() for s in (template.get("secondary_muscle_groups") or [])]
    secondary_str = " ".join(secondary)

    # Core / abs — check early so "core" doesn't bleed into other rules
    if _contains(primary, "core", "abs", "abdominal", "oblique") or _contains(
        name, "plank", "pallof", "dead bug", "bird dog", "ab wheel", "crunch", "sit-up", "situp"
    ):
        return "core"

    if _contains(primary, "calf", "calve", "gastrocnemius", "soleus"):
        return "calf"

    if _contains(primary, "glute", "gluteus"):
        return "glute"

    if _contains(primary, "hamstring"):
        return "hip_hinge"

    if _contains(primary, "quad", "quadricep"):
        return "quad_compound"

    if _contains(primary, "bicep", "brachialis", "brachioradialis"):
        return "bicep"

    if _contains(primary, "tricep"):
        return "tricep_isolation"

    # Rear delt — must come before generic shoulder
    if _contains(primary, "rear delt", "rear_delt", "rear deltoid") or _contains(
        name, "face pull", "rear delt", "reverse fly", "reverse flye", "band pull apart"
    ):
        return "rear_delt"

    # Shoulder
    if _contains(primary, "shoulder", "deltoid", "delt", "front delt", "front_delt"):
        if _contains(name, "raise", "lateral", "front raise"):
            return "shoulder_isolation"
        if _contains(secondary_str, "tricep"):
            return "shoulder_compound"
        return "shoulder_isolation"

    # Chest
    if _contains(primary, "chest", "pectoral"):
        if _contains(name, "fly", "flye", "pec deck", "crossover"):
            return "chest_isolation"
        if _contains(secondary_str, "tricep") or _contains(name, "press"):
            return "chest_compound"
        return "chest_isolation"

    # Back / lats
    if _contains(primary, "lat", "latissimus"):
        if _contains(name, "pulldown", "pull-up", "pull up", "chin up", "chin-up", "chinup", "pull-down"):
            return "vertical_pull"
        if _contains(name, "row", "rowing"):
            return "horizontal_pull"
        return "vertical_pull"

    if _contains(primary, "upper back", "upper_back", "rhomboid", "trap", "mid back", "mid_back"):
        if _contains(name, "face pull", "rear delt", "reverse fly", "reverse flye", "band pull"):
            return "rear_delt"
        return "horizontal_pull"

    if _contains(primary, "back") and not _contains(primary, "lower back", "lower_back"):
        if _contains(name, "row", "rowing"):
            return "horizontal_pull"
        if _contains(name, "pulldown", "pull-up", "pull up", "chin"):
            return "vertical_pull"
        if _contains(name, "face pull", "rear delt"):
            return "rear_delt"
        return "horizontal_pull"

    # Leg catch-alls
    if _contains(primary, "leg", "hip", "adductor", "abductor"):
        if _contains(name, "curl", "deadlift", "rdl", "hinge"):
            return "hip_hinge"
        if _contains(name, "press", "squat", "lunge", "step", "extension"):
            return "quad_compound"
        if _contains(name, "hip thrust", "kickback"):
            return "glute"
        if _contains(name, "calf", "raise"):
            return "calf"

    return None
