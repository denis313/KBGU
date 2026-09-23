from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers import auth, catalog, diary, menu, profile, telegram

WEB_PAGE = Path(__file__).resolve().parent.parent / "web" / "Calorie Tracker BnB v2.html"

app = FastAPI(
    title="Calorie Tracker",
    version="2.0.0",
    description="Calorie targets, food diary and generated menus backed by PostgreSQL.",
)

for module in (auth, profile, catalog, diary, menu, telegram):
    app.include_router(module.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_PAGE)
