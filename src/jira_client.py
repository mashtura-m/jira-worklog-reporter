"""
jira_client.py
~~~~~~~~~~~~~~
Low-level Jira REST API client: issue-key discovery and worklog retrieval.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterator

import requests
from dateutil.parser import parse as parse_dt
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class JiraClientError(Exception):
    """Raised when a Jira API call fails."""


class JiraClient:
    """Thread-safe, pagination-aware Jira REST v3 client."""

    _SEARCH_URL_TPL   = "{base}/rest/api/3/search/jql"
    _WORKLOG_URL_TPL  = "{base}/rest/api/3/issue/{key}/worklog"
    _DEFAULT_PAGE     = 100

    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth     = HTTPBasicAuth(email, api_token)
        self._headers  = {"Accept": "application/json"}

    # ------------------------------------------------------------------ #
    #  Issue-key discovery                                                 #
    # ------------------------------------------------------------------ #

    def _iter_issue_keys(self, jql: str) -> Iterator[str]:
        """Yield all issue keys matching *jql*, handling cursor-based pagination."""
        url    = self._SEARCH_URL_TPL.format(base=self._base_url)
        cursor = None
        total  = 0

        while True:
            payload: dict = {
                "jql"       : jql,
                "fields"    : ["summary", "issuetype"],
                "maxResults": self._DEFAULT_PAGE,
            }
            if cursor:
                payload["nextPageToken"] = cursor

            response = self._post(url, payload)
            batch    = response.get("issues", [])

            for issue in batch:
                yield issue["key"]

            total  += len(batch)
            cursor  = response.get("nextPageToken")
            logger.debug("Issue keys fetched so far: %d", total)

            if not cursor or not batch:
                break

    def fetch_issue_keys(self, project: str) -> list[str]:
        """
        Return every issue key in *project* (non-subtasks + subtasks).

        Two separate JQL passes guarantee complete coverage — Jira's
        ``issueType not in subtaskIssueTypes()`` filter otherwise silently
        omits sub-tasks from mixed queries.
        """
        jql_non_subtasks = (
            f'project = "{project}" AND issueType not in subtaskIssueTypes() '
            f"ORDER BY created ASC"
        )
        jql_subtasks = (
            f'project = "{project}" AND issueType in subtaskIssueTypes() '
            f"ORDER BY created ASC"
        )

        logger.info("[Pass 1] Fetching non-subtask issues…")
        keys_a = list(self._iter_issue_keys(jql_non_subtasks))
        logger.info("  → %d non-subtask issues", len(keys_a))

        logger.info("[Pass 2] Fetching subtask issues…")
        keys_b = list(self._iter_issue_keys(jql_subtasks))
        logger.info("  → %d subtask issues", len(keys_b))

        # Merge, preserving order, deduplicating
        seen: set[str] = set()
        merged: list[str] = []
        for key in keys_a + keys_b:
            if key not in seen:
                seen.add(key)
                merged.append(key)

        logger.info("Total unique issues: %d", len(merged))
        return merged

    # ------------------------------------------------------------------ #
    #  Worklog retrieval                                                   #
    # ------------------------------------------------------------------ #

    def fetch_worklogs(self, issue_key: str) -> list[dict]:
        """Return all worklog entries for *issue_key*."""
        url     = self._WORKLOG_URL_TPL.format(base=self._base_url, key=issue_key)
        entries: list[dict] = []
        start   = 0

        while True:
            response = self._get(url, params={"startAt": start, "maxResults": self._DEFAULT_PAGE})
            batch    = response.get("worklogs", [])
            if not batch:
                break
            entries.extend(batch)
            start += len(batch)
            if start >= response.get("total", 0):
                break

        return entries

    # ------------------------------------------------------------------ #
    #  HTTP helpers                                                        #
    # ------------------------------------------------------------------ #

    def _get(self, url: str, params: dict | None = None) -> dict:
        response = requests.get(
            url,
            params=params,
            auth=self._auth,
            headers=self._headers,
            timeout=30,
        )
        self._raise_for_status(response)
        return response.json()

    def _post(self, url: str, payload: dict) -> dict:
        response = requests.post(
            url,
            json=payload,
            auth=self._auth,
            headers=self._headers,
            timeout=30,
        )
        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if not response.ok:
            raise JiraClientError(
                f"Jira API error {response.status_code}: {response.text[:300]}"
            )


# ------------------------------------------------------------------ #
#  Date utilities                                                      #
# ------------------------------------------------------------------ #

def to_utc_naive(timestamp: str) -> datetime:
    """
    Parse a Jira timestamp string to a **naive UTC** :class:`datetime`.

    Handles formats such as:
    - ``"2026-04-17T17:00:00.000-0500"``  (ISO 8601 with UTC offset)
    - ``"2026-04-02 04:30:00"``           (naive, assumed UTC)
    - ``"2026-04-02 04:30:00.123000"``    (naive with microseconds)
    """
    dt = parse_dt(timestamp)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
