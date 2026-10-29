# FlowLens backend and the fixture apps (same Python environment). Built from the repository root.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/opt/venv/bin:$PATH

RUN pip install --no-cache-dir "uv>=0.5"

WORKDIR /app/backend
# Dependencies first (cached), exactly as locked in uv.lock.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# Chromium matching the locked Playwright version, with its system libraries.
RUN python -m playwright install --with-deps chromium

COPY backend/ /app/backend/
RUN uv sync --frozen --no-dev
COPY fixtures/ /app/fixtures/
COPY demo/ /app/demo/

EXPOSE 8000
CMD ["uvicorn", "flowlens.main:app", "--host", "0.0.0.0", "--port", "8000"]
