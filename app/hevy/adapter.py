"""
Thin adapter over the Hevy API v1. All Hevy I/O goes through here.
If Hevy changes or gets replaced, swap this file only.
"""

from datetime import date, timedelta

import httpx

HEVY_BASE = "https://api.hevyapp.com/v1"


class HevyClient:
    def __init__(self, api_key: str):
        self._headers = {"api-key": api_key, "Content-Type": "application/json"}

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = httpx.get(f"{HEVY_BASE}{path}", headers=self._headers, params=params, timeout=30)
        if not r.is_success:
            raise ValueError(f"Hevy {r.status_code} on GET {path}: {r.text}")
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = httpx.post(f"{HEVY_BASE}{path}", headers=self._headers, json=body, timeout=30)
        if not r.is_success:
            raise ValueError(f"Hevy {r.status_code} on POST {path}: {r.text}")
        return r.json()

    def _put(self, path: str, body: dict) -> dict:
        r = httpx.put(f"{HEVY_BASE}{path}", headers=self._headers, json=body, timeout=30)
        if not r.is_success:
            raise ValueError(f"Hevy {r.status_code} on PUT {path}: {r.text}")
        return r.json()

    # ------------------------------------------------------------------ #
    # Workouts                                                             #
    # ------------------------------------------------------------------ #

    def get_workouts(self, page: int = 1, page_size: int = 10) -> dict:
        return self._get("/workouts", {"page": page, "pageSize": page_size})

    def get_all_workouts(self) -> list[dict]:
        """Fetch all workouts, paginating until done."""
        workouts = []
        page = 1
        while True:
            data = self.get_workouts(page=page, page_size=10)
            batch = data.get("workouts", [])
            workouts.extend(batch)
            if len(batch) < 10:
                break
            page += 1
        return workouts

    def get_exercise_history(self, exercise_template_id: str, page: int = 1) -> dict:
        return self._get(f"/exercise_history/{exercise_template_id}", {"page": page, "pageSize": 10})

    # ------------------------------------------------------------------ #
    # Exercise templates                                                   #
    # ------------------------------------------------------------------ #

    def get_exercise_templates(self, page: int = 1) -> dict:
        return self._get("/exercise_templates", {"page": page, "pageSize": 100})

    def get_all_exercise_templates(self) -> list[dict]:
        templates = []
        page = 1
        while True:
            data = self.get_exercise_templates(page=page)
            batch = data.get("exercise_templates", [])
            templates.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return templates

    # ------------------------------------------------------------------ #
    # Routines                                                             #
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Body measurements                                                    #
    # ------------------------------------------------------------------ #

    def get_body_measurements(self, page: int = 1, page_size: int = 10) -> dict:
        return self._get("/body_measurements", {"page": page, "pageSize": page_size})

    def get_all_body_measurements(self) -> list[dict]:
        """Fetch all body measurements, paginating until done."""
        entries = []
        page = 1
        while True:
            data = self.get_body_measurements(page=page, page_size=10)
            batch = data.get("body_measurements", [])
            entries.extend(batch)
            if len(batch) < 10:
                break
            page += 1
        return entries

    # ------------------------------------------------------------------ #
    # Routines                                                             #
    # ------------------------------------------------------------------ #

    def get_routines(self) -> list[dict]:
        return self._get("/routines").get("routines", [])

    def create_routine(self, routine: dict) -> dict:
        return self._post("/routines", {"routine": routine})

    def update_routine(self, routine_id: str, routine: dict) -> dict:
        return self._put(f"/routines/{routine_id}", {"routine": routine})

    def delete_routine(self, routine_id: str) -> None:
        r = httpx.delete(f"{HEVY_BASE}/routines/{routine_id}", headers=self._headers, timeout=30)
        if not r.is_success:
            raise ValueError(f"Hevy {r.status_code} on DELETE /routines/{routine_id}: {r.text}")

    # ------------------------------------------------------------------ #
    # Plan → Hevy routine conversion                                       #
    # ------------------------------------------------------------------ #

    _DOW_OFFSET = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                   "friday": 4, "saturday": 5, "sunday": 6}

    def _day_to_routine(self, day: dict, plan: dict) -> dict:
        """Convert a single training day to a Hevy routine payload."""
        start = date.fromisoformat(plan["start_date"])
        offset = self._DOW_OFFSET.get(day["day_of_week"].lower(), 0)
        day_date = start + timedelta(days=offset)
        date_str = f"{day_date.strftime('%b')} {day_date.day}"  # e.g. "Jun 16"

        day_type = day["type"].capitalize()
        title = f"W{plan['week_number']} {day_type} — {date_str}"

        exercises = [
            {
                "exercise_template_id": ex["exercise_template_id"],
                "superset_id": None,
                "notes": None,
                "sets": [
                    {
                        "type": "normal",
                        "weight_kg": s["load_lbs"] / 2.2046,
                        "reps": s["reps"],
                        "distance_meters": None,
                        "duration_seconds": None,
                        "custom_metric": None,
                    }
                    for s in ex["sets"]
                ],
            }
            for ex in day["exercises"]
        ]
        return {"title": title, "folder_id": None, "exercises": exercises}

    def push_plan(self, plan: dict, routine_ids: dict | None = None) -> list[dict]:
        """Push each training day as a separate Hevy routine. Returns list of API results."""
        routine_ids = routine_ids or {}
        results = []
        for day in plan["days"]:
            if day["type"] == "rest":
                continue
            routine = self._day_to_routine(day, plan)
            day_key = day["day_of_week"]
            existing_id = routine_ids.get(day_key)
            if existing_id:
                result = self.update_routine(existing_id, routine)
            else:
                result = self.create_routine(routine)
            results.append({"day": day_key, "result": result})
        return results
