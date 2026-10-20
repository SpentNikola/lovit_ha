"""Async client for the Lovit personal cabinet (https://lk.lovit.ru).

The personal cabinet is a Laravel application protected by a classic
session cookie.  The flow implemented here is the very same one a browser
performs:

1. ``GET /login`` and extract the hidden ``_token`` (CSRF) field;
2. ``POST /login`` with ``_token``, ``login`` and ``password`` -- Laravel
   answers with a redirect and sets an authenticated session cookie;
3. ``GET /api/user/info`` returning the JSON document with the balance.

The session cookie is a sliding one, so every successful request extends
its lifetime.  When the session finally expires the API answers with a
redirect to ``/login``; in that case the client signs in again.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import BASE_URL, LOGIN_PATH, USER_INFO_PATH

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

#: HTTP statuses meaning "you are not (or no longer) authenticated".
_AUTH_HTTP_STATUSES = frozenset({401, 403, 419})
#: HTTP statuses used by Laravel as "redirect to the login page".
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

_INPUT_TOKEN_RE = re.compile(r"""<input[^>]*name=["']_token["'][^>]*>""", re.IGNORECASE)
_META_TOKEN_RE = re.compile(
    r"""<meta[^>]*name=["']csrf-token["'][^>]*>""", re.IGNORECASE
)
_VALUE_RE = re.compile(r"""value=["']([^"']+)["']""", re.IGNORECASE)
_CONTENT_RE = re.compile(r"""content=["']([^"']+)["']""", re.IGNORECASE)


class LovitError(Exception):
    """Base error raised by the Lovit API client."""


class LovitAuthError(LovitError):
    """Raised when lk.lovit.ru rejects the login or the password."""


class LovitConnectionError(LovitError):
    """Raised when lk.lovit.ru cannot be reached or answers with an error."""


def _as_float(value: Any) -> float | None:
    """Convert an API value to float, returning ``None`` when impossible."""
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Convert an API value to int, returning ``None`` when impossible."""
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    """Convert an API value to a non-empty string."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_csrf_token(html: str) -> str | None:
    """Extract the CSRF token from the login page markup."""
    for pattern, value_pattern in (
        (_INPUT_TOKEN_RE, _VALUE_RE),
        (_META_TOKEN_RE, _CONTENT_RE),
    ):
        tag = pattern.search(html)
        if tag is None:
            continue
        value = value_pattern.search(tag.group(0))
        if value is not None:
            return value.group(1)
    return None


_SENSITIVE_KEYS = frozenset({"password", "passwd", "pwd", "token", "hash"})


def _strip_sensitive(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the payload without credentials."""
    return {
        key: value
        for key, value in payload.items()
        if key.lower() not in _SENSITIVE_KEYS
    }


@dataclass(slots=True)
class LovitSubscription:
    """One subscription (service) attached to the account."""

    sub_id: str
    mobile_no: str | None
    status: str | None
    desk: str | None
    type: str | None
    tariff_id: int | None
    started: str | None
    raw: dict[str, Any]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> LovitSubscription:
        """Build a subscription from the API payload."""
        return cls(
            sub_id=str(data.get("sub_id") or ""),
            mobile_no=_as_str(data.get("mobile_no")),
            status=_as_str(data.get("status")),
            desk=_as_str(data.get("desk")),
            type=_as_str(data.get("type")),
            tariff_id=_as_int(data.get("tariff_id")),
            started=_as_str(data.get("sub_tarif_started")),
            raw=dict(data),
        )


@dataclass(slots=True)
class LovitAccountData:
    """Account snapshot returned by ``/api/user/info``."""

    login: str | None
    balance: float | None
    payment: float | None
    days_to_off: int | None
    ip: str | None
    subscriptions: list[LovitSubscription]
    raw: dict[str, Any]

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> LovitAccountData:
        """Build an account snapshot from the API payload."""
        subscriptions = [
            LovitSubscription.from_api(item)
            for item in payload.get("subs") or []
            if isinstance(item, dict)
        ]
        return cls(
            login=_as_str(payload.get("login")),
            balance=_as_float(payload.get("balance")),
            payment=_as_float(payload.get("payment")),
            days_to_off=_as_int(payload.get("days_to_off")),
            ip=_as_str(payload.get("ip")),
            subscriptions=subscriptions,
            raw=_strip_sensitive(payload),
        )


class LovitClient:
    """Minimal client for the Lovit personal cabinet."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        login: str,
        password: str,
    ) -> None:
        """Initialise the client with an aiohttp session and credentials."""
        self._session = session
        self._login = login
        self._password = password
        self._data: LovitAccountData | None = None
        self._lock = asyncio.Lock()

    @property
    def data(self) -> LovitAccountData | None:
        """Return the last successfully fetched account snapshot."""
        return self._data

    async def async_close(self) -> None:
        """Close the underlying HTTP session."""
        await self._session.close()

    async def async_get_data(self) -> LovitAccountData:
        """Return fresh account data, signing in again when needed."""
        if self._data is None:
            return await self.async_login()

        try:
            payload = await self._async_fetch_user_info()
        except LovitAuthError:
            _LOGGER.debug("Lovit session is no longer valid, signing in again")
            return await self.async_login()

        if payload is None:
            _LOGGER.debug("Lovit API asked for authentication, signing in again")
            return await self.async_login()

        self._data = LovitAccountData.from_api(payload)
        return self._data

    async def async_login(self) -> LovitAccountData:
        """Sign in and return the account snapshot."""
        async with self._lock:
            await self._async_perform_login()
            payload = await self._async_fetch_user_info()
            if payload is None:
                raise LovitAuthError("lk.lovit.ru rejected the login or password")

            self._data = LovitAccountData.from_api(payload)
            _LOGGER.debug("Authenticated at lk.lovit.ru as %s", self._data.login)
            return self._data

    async def _async_perform_login(self) -> None:
        """Post the login form with a fresh CSRF token."""
        form = {
            "_token": await self._async_fetch_csrf_token(),
            "login": self._login,
            "password": self._password,
        }
        headers = {
            **_HEADERS,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9," "*/*;q=0.8"
            ),
            "Origin": BASE_URL,
            "Referer": BASE_URL + LOGIN_PATH,
        }

        for attempt in range(2):
            try:
                async with self._session.post(
                    BASE_URL + LOGIN_PATH,
                    data=form,
                    headers=headers,
                    allow_redirects=False,
                    timeout=REQUEST_TIMEOUT,
                ) as response:
                    await response.read()

                    if response.status == 419 and attempt == 0:
                        # The CSRF token expired between GET and POST.
                        _LOGGER.debug("Refreshing expired CSRF token")
                        form["_token"] = await self._async_fetch_csrf_token()
                        continue

                    if response.status >= 500:
                        raise LovitConnectionError(
                            f"lk.lovit.ru returned HTTP {response.status}"
                        )
            except (aiohttp.ClientError, TimeoutError) as err:
                raise LovitConnectionError(
                    f"Cannot sign in to lk.lovit.ru: {err}"
                ) from err
            return

    async def _async_fetch_csrf_token(self) -> str:
        """Load the login page and extract the CSRF token."""
        try:
            async with self._session.get(
                BASE_URL + LOGIN_PATH,
                headers=_HEADERS,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                response.raise_for_status()
                html = await response.text()
        except aiohttp.ClientResponseError as err:
            raise LovitConnectionError(
                f"lk.lovit.ru returned HTTP {err.status} for {LOGIN_PATH}"
            ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LovitConnectionError(f"Cannot reach lk.lovit.ru: {err}") from err

        token = _extract_csrf_token(html)
        if token is None:
            raise LovitError("Cannot find the CSRF token on the login page")
        return token

    async def _async_fetch_user_info(self) -> dict[str, Any] | None:
        """Fetch ``/api/user/info``; return ``None`` when not authenticated."""
        headers = {
            **_HEADERS,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": BASE_URL + "/",
        }

        try:
            async with self._session.get(
                BASE_URL + USER_INFO_PATH,
                headers=headers,
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if (
                    response.status in _REDIRECT_STATUSES
                    or response.status in _AUTH_HTTP_STATUSES
                ):
                    return None
                if response.status >= 400:
                    raise LovitConnectionError(
                        f"lk.lovit.ru returned HTTP {response.status} "
                        f"for {USER_INFO_PATH}"
                    )
                content_type = response.headers.get("Content-Type", "")
                body = await response.text()
        except aiohttp.ClientResponseError as err:
            if err.status in _AUTH_HTTP_STATUSES:
                return None
            raise LovitConnectionError(
                f"lk.lovit.ru returned HTTP {err.status} for {USER_INFO_PATH}"
            ) from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise LovitConnectionError(f"Cannot reach lk.lovit.ru: {err}") from err

        if "json" not in content_type.lower():
            # A login page served with HTTP 200 instead of a redirect.
            if "_token" in body or "auth_form" in body:
                return None
            raise LovitError(f"Unexpected non-JSON response from {USER_INFO_PATH}")

        try:
            payload = json.loads(body)
        except ValueError as err:
            raise LovitError(
                f"Cannot decode the response from {USER_INFO_PATH}"
            ) from err

        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise LovitError(f"Unexpected API response: {str(payload)[:200]}")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise LovitError("The API response does not contain account data")
        return data
