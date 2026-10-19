"""Vendored Aquanta cloud API client.

Replaces the external ``aquanta==0.2`` PyPI dependency. Interface-compatible with it
(``Aquanta(email, password)``, ``.devices()``, ``device.water/.infocenter/.advanced``,
``set_boost``/``delete_boost``/``set_away``/``delete_away``) so the rest of the
integration needs only an import swap, while adding:

  * token lifecycle: Firebase refresh + automatic re-auth on 401 (the pip client
    authenticated once and never refreshed);
  * setpoint and mode writes (the pip client had none);
  * typed errors (AquantaConnectionError / AquantaAuthError, both RuntimeError
    subclasses so existing ``except RuntimeError`` callers still work);
  * a lock serialising re-auth, and ``close()`` for the shared session.

Reconstructed from the Aquanta app and cross-checked against aquanta==0.2.
Units: setPoint and water.temperature are degC.
"""

from __future__ import annotations

import threading
from typing import Any

import requests

FIREBASE_WEB_API_KEY = "AIzaSyBHWHB8Org9BWCH-YFzis-8oEbMaKmI2Tw"
IDENTITY_TOOLKIT = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)
SECURE_TOKEN = "https://securetoken.googleapis.com/v1/token"
API_ROOT = "https://api.aquanta.io"
API_V2 = API_ROOT + "/v2"

SETPOINT_MIN = 10  # app setPointMin = 10 degC
SETPOINT_MAX = 110  # app setPointMax = 110 degC

# Mutually-exclusive mode flags in `advanced`.
MODE_FIELDS = {
    "thermostat": "thermostatEnabled",
    "timer": "timerEnabled",
    "tou": "touEnabled",
    "intelligence": "intelEnabled",
}

# Firebase error strings that mean the credentials are wrong (vs a transient outage).
_AUTH_ERROR_MARKERS = (
    "EMAIL_NOT_FOUND",
    "INVALID_PASSWORD",
    "INVALID_LOGIN_CREDENTIALS",
    "USER_DISABLED",
    "MISSING_PASSWORD",
    "INVALID_EMAIL",
)


class AquantaError(RuntimeError):
    """Base error. Subclasses RuntimeError for backwards-compatible handling."""


class AquantaConnectionError(AquantaError):
    """A transient/network/server failure talking to Aquanta."""


class AquantaAuthError(AquantaError):
    """Credentials were rejected."""


class AquantaHelper:
    """GET/PUT/PATCH/DELETE against api.aquanta.io, with re-auth on 401."""

    def __init__(self, session: requests.Session, timeout: int, reauth) -> None:
        """Store the shared session, timeout and re-auth callback."""
        self._session = session
        self._timeout = timeout
        self._reauth = reauth  # callable(stale_auth: str | None) -> None
        self.headers: dict[str, str] = {}

    def _send(self, method: str, url: str, **kw) -> requests.Response:
        try:
            return self._session.request(
                method, url, timeout=self._timeout, headers=self.headers, **kw
            )
        except requests.RequestException:
            # Strip the message so a token in a URL is never logged.
            raise AquantaConnectionError(f"{method} {url} failed") from None

    def _do(self, method: str, url: str, **kw) -> requests.Response:
        stale_auth = self.headers.get("Authorization")
        resp = self._send(method, url, **kw)
        # Only 401 means "token no longer valid" -> refresh once and retry.
        # A persistent 401 after a successful refresh is a real auth failure.
        if resp.status_code == 401:
            self._reauth(stale_auth)
            resp = self._send(method, url, **kw)
            if resp.status_code == 401:
                raise AquantaAuthError(f"{method} {url} -> 401 after re-auth")
        return resp

    @staticmethod
    def _json(resp: requests.Response):
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    def get(self, path: str, params: dict | None = None):
        """GET a /v2 path and return parsed JSON.

        An empty or non-JSON body (e.g. a captive portal) is treated as a
        connection error rather than silently returning None.
        """
        resp = self._do("GET", API_V2 + path, params=params)
        if not resp.ok:
            raise AquantaConnectionError(f"GET {path} -> {resp.status_code}")
        data = self._json(resp)
        if data is None:
            raise AquantaConnectionError(f"GET {path} returned no JSON body")
        return data

    def put(self, path: str, value: Any) -> None:
        """PUT JSON to a /v2 path."""
        resp = self._do("PUT", API_V2 + path, json=value)
        if not resp.ok:
            raise AquantaConnectionError(f"PUT {path} -> {resp.status_code}")

    def patch(self, path: str, value: Any):
        """PATCH JSON to a /v2 path and return parsed JSON if any."""
        resp = self._do("PATCH", API_V2 + path, json=value)
        if not resp.ok:
            raise AquantaConnectionError(f"PATCH {path} -> {resp.status_code}")
        return self._json(resp)

    def delete(self, path: str) -> None:
        """DELETE a /v2 path."""
        resp = self._do("DELETE", API_V2 + path)
        if not resp.ok:
            raise AquantaConnectionError(f"DELETE {path} -> {resp.status_code}")


class Aquanta:
    """Authenticated Aquanta session.

    Auth: Firebase sign-in -> idToken; GET /auth?idtoken= -> {apiKey};
    then Authorization: Bearer <apiKey> on all /v2 calls.
    """

    def __init__(self, email: str, password: str, timeout: int = 10) -> None:
        """Authenticate and prepare the session."""
        self._email = email
        self._password = password
        self._timeout = timeout
        self._session = requests.Session()
        self._refresh_token: str | None = None
        self._lock = threading.Lock()
        self._helper = AquantaHelper(self._session, timeout, self._reauth)
        self._devices: dict[int, AquantaDevice] | None = None
        try:
            self._authenticate()
        except Exception:
            # Don't leak the session if the initial login fails.
            self._session.close()
            raise

    # --- auth ---

    def _post(self, url: str, **kw) -> requests.Response:
        try:
            return self._session.post(
                url, params={"key": FIREBASE_WEB_API_KEY}, timeout=self._timeout, **kw
            )
        except requests.RequestException:
            raise AquantaConnectionError("Firebase request failed") from None

    def _firebase_sign_in(self) -> str:
        resp = self._post(
            IDENTITY_TOOLKIT,
            json={
                "email": self._email,
                "password": self._password,
                "returnSecureToken": True,
            },
        )
        if not resp.ok:
            body = resp.text or ""
            if resp.status_code in (400, 401, 403) and any(
                m in body for m in _AUTH_ERROR_MARKERS
            ):
                raise AquantaAuthError("Invalid Aquanta credentials")
            raise AquantaConnectionError(f"Firebase sign-in -> {resp.status_code}")
        try:
            data = resp.json()
            self._refresh_token = data["refreshToken"]
            return data["idToken"]
        except (ValueError, KeyError, TypeError) as err:
            raise AquantaConnectionError("Malformed Firebase sign-in response") from err

    def _firebase_refresh(self) -> str:
        if not self._refresh_token:
            return self._firebase_sign_in()
        resp = self._post(
            SECURE_TOKEN,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
        )
        if not resp.ok:
            # Only a rejected refresh token warrants a full re-login; a 5xx/429
            # is transient and should surface as a connection error.
            if resp.status_code in (400, 401):
                return self._firebase_sign_in()
            raise AquantaConnectionError(f"token refresh -> {resp.status_code}")
        try:
            data = resp.json()
            self._refresh_token = data["refresh_token"]
            return data["id_token"]
        except (ValueError, KeyError, TypeError) as err:
            raise AquantaConnectionError("Malformed token refresh response") from err

    def _exchange_key(self, id_token: str) -> None:
        try:
            resp = self._session.get(
                API_ROOT + "/auth",
                params={"idtoken": id_token},
                timeout=self._timeout,
            )
        except requests.RequestException:
            raise AquantaConnectionError("/auth request failed") from None
        if resp.status_code == 401:
            raise AquantaAuthError("Aquanta rejected the Firebase token")
        if not resp.ok:
            raise AquantaConnectionError(f"/auth -> {resp.status_code}")
        try:
            api_key = resp.json()["apiKey"]
        except (ValueError, KeyError, TypeError) as err:
            raise AquantaConnectionError("Malformed /auth response") from err
        self._helper.headers = {"Authorization": f"Bearer {api_key}"}

    def _authenticate(self) -> None:
        self._exchange_key(self._firebase_sign_in())

    def _reauth(self, stale_auth: str | None) -> None:
        # Double-checked under a lock so concurrent 401s (a poll overlapping a
        # user write) only refresh once.
        with self._lock:
            if self._helper.headers.get("Authorization") != stale_auth:
                return  # another thread already refreshed
            self._exchange_key(self._firebase_refresh())

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    # --- devices (pip-compatible) ---

    def devices(self):
        """Return a mapping of device id -> AquantaDevice (cached)."""
        if self._devices is None:
            data = self.get_devices_raw()
            if not isinstance(data, list):
                raise AquantaConnectionError("Unexpected /devices response")
            self._devices = {
                d["id"]: AquantaDevice(self._helper, d["id"])
                for d in data
                if isinstance(d, dict) and "id" in d
            }
        return self._devices

    def get_devices_raw(self):
        """Return the raw /devices list payload."""
        return self._helper.get("/devices", params={"inlineAddress": "true"})

    def __len__(self):
        """Return the number of devices on the account."""
        return len(self.devices())

    def __contains__(self, key):
        """Return whether a device id is present."""
        return key in self.devices()

    def __iter__(self):
        """Iterate (id, AquantaDevice) pairs."""
        return iter(self.devices().items())

    def __getitem__(self, key):
        """Return the AquantaDevice for a device id."""
        return self.devices()[key]


class AquantaDevice:
    """One Aquanta device."""

    def __init__(self, helper: AquantaHelper, device_id: int) -> None:
        """Bind to a device id through the shared helper."""
        self._helper = helper
        self._id = device_id

    def _p(self, name: str) -> str:
        return f"/devices/{self._id}/{name}"

    @property
    def water(self):
        """Return the device water payload (temperature, availability)."""
        return self._helper.get(self._p("water"))

    @property
    def infocenter(self):
        """Return the device infocenter payload (mode, records, title)."""
        return self._helper.get(self._p("infocenter"))

    @property
    def advanced(self):
        """Return the device advanced payload (mode flags, setPoint)."""
        return self._helper.get(self._p("advanced"))

    @property
    def timer(self):
        """Return the device timer configuration."""
        return self._helper.get(self._p("timer"))

    @timer.setter
    def timer(self, value):
        """Set the device timer configuration."""
        self._helper.put(self._p("timer"), value)

    def set_boost(self, start: str, end: str) -> None:
        """Enable boost between two ISO-8601 UTC timestamps."""
        self._helper.put(self._p("boost"), {"start": start, "end": end})

    def delete_boost(self) -> None:
        """Clear the boost window."""
        self._helper.delete(self._p("boost"))

    def set_away(self, start: str, end: str) -> None:
        """Enable away between two ISO-8601 UTC timestamps."""
        self._helper.put(self._p("away"), {"start": start, "end": end})

    def delete_away(self) -> None:
        """Clear the away window."""
        self._helper.delete(self._p("away"))

    def patch_advanced(self, fields: dict[str, Any]):
        """Batch-PATCH advanced fields (PATCH /v2/devices/advanced)."""
        body = [
            {"id": self._id, "patch": {"op": "replace", "path": k, "value": v}}
            for k, v in fields.items()
        ]
        return self._helper.patch("/devices/advanced", body)

    def set_setpoint(self, value: int):
        """Set the thermostat target in degC (10-110)."""
        v = int(round(value))
        if not (SETPOINT_MIN <= v <= SETPOINT_MAX):
            raise ValueError(f"setpoint {v} out of range {SETPOINT_MIN}-{SETPOINT_MAX}")
        return self.patch_advanced({"setPoint": v})

    def set_mode(self, mode: str):
        """Select one mode ('thermostat'|'timer'|'tou'|'intelligence') or 'off'."""
        if mode == "off":
            return self.patch_advanced({"controlEnabled": False})
        if mode not in MODE_FIELDS:
            raise ValueError(f"unknown mode '{mode}'")
        fields = {flag: (name == mode) for name, flag in MODE_FIELDS.items()}
        fields["controlEnabled"] = True
        return self.patch_advanced(fields)
