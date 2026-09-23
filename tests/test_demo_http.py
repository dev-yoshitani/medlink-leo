from unittest.mock import MagicMock

import pytest

from scripts import check_demo_http


def response(body):
    value = MagicMock()
    value.__enter__.return_value = value
    value.status = 200
    value.read.return_value = body
    return value


def test_startup_connection_reset_is_retried(monkeypatch):
    opener = MagicMock(side_effect=[ConnectionResetError(), response(b"ok"), response(b"<html>")])
    monkeypatch.setattr(check_demo_http.urllib.request, "urlopen", opener)
    monkeypatch.setattr(check_demo_http.time, "sleep", lambda _: None)
    check_demo_http.check_demo()
    assert opener.call_count == 3


def test_persistent_connection_failure_reaches_deadline(monkeypatch):
    monkeypatch.setattr(
        check_demo_http.urllib.request, "urlopen", MagicMock(side_effect=ConnectionResetError())
    )
    monkeypatch.setattr(check_demo_http.time, "monotonic", MagicMock(side_effect=[0, 61]))
    with pytest.raises(ConnectionResetError):
        check_demo_http.check_demo()


def test_wrong_health_body_is_not_hidden_by_retry(monkeypatch):
    monkeypatch.setattr(
        check_demo_http.urllib.request, "urlopen", MagicMock(return_value=response(b"wrong app"))
    )
    with pytest.raises(AssertionError):
        check_demo_http.check_demo()
