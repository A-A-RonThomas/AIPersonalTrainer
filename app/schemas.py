from datetime import date, datetime
from pydantic import BaseModel


class PlannedSet(BaseModel):
    set_number: int
    reps: int
    load_kg: float
    rpe_target: int


class PlannedExercise(BaseModel):
    slot: str
    exercise_template_id: str
    name: str
    sets: list[PlannedSet]


class TrainingDay(BaseModel):
    day_of_week: str  # "monday" ... "sunday"
    type: str  # "push" | "pull" | "legs" | "rest"
    exercises: list[PlannedExercise] = []


class WeekPlan(BaseModel):
    week_number: int
    start_date: date
    goal: str
    days: list[TrainingDay]


class PlanOut(BaseModel):
    id: int
    week_number: int
    start_date: date
    goal: str
    status: str
    plan_json: WeekPlan
    trainer_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SetHistory(BaseModel):
    reps: int
    load_kg: float
    completed: bool


class ExerciseHistoryOut(BaseModel):
    exercise_template_id: str
    exercise_name: str
    slot: str
    workout_date: date
    week_number: int
    sets_data: list[SetHistory]
    notes: str | None

    model_config = {"from_attributes": True}
