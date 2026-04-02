from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

SCAN_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

import worker_state


# ---------------------------------------------------------------------------
# Helpers to build fake Supabase chained-builder responses
# ---------------------------------------------------------------------------

def _make_response(data: list) -> MagicMock:
    resp = MagicMock()
    resp.data = data
    return resp


def _make_chain(response_data: list) -> MagicMock:
    """Returns a mock that supports arbitrary chained calls ending in .execute()."""
    terminal = MagicMock()
    terminal.execute.return_value = _make_response(response_data)
    chain = MagicMock()
    chain.return_value = terminal
    # Make every attribute access on chain return something that is also chainable
    # and ultimately calls execute() correctly.  We build a recursive chain mock.
    def _chainable(*args, **kwargs):
        return terminal
    chain.side_effect = None
    # Use a helper that propagates through any number of chained calls
    builder = _ChainBuilder(response_data)
    return builder


class _ChainBuilder:
    """Supports .table().select().eq().order().limit().execute() style chains."""

    def __init__(self, response_data: list) -> None:
        self._response_data = response_data
        self._calls: list = []

    def __call__(self, *args, **kwargs) -> _ChainBuilder:
        self._calls.append(("__call__", args, kwargs))
        return self

    def __getattr__(self, name: str) -> _ChainBuilder:
        # Return self for any attribute so the chain continues
        def method(*args, **kwargs):
            self._calls.append((name, args, kwargs))
            return self
        return method

    def execute(self):
        return _make_response(self._response_data)


# ---------------------------------------------------------------------------
# Proper mock client using MagicMock for precise call inspection
# ---------------------------------------------------------------------------

def _build_client_mock(table_response_data: list | None = None) -> MagicMock:
    """
    Builds a MagicMock Supabase client where table(...) returns a builder mock.
    All chained methods return the same builder mock, and .execute() returns
    a response with the given data.
    """
    if table_response_data is None:
        table_response_data = []

    response = MagicMock()
    response.data = table_response_data

    # Build a builder that supports arbitrary chaining
    builder = MagicMock()
    # Every method on builder returns builder itself (for chaining)
    builder.select.return_value = builder
    builder.insert.return_value = builder
    builder.upsert.return_value = builder
    builder.update.return_value = builder
    builder.eq.return_value = builder
    builder.is_.return_value = builder
    builder.order.return_value = builder
    builder.limit.return_value = builder
    builder.execute.return_value = response

    client = MagicMock()
    client.table.return_value = builder

    return client, builder, response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHeartbeat(unittest.TestCase):
    def test_upsert_called_with_correct_data_returns_worker_id(self):
        worker_id = "worker-uuid-1234"
        client, builder, response = _build_client_mock([{"id": worker_id}])

        with patch("db.get_client", return_value=client):
            result = worker_state.heartbeat("my-worker", tunnel_url="https://tunnel.example.com")

        client.table.assert_called_once_with("scanner_workers")
        builder.upsert.assert_called_once_with(
            {
                "name": "my-worker",
                "last_heartbeat": "now()",
                "status": "online",
                "tunnel_url": "https://tunnel.example.com",
            },
            on_conflict="name",
        )
        self.assertEqual(result, worker_id)

    def test_heartbeat_without_tunnel_url_omits_key(self):
        worker_id = "worker-uuid-5678"
        client, builder, response = _build_client_mock([{"id": worker_id}])

        with patch("db.get_client", return_value=client):
            result = worker_state.heartbeat("my-worker")

        upsert_payload = builder.upsert.call_args[0][0]
        self.assertNotIn("tunnel_url", upsert_payload)
        self.assertEqual(result, worker_id)

    def test_heartbeat_returns_worker_id(self):
        client, builder, response = _build_client_mock([{"id": "abc-def"}])

        with patch("db.get_client", return_value=client):
            result = worker_state.heartbeat("worker-x")

        self.assertEqual(result, "abc-def")


class TestCreateJob(unittest.TestCase):
    def test_insert_called_with_correct_data_returns_job_id(self):
        job_id = "job-uuid-9999"
        client, builder, response = _build_client_mock([{"id": job_id}])

        with patch("db.get_client", return_value=client):
            result = worker_state.create_job(
                "worker-123",
                "vpt_scan",
                {"cities": ["OAKLAND"]},
            )

        client.table.assert_called_once_with("scanner_jobs")
        builder.insert.assert_called_once_with(
            {
                "worker_id": "worker-123",
                "job_type": "vpt_scan",
                "scope": {"cities": ["OAKLAND"]},
                "status": "running",
            }
        )
        self.assertEqual(result, job_id)

    def test_status_is_always_running(self):
        client, builder, response = _build_client_mock([{"id": "j1"}])

        with patch("db.get_client", return_value=client):
            worker_state.create_job("w1", "pge_scan", {})

        insert_payload = builder.insert.call_args[0][0]
        self.assertEqual(insert_payload["status"], "running")


class TestUpdateJob(unittest.TestCase):
    def test_only_provided_kwargs_included_in_patch(self):
        client, builder, response = _build_client_mock([{"id": "j1"}])

        with patch("db.get_client", return_value=client):
            worker_state.update_job("job-abc", status="completed", processed_count=42)

        builder.update.assert_called_once_with(
            {"status": "completed", "processed_count": 42}
        )
        builder.eq.assert_called_once_with("id", "job-abc")

    def test_none_kwargs_not_included(self):
        client, builder, response = _build_client_mock([{"id": "j1"}])

        with patch("db.get_client", return_value=client):
            worker_state.update_job(
                "job-abc",
                status="interrupted",
                current_city=None,
                current_apn=None,
                hit_count=5,
            )

        patch_dict = builder.update.call_args[0][0]
        self.assertIn("status", patch_dict)
        self.assertIn("hit_count", patch_dict)
        self.assertNotIn("current_city", patch_dict)
        self.assertNotIn("current_apn", patch_dict)

    def test_all_kwargs_included_when_provided(self):
        client, builder, response = _build_client_mock([{"id": "j1"}])

        with patch("db.get_client", return_value=client):
            worker_state.update_job(
                "job-xyz",
                status="running",
                current_city="OAKLAND",
                current_apn="123-456-789",
                processed_count=100,
                hit_count=10,
                error_summary="some error",
            )

        patch_dict = builder.update.call_args[0][0]
        self.assertEqual(patch_dict["status"], "running")
        self.assertEqual(patch_dict["current_city"], "OAKLAND")
        self.assertEqual(patch_dict["current_apn"], "123-456-789")
        self.assertEqual(patch_dict["processed_count"], 100)
        self.assertEqual(patch_dict["hit_count"], 10)
        self.assertEqual(patch_dict["error_summary"], "some error")

    def test_no_db_call_when_no_kwargs(self):
        client, builder, response = _build_client_mock([])

        with patch("db.get_client", return_value=client):
            worker_state.update_job("job-empty")

        client.table.assert_not_called()


class TestWriteCheckpoint(unittest.TestCase):
    def test_insert_called_with_correct_data(self):
        client, builder, response = _build_client_mock([{"id": "cp1"}])

        with patch("db.get_client", return_value=client):
            worker_state.write_checkpoint(
                "job-123",
                city="OAKLAND",
                apn="001-002-003",
                row_offset=50,
                phase="scanning",
                extra={"foo": "bar"},
            )

        client.table.assert_called_once_with("scanner_job_checkpoints")
        builder.insert.assert_called_once_with(
            {
                "job_id": "job-123",
                "city": "OAKLAND",
                "apn": "001-002-003",
                "row_offset": 50,
                "phase": "scanning",
                "extra": {"foo": "bar"},
            }
        )

    def test_none_fields_omitted_from_insert(self):
        client, builder, response = _build_client_mock([{"id": "cp2"}])

        with patch("db.get_client", return_value=client):
            worker_state.write_checkpoint(
                "job-456",
                city=None,
                apn=None,
                row_offset=10,
                phase=None,
                extra=None,
            )

        payload = builder.insert.call_args[0][0]
        self.assertEqual(payload["job_id"], "job-456")
        self.assertEqual(payload["row_offset"], 10)
        self.assertNotIn("city", payload)
        self.assertNotIn("apn", payload)
        self.assertNotIn("phase", payload)
        self.assertNotIn("extra", payload)


class TestGetLatestCheckpoint(unittest.TestCase):
    def test_returns_checkpoint_when_found(self):
        checkpoint = {"id": "cp-1", "job_id": "job-1", "city": "BERKELEY"}
        client, builder, response = _build_client_mock([checkpoint])

        with patch("db.get_client", return_value=client):
            result = worker_state.get_latest_checkpoint("job-1")

        client.table.assert_called_once_with("scanner_job_checkpoints")
        builder.eq.assert_called_once_with("job_id", "job-1")
        builder.order.assert_called_once_with("created_at", desc=True)
        builder.limit.assert_called_once_with(1)
        self.assertEqual(result, checkpoint)

    def test_returns_none_when_no_results(self):
        client, builder, response = _build_client_mock([])

        with patch("db.get_client", return_value=client):
            result = worker_state.get_latest_checkpoint("job-no-checkpoints")

        self.assertIsNone(result)


class TestGetResumableJob(unittest.TestCase):
    def test_queries_interrupted_status_and_job_type(self):
        job_row = {"id": "job-resume-1", "job_type": "vpt_scan", "status": "interrupted"}
        checkpoint_row = {"id": "cp-resume-1", "job_id": "job-resume-1"}

        # We need two separate client mocks: one for the job query, one for the checkpoint.
        # Use a counter to return different data on successive get_client calls.
        job_client, job_builder, job_response = _build_client_mock([job_row])
        cp_client, cp_builder, cp_response = _build_client_mock([checkpoint_row])

        clients = [job_client, cp_client]
        call_count = 0

        def _get_client_side_effect():
            nonlocal call_count
            c = clients[call_count % len(clients)]
            call_count += 1
            return c

        with patch("db.get_client", side_effect=_get_client_side_effect):
            result = worker_state.get_resumable_job("vpt_scan")

        # Job query assertions
        job_client.table.assert_called_once_with("scanner_jobs")
        job_builder.eq.assert_any_call("status", "interrupted")
        job_builder.eq.assert_any_call("job_type", "vpt_scan")
        job_builder.order.assert_called_once_with("created_at", desc=True)
        job_builder.limit.assert_called_once_with(1)

        self.assertEqual(result["id"], "job-resume-1")
        self.assertEqual(result["checkpoint"], checkpoint_row)

    def test_returns_none_when_no_interrupted_jobs(self):
        client, builder, response = _build_client_mock([])

        with patch("db.get_client", return_value=client):
            result = worker_state.get_resumable_job("vpt_scan")

        self.assertIsNone(result)

    def test_includes_checkpoint_key(self):
        job_row = {"id": "j2", "job_type": "pge_scan", "status": "interrupted"}
        checkpoint_row = {"id": "cp-2", "job_id": "j2", "phase": "checking"}

        clients_data = [[job_row], [checkpoint_row]]
        call_count = 0

        def _get_client():
            nonlocal call_count
            c_mock, b_mock, r_mock = _build_client_mock(clients_data[call_count % len(clients_data)])
            call_count += 1
            return c_mock

        with patch("db.get_client", side_effect=_get_client):
            result = worker_state.get_resumable_job("pge_scan")

        self.assertIn("checkpoint", result)
        self.assertEqual(result["checkpoint"]["phase"], "checking")


class TestMarkDiscovery(unittest.TestCase):
    def test_update_called_with_null_filter_returns_true_on_update(self):
        client, builder, response = _build_client_mock([{"apn": "111-222-333"}])

        with patch("db.get_client", return_value=client):
            result = worker_state.mark_discovery("111-222-333", "job-disc-1")

        client.table.assert_called_once_with("bills")
        builder.update.assert_called_once_with(
            {"first_seen_at": "now()", "discovered_by_job_id": "job-disc-1"}
        )
        builder.eq.assert_called_once_with("apn", "111-222-333")
        builder.is_.assert_called_once_with("first_seen_at", "null")
        self.assertTrue(result)

    def test_returns_false_when_no_rows_updated(self):
        client, builder, response = _build_client_mock([])

        with patch("db.get_client", return_value=client):
            result = worker_state.mark_discovery("already-seen-apn", "job-disc-2")

        self.assertFalse(result)

    def test_returns_true_when_row_was_updated(self):
        client, builder, response = _build_client_mock([{"apn": "999-888-777"}])

        with patch("db.get_client", return_value=client):
            result = worker_state.mark_discovery("999-888-777", "job-new")

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
