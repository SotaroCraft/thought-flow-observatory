"""Unit-test safety: deny unexpected outbound network access."""

from __future__ import annotations

import socket
import urllib.request

import pytest


@pytest.fixture(autouse=True)
def _deny_unit_test_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail closed on unexpected urllib/socket network from ordinary unit tests."""

    def _blocked_connect(self: socket.socket, *args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "UNIT_TEST_NETWORK_DENIED: unexpected outbound socket connection"
        )

    def _blocked_urlopen(*args: object, **kwargs: object) -> None:
        raise RuntimeError("UNIT_TEST_NETWORK_DENIED: unexpected urllib request")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    monkeypatch.setattr(urllib.request, "urlopen", _blocked_urlopen)
