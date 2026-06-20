from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.hevy.adapter import HevyClient
from app.models import BodyWeight
from app.templating import templates

router = APIRouter()


def _rolling_avg(sorted_entries: list[BodyWeight], window: int = 7) -> list[float | None]:
    weights = [e.weight_lbs for e in sorted_entries]
    avgs = []
    for i in range(len(weights)):
        window_vals = weights[max(0, i - window + 1): i + 1]
        avgs.append(round(sum(window_vals) / len(window_vals), 1))
    return avgs


@router.get("/weight", response_class=HTMLResponse)
async def weight_chart(request: Request, db: Session = Depends(get_db)):
    entries = db.query(BodyWeight).order_by(BodyWeight.date).all()
    rolling = _rolling_avg(entries)

    chart_data = {
        "labels": [e.date.isoformat() for e in entries],
        "weights": [e.weight_lbs for e in entries],
        "rolling": rolling,
    }

    return templates.TemplateResponse(request, "weight.html", {
        "chart_data": chart_data,
        "today": date.today().isoformat(),
    })


@router.post("/weight")
async def log_weight(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    entry_date = date.fromisoformat(str(form.get("date")))
    weight_lbs = round(float(str(form.get("weight_lbs"))), 1)

    existing = db.query(BodyWeight).filter(BodyWeight.date == entry_date).first()
    if existing:
        existing.weight_lbs = weight_lbs
    else:
        db.add(BodyWeight(date=entry_date, weight_lbs=weight_lbs))
    db.commit()

    return RedirectResponse(url="/weight", status_code=303)


@router.get("/debug/body-measurements")
async def debug_body_measurements():
    hevy = HevyClient(settings.hevy_api_key)
    try:
        data = hevy._get("/body_measurements", {"page": 1, "pageSize": 10})
        return {"status": "ok", "data": data}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/debug/sync-dry-run")
async def debug_sync_dry_run():
    hevy = HevyClient(settings.hevy_api_key)
    raw = hevy.get_all_body_measurements()
    return {"raw_count": len(raw), "first_3": raw[:3]}


@router.get("/debug/weight-db")
async def debug_weight_db(db: Session = Depends(get_db)):
    rows = db.query(BodyWeight).order_by(BodyWeight.date.desc()).limit(10).all()
    return {"count": db.query(BodyWeight).count(), "latest": [{"date": str(r.date), "weight_lbs": r.weight_lbs} for r in rows]}


@router.post("/weight/sync")
async def sync_from_hevy(request: Request, db: Session = Depends(get_db)):
    hevy = HevyClient(settings.hevy_api_key)
    raw = hevy.get_all_body_measurements()

    KG_TO_LBS = 2.20462
    imported = 0
    for m in raw:
        weight_kg = m.get("weight_kg")
        if weight_kg is None:
            continue
        date_str = m.get("date", "")
        if not date_str:
            continue
        try:
            entry_date = date.fromisoformat(date_str[:10])
        except ValueError:
            continue
        weight_lbs = round(weight_kg * KG_TO_LBS, 1)
        existing = db.query(BodyWeight).filter(BodyWeight.date == entry_date).first()
        if existing:
            existing.weight_lbs = weight_lbs
        else:
            db.add(BodyWeight(date=entry_date, weight_lbs=weight_lbs))
            imported += 1

    db.commit()
    return RedirectResponse(url="/weight", status_code=303)


@router.post("/weight/delete")
async def delete_weight(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    entry_date = date.fromisoformat(str(form.get("date")))
    db.query(BodyWeight).filter(BodyWeight.date == entry_date).delete()
    db.commit()
    return RedirectResponse(url="/weight", status_code=303)
