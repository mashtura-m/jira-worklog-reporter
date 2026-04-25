"""
tests/test_jira_client.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for JiraClient and WorklogAggregator.
All Jira API calls are mocked — no network required.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.jira_client        import JiraClient, JiraClientError, to_utc_naive
from src.worklog_aggregator import WorklogAggregator


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client() -> JiraClient:
    return JiraClient(
        base_url  = "https://example.atlassian.net",
        email     = "test@example.com",
        api_token = "dummy",
    )


# ── to_utc_naive ─────────────────────────────────────────────────────────────

class TestToUtcNaive:
    def test_iso_with_offset(self):
        dt = to_utc_naive("2026-04-17T17:00:00.000-0500")
        assert dt == datetime(2026, 4, 17, 22, 0, 0)
        assert dt.tzinfo is None

    def test_naive_string(self):
        dt = to_utc_naive("2026-04-02 04:30:00")
        assert dt == datetime(2026, 4, 2, 4, 30, 0)

    def test_with_microseconds(self):
        dt = to_utc_naive("2026-04-02 04:30:00.123000")
        assert dt.microsecond == 123000


# ── JiraClient ────────────────────────────────────────────────────────────────

class TestFetchIssueKeys:
    def _mock_response(self, issues: list, next_token: str | None = None):
        mock = MagicMock()
        mock.ok = True
        payload: dict = {"issues": issues}
        if next_token:
            payload["nextPageToken"] = next_token
        mock.json.return_value = payload
        return mock

    @patch("src.jira_client.requests.post")
    def test_single_page(self, mock_post, client):
        issues = [{"key": f"PROJ-{i}"} for i in range(3)]
        mock_post.return_value = self._mock_response(issues)

        keys = client.fetch_issue_keys("PROJ")
        # Called twice (non-subtasks + subtasks)
        assert mock_post.call_count == 2
        # 3 non-subtasks + 3 subtasks, but deduplicated (same mock returns same keys)
        assert set(keys) == {"PROJ-0", "PROJ-1", "PROJ-2"}

    @patch("src.jira_client.requests.post")
    def test_http_error_raises(self, mock_post, client):
        mock = MagicMock()
        mock.ok = False
        mock.status_code = 403
        mock.text = "Forbidden"
        mock_post.return_value = mock

        with pytest.raises(JiraClientError, match="403"):
            client.fetch_issue_keys("PROJ")


class TestFetchWorklogs:
    @patch("src.jira_client.requests.get")
    def test_single_page(self, mock_get, client):
        mock = MagicMock()
        mock.ok = True
        mock.json.return_value = {
            "worklogs": [{"id": "1"}, {"id": "2"}],
            "total"   : 2,
        }
        mock_get.return_value = mock

        logs = client.fetch_worklogs("PROJ-1")
        assert len(logs) == 2

    @patch("src.jira_client.requests.get")
    def test_empty_worklogs(self, mock_get, client):
        mock = MagicMock()
        mock.ok = True
        mock.json.return_value = {"worklogs": [], "total": 0}
        mock_get.return_value = mock

        logs = client.fetch_worklogs("PROJ-99")
        assert logs == []


# ── WorklogAggregator ─────────────────────────────────────────────────────────

class TestWorklogAggregator:
    _START = datetime(2026, 4, 1)
    _END   = datetime(2026, 4, 30, 23, 59, 59)

    def _make_aggregator(self, client, cache_path=None):
        return WorklogAggregator(client, cache_path=cache_path)

    def test_filters_by_date_range(self):
        mock_client = MagicMock(spec=JiraClient)
        mock_client.fetch_issue_keys.return_value = ["PROJ-1"]
        mock_client.fetch_worklogs.return_value = [
            {
                "started"         : "2026-04-15T10:00:00.000+0000",
                "timeSpentSeconds": 3600,
                "author"          : {"displayName": "Alice"},
            },
            {
                "started"         : "2026-03-01T10:00:00.000+0000",
                "timeSpentSeconds": 3600,
                "author"          : {"displayName": "Bob"},
            },
        ]

        agg     = self._make_aggregator(mock_client)
        records = agg.collect("PROJ", self._START, self._END)

        assert len(records) == 1
        assert records[0]["author"] == "Alice"
        assert records[0]["hours"] == 1.0

    def test_cache_is_written_and_read(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        mock_client = MagicMock(spec=JiraClient)
        mock_client.fetch_issue_keys.return_value = ["PROJ-1"]
        mock_client.fetch_worklogs.return_value = [
            {
                "started"         : "2026-04-10T08:00:00.000+0000",
                "timeSpentSeconds": 7200,
                "author"          : {"displayName": "Charlie"},
            }
        ]

        agg = self._make_aggregator(mock_client, cache_path=cache_file)
        agg.collect("PROJ", self._START, self._END)

        assert cache_file.exists(), "Cache file was not created"

        # Second call should hit cache and NOT call Jira again
        agg2    = self._make_aggregator(mock_client, cache_path=cache_file)
        records = agg2.collect("PROJ", self._START, self._END)

        assert mock_client.fetch_issue_keys.call_count == 1  # only called once
        assert len(records) == 1
