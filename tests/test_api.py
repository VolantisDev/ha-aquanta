"""Unit tests for the vendored Aquanta API client (no Home Assistant needed)."""

import pytest

from custom_components.aquanta.api import (
    API_V2,
    AquantaConnectionError,
    AquantaDevice,
    AquantaHelper,
)


class FakeResp:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status=200, content=b"{}", json_data=None):
        """Store the canned status/body."""
        self.status_code = status
        self.content = content
        self._json = {} if json_data is None else json_data

    @property
    def ok(self):
        """Return True for 2xx."""
        return 200 <= self.status_code < 300

    def json(self):
        """Return the canned JSON body."""
        return self._json


class FakeSession:
    """Returns queued responses and records calls."""

    def __init__(self, responses):
        """Queue the responses to return in order."""
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kw):
        """Record the call and pop the next queued response."""
        self.calls.append((method, url, kw))
        return self.responses.pop(0)


def _make(responses, reauth=None):
    session = FakeSession(responses)
    helper = AquantaHelper(session, 10, reauth or (lambda stale: None))
    helper.headers = {"Authorization": "Bearer old"}
    return AquantaDevice(helper, 1), helper, session


def test_set_setpoint_body_and_path():
    """set_setpoint PATCHes /devices/advanced with the batch body."""
    dev, _helper, session = _make([FakeResp()])
    dev.set_setpoint(49)
    method, url, kw = session.calls[0]
    assert method == "PATCH"
    assert url == API_V2 + "/devices/advanced"
    assert kw["json"] == [
        {"id": 1, "patch": {"op": "replace", "path": "setPoint", "value": 49}}
    ]


def test_set_setpoint_out_of_range():
    """An out-of-range setpoint raises ValueError."""
    dev, _helper, _session = _make([FakeResp()])
    with pytest.raises(ValueError):
        dev.set_setpoint(500)


def test_set_mode_thermostat_sets_exclusive_flags():
    """set_mode('thermostat') enables one flag and disables the rest."""
    dev, _helper, session = _make([FakeResp()])
    dev.set_mode("thermostat")
    body = session.calls[0][2]["json"]
    flags = {e["patch"]["path"]: e["patch"]["value"] for e in body}
    assert flags == {
        "thermostatEnabled": True,
        "timerEnabled": False,
        "touEnabled": False,
        "intelEnabled": False,
        "controlEnabled": True,
    }


def test_set_mode_off():
    """set_mode('off') only disables controlEnabled."""
    dev, _helper, session = _make([FakeResp()])
    dev.set_mode("off")
    assert session.calls[0][2]["json"] == [
        {"id": 1, "patch": {"op": "replace", "path": "controlEnabled", "value": False}}
    ]


def test_set_mode_invalid():
    """An unknown mode raises ValueError."""
    dev, _helper, _session = _make([FakeResp()])
    with pytest.raises(ValueError):
        dev.set_mode("bogus")


def test_401_triggers_single_reauth_and_retry():
    """A 401 re-auths once and retries the request."""
    state = {"reauths": 0, "helper": None}

    def reauth(_stale):
        state["reauths"] += 1
        state["helper"].headers = {"Authorization": "Bearer new"}

    dev, helper, session = _make(
        [FakeResp(401, b""), FakeResp(200, b"{}", {"temperature": 45})], reauth=reauth
    )
    state["helper"] = helper
    assert dev.water == {"temperature": 45}
    assert state["reauths"] == 1
    assert len(session.calls) == 2


def test_get_empty_body_raises():
    """An empty 2xx body on a GET is treated as a connection error."""
    dev, _helper, _session = _make([FakeResp(200, b"", None)])
    with pytest.raises(AquantaConnectionError):
        _ = dev.water
