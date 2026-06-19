from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProgramState(Base):
    __tablename__ = "program_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal: Mapped[str] = mapped_column(String(20))  # "preserve" | "build"
    training_days_per_week: Mapped[int] = mapped_column(Integer)
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    is_cold_start: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_number: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    goal: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | approved
    plan_json: Mapped[dict] = mapped_column(JSONB)  # full plan object
    trainer_notes: Mapped[str | None] = mapped_column(Text)  # Claude's explanation of changes
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)

    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="plan", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("weekly_plans.id"))
    role: Mapped[str] = mapped_column(String(20))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    plan: Mapped["WeeklyPlan"] = relationship(back_populates="chat_messages")


class ExerciseTemplate(Base):
    """Hevy exercise templates, classified into PPL slots by muscle group."""
    __tablename__ = "exercise_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    slot: Mapped[str] = mapped_column(String(100))
    primary_muscle: Mapped[str | None] = mapped_column(String(100))
    secondary_muscles: Mapped[list] = mapped_column(JSONB, default=list)
    category: Mapped[str | None] = mapped_column(String(100))


class ExerciseHistory(Base):
    """One row per exercise per completed Hevy workout session."""
    __tablename__ = "exercise_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_template_id: Mapped[str] = mapped_column(String(100))
    exercise_name: Mapped[str] = mapped_column(String(200))
    slot: Mapped[str] = mapped_column(String(100))  # e.g. "chest_compound"
    workout_date: Mapped[date] = mapped_column(Date)
    week_number: Mapped[int] = mapped_column(Integer)
    sets_data: Mapped[list] = mapped_column(JSONB)  # [{reps, load_kg, completed}]
    notes: Mapped[str | None] = mapped_column(Text)
    hevy_workout_id: Mapped[str | None] = mapped_column(String(100))
