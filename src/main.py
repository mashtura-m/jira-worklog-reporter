"""
CLI entry-point for Jira Worklog Reporter
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.config import Config
from src.jira_client import JiraClient
from src.worklog_aggregator import WorklogAggregator

# Load environment variables from .env (if present)
load_dotenv()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_date(date_str: str, end_of_day: bool = False) -> datetime:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.replace(hour=23, minute=59, second=59) if end_of_day else dt


def main() -> int:
    cfg = Config.from_env()
    configure_logging(cfg.log_level)
    log = logging.getLogger(__name__)

    log.info("=" * 50)
    log.info(" Jira Worklog Report | %s → %s", cfg.start_date, cfg.end_date)
    log.info("=" * 50)

    start_dt = parse_date(cfg.start_date)
    end_dt = parse_date(cfg.end_date, end_of_day=True)

    cache_path: Path | None = None
    if cfg.use_cache:
        cache_path = cfg.cache_file
        cache_path.parent.mkdir(parents=True, exist_ok=True)

    client = JiraClient(cfg.base_url, cfg.email, cfg.api_token)
    aggregator = WorklogAggregator(client, cache_path=cache_path)

    records = aggregator.collect(cfg.project, start_dt, end_dt)

    if not records:
        log.warning("No worklogs found.")
        return 0

    from src.excel_generator import build_excel  # lazy import

    cfg.output_file.parent.mkdir(parents=True, exist_ok=True)

    build_excel(
        records,
        start_dt,
        end_dt,
        str(cfg.output_file),
        cfg.project,
    )

    log.info("Report written → %s", cfg.output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())