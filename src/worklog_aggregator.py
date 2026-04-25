"""
worklog_aggregator.py
~~~~~~~~~~~~~~~~~~~~~
Fetches, filters, and normalises Jira worklogs into plain records.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from .jira_client import JiraClient, to_utc_naive

logger = logging.getLogger(__name__)


class WorklogRecord(TypedDict):
    issue  : str
    author : str
    started: datetime
    hours  : float


class WorklogAggregator:
    """
    Orchestrates worklog collection for a single Jira project and date range.

    Parameters
    ----------
    client:
        A configured :class:`JiraClient` instance.
    cache_path:
        Optional filesystem path for JSON caching.  Pass ``None`` to disable.
    """

    def __init__(self, client: JiraClient, cache_path: Path | None = None) -> None:
        self._client     = client
        self._cache_path = cache_path

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def collect(
        self,
        project   : str,
        start_date: datetime,
        end_date  : datetime,
    ) -> list[WorklogRecord]:
        """
        Return filtered worklog records for *project* within [start_date, end_date].

        Results are read from the on-disk cache when available; otherwise they
        are fetched from Jira and the cache is populated for subsequent runs.
        """
        if self._cache_path:
            cached = self._load_cache()
            if cached is not None:
                logger.info("Using cached worklog data from %s", self._cache_path)
                return cached

        logger.info("Fetching fresh worklog data from Jira…")
        records = self._fetch_and_filter(project, start_date, end_date)

        if self._cache_path:
            self._save_cache(records)

        return records

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _fetch_and_filter(
        self,
        project   : str,
        start_date: datetime,
        end_date  : datetime,
    ) -> list[WorklogRecord]:
        keys    = self._client.fetch_issue_keys(project)
        records : list[WorklogRecord] = []
        authors : set[str] = set()

        for idx, key in enumerate(keys, start=1):
            worklogs = self._client.fetch_worklogs(key)

            for entry in worklogs:
                started = to_utc_naive(entry["started"])
                if not (start_date <= started <= end_date):
                    continue

                author = entry.get("author", {}).get("displayName", "Unknown")
                authors.add(author)
                records.append(
                    WorklogRecord(
                        issue   = key,
                        author  = author,
                        started = started,
                        hours   = entry.get("timeSpentSeconds", 0) / 3600,
                    )
                )

            logger.debug("[%d/%d] %s — %d log(s)", idx, len(keys), key, len(worklogs))

        logger.info("Unique authors    : %d — %s", len(authors), sorted(authors))
        logger.info("Filtered records  : %d", len(records))
        return records

    # ------------------------------------------------------------------ #
    #  Cache I/O                                                           #
    # ------------------------------------------------------------------ #

    def _save_cache(self, records: list[WorklogRecord]) -> None:
        assert self._cache_path is not None
        with self._cache_path.open("w", encoding="utf-8") as fh:
            json.dump(records, fh, default=str)
        logger.info("Cache saved → %s", self._cache_path)

    def _load_cache(self) -> list[WorklogRecord] | None:
        if self._cache_path is None or not self._cache_path.exists():
            return None
        with self._cache_path.open(encoding="utf-8") as fh:
            return json.load(fh)
