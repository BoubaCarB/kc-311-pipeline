"""Settings, read from the environment.

Everything configurable lives here and arrives via environment variables,
so the same code runs from a laptop and from GitHub Actions with no edits.
No paths to anybody's Desktop.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    dataset_url: str
    app_token: str | None
    source_tz: ZoneInfo
    window_months: int
    data_dir: Path
    sheet_id: str | None
    service_account_file: Path
    service_account_json: str | None


def load() -> Settings:
    # A real environment variable wins over .env, so CI secrets are never
    # shadowed by a stray local file.
    load_dotenv(override=False)
    env = os.environ.get
    return Settings(
        dataset_url=env("KC311_DATASET_URL") or "https://data.kcmo.org/resource/d4px-6rwg.json",
        app_token=env("KC311_APP_TOKEN") or None,
        source_tz=ZoneInfo(env("KC311_SOURCE_TIMEZONE") or "America/Chicago"),
        window_months=int(env("KC311_WINDOW_MONTHS") or 12),
        data_dir=Path(env("KC311_DATA_DIR") or "./data"),
        sheet_id=env("GOOGLE_SHEET_ID") or None,
        service_account_file=Path(env("GOOGLE_SERVICE_ACCOUNT_FILE") or "./service-account.json"),
        service_account_json=env("GOOGLE_SERVICE_ACCOUNT_JSON") or None,
    )
