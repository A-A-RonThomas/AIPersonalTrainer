from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import settings
from app.hevy.adapter import HevyClient
from app.templating import templates

router = APIRouter()

KG_TO_LBS = 2.20462


def _rolling_avg(sorted_entries: list[dict], window: int = 7) -> list[float | None]:
    weights = [e["weight_lbs"] for e in sorted_entries]
    avgs = []
    for i in range(len(weights)):
        window_vals = weights[max(0, i - window + 1): i + 1]
        avgs.append(round(sum(window_vals) / len(window_vals), 1))
    return avgs


@router.get("/weight", response_class=HTMLResponse)
async def weight_chart(request: Request):
    hevy = HevyClient(settings.hevy_api_key)
    raw = hevy.get_all_body_measurements()

    entries = []
    for m in raw:
        weight_kg = m.get("weight_kg")
        if weight_kg is None:
            continue
        created_at = m.get("created_at", "")
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_str = dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue
        entries.append({"date": date_str, "weight_lbs": round(weight_kg * KG_TO_LBS, 1)})

    # Sort ascending by date, keep only the latest entry per day
    by_date: dict[str, float] = {}
    for e in entries:
        by_date[e["date"]] = e["weight_lbs"]

    sorted_entries = [{"date": d, "weight_lbs": w} for d, w in sorted(by_date.items())]
    rolling = _rolling_avg(sorted_entries)

    chart_data = {
        "labels": [e["date"] for e in sorted_entries],
        "weights": [e["weight_lbs"] for e in sorted_entries],
        "rolling": rolling,
    }

    return templates.TemplateResponse(request, "weight.html", {"chart_data": chart_data})
