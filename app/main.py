from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import chat, plan, setup, weight

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Trainer")

app.include_router(plan.router)
app.include_router(chat.router)
app.include_router(setup.router)
app.include_router(weight.router)
