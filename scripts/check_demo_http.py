"""Bounded HTTP smoke check for local or CI Streamlit startup."""

import http.client
import time
import urllib.error
import urllib.request


def check_demo() -> None:
    deadline = time.monotonic() + 60
    while True:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8501/_stcore/health", timeout=3
            ) as response:
                assert response.status == 200
                assert response.read().strip() == b"ok"
            break
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.RemoteDisconnected,
        ):
            # Docker can expose the forwarded port before Streamlit starts listening.
            # Retry only startup transport failures, retaining the deadline and content assertions.
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    with urllib.request.urlopen("http://127.0.0.1:8501/", timeout=3) as response:
        assert response.status == 200
        assert b"<html" in response.read().lower()
    print("Streamlit health and root returned HTTP 200")


if __name__ == "__main__":
    check_demo()
