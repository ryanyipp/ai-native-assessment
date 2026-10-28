"""FlowLens API. Start:  uvicorn flowlens.main:app --port 8000  (from backend/)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flowlens.api.runs import router
from flowlens.config import get_settings
from flowlens.storage.db import Store


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    app.state.settings = settings
    app.state.store = Store(settings.database_path)
    app.state.store.mark_interrupted()
    yield


app = FastAPI(title="FlowLens", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{get_settings().frontend_port}", f"http://127.0.0.1:{get_settings().frontend_port}"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
