"""Runtime settings, read from the repository-root .env.

Empty values in .env fall back to the defaults below, so a partially filled
.env still works. Secrets are never logged or returned by the API.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3-flash-preview"

    # Overall credit pool across all runs (tracked from recorded usage).
    flowlens_budget_usd: float = 10.0
    # Per-run cap, deliberately small while the slice is being tuned.
    flowlens_run_budget_usd: float = 0.50
    flowlens_max_concurrent_model_calls: int = 2
    flowlens_max_model_calls_per_run: int = 40
    flowlens_max_output_tokens: int = 800
    flowlens_max_steps: int = 15
    flowlens_model_timeout_s: float = 60.0
    flowlens_provider_json_schema: bool = False  # send reply schemas to the provider (off: see llm.py)

    app_env: str = "development"
    backend_port: int = 8000
    frontend_port: int = 5173
    fixture_port: int = 5174
    artifacts_dir: Path = Field(default=REPO_ROOT / "artifacts")
    database_url: str = ""
    # creator-studio :5174 broken / :5175 corrected; ticket-desk (held out) :5176 broken / :5177 corrected.
    flowlens_allowed_origins: str = (
        "http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,"
        "http://localhost:5176,http://127.0.0.1:5176,http://localhost:5177,http://127.0.0.1:5177"
    )
    # Harness endpoint (POST) that provisions an isolated test-data workspace, and
    # the cookie that selects it. Empty endpoint = no isolation; verification is
    # then inconclusive because controlled test data cannot be set up.
    flowlens_workspace_endpoint: str = "/__fixture/workspaces"
    flowlens_workspace_cookie: str = "cs_ws"
    flowlens_test_session_path: str = ""
    flowlens_headless: bool = True

    @property
    def artifacts_path(self) -> Path:
        p = self.artifacts_dir
        if not p.is_absolute():
            p = (REPO_ROOT / p).resolve()
        return p

    @property
    def database_path(self) -> Path:
        url = self.database_url
        if url.startswith("sqlite:///"):
            p = Path(url.removeprefix("sqlite:///"))
            return p if p.is_absolute() else (REPO_ROOT / p).resolve()
        return self.artifacts_path / "flowlens.db"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.flowlens_allowed_origins.split(",") if o.strip()]

    @property
    def has_api_key(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_api_key.get_secret_value().strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
