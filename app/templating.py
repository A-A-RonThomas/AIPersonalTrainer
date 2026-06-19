from jinja2 import Environment, FileSystemLoader
from starlette.templating import Jinja2Templates

_env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=True,
    cache_size=0,
)

_env.filters["lbs"] = lambda kg: round(kg * 2.2046) if kg else 0

templates = Jinja2Templates(env=_env)
