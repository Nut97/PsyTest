from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import requests

from apis.auth_api import AuthApi
from core.logger import log
from core.settings import Settings
from core.utils.datasets import user_label


def _short_text(value: Any, limit: int = 120) -> str:
    text = str(value or '').replace('\r', ' ').replace('\n', ' ').strip()
    if not text:
        return '-'
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + '...'


def _result_meta(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        return '-', '-'
    code = payload.get('code')
    msg = payload.get('msg') or payload.get('message')
    code_text = str(code) if code not in (None, '') else '-'
    msg_text = _short_text(msg)
    return code_text, msg_text


@dataclass
class CachedToken:
    token: str
    login_data: dict[str, Any]
    expires_at: float | None


class TokenManager:
    def __init__(self, *, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.api = AuthApi(settings=settings, session=session)
        self._cache: dict[tuple[str, str], CachedToken] = {}

    @staticmethod
    def username_of(account: dict[str, Any] | None) -> str | None:
        if not account:
            return None
        return (
            account.get('username')
            or account.get('studentNum')
            or account.get('account')
            or account.get('userName')
        )

    def _cache_key(self, account: dict[str, Any]) -> tuple[str, str] | None:
        username = self.username_of(account)
        if not username:
            return None
        return (self.settings.base_url, str(username))

    def _is_valid(self, cached: CachedToken) -> bool:
        if not cached.token:
            return False
        if cached.expires_at is None:
            return True
        return time.time() < cached.expires_at - 60

    def get_login_data(self, account: dict[str, Any] | None, *, force_refresh: bool = False) -> dict[str, Any] | None:
        if self.settings.auth_token:
            return {'access_token': self.settings.auth_token, 'token_type': 'bearer'}
        if not account:
            return None
        label = user_label(account)
        username = self.username_of(account) or '-'
        key = self._cache_key(account)
        if key and not force_refresh:
            cached = self._cache.get(key)
            if cached and self._is_valid(cached):
                return cached.login_data

        log.info('[%s] REQ POST %s username=%s', label, self.settings.auth_path, username)
        response = self.api.login(account)
        if response.status_code != 200:
            log.error(
                '[%s] RES POST %s -> http=%s success=False code=- msg=%s',
                label,
                self.settings.auth_path,
                response.status_code,
                _short_text(response.text),
            )
            return None
        try:
            payload = response.json()
        except Exception:
            log.error(
                '[%s] RES POST %s -> http=%s success=False code=- msg=invalid-json',
                label,
                self.settings.auth_path,
                response.status_code,
            )
            return None
        result_code, result_msg = _result_meta(payload)
        login_data = (payload or {}).get('data') or {}
        token = str(login_data.get('access_token') or '')
        if not token:
            log.error(
                '[%s] RES POST %s -> http=%s success=False code=%s msg=%s',
                label,
                self.settings.auth_path,
                response.status_code,
                result_code,
                result_msg,
            )
            return None
        log.info(
            '[%s] RES POST %s -> http=%s success=True code=%s msg=%s',
            label,
            self.settings.auth_path,
            response.status_code,
            result_code,
            result_msg,
        )

        expires_in = login_data.get('expires_in')
        expires_at = None
        try:
            expires_at = time.time() + int(expires_in)
        except Exception:
            expires_at = None

        if key:
            self._cache[key] = CachedToken(token=token, login_data=login_data, expires_at=expires_at)
        return login_data

    def get_token(self, account: dict[str, Any] | None, *, force_refresh: bool = False) -> str | None:
        if self.settings.auth_token:
            return self.settings.auth_token
        login_data = self.get_login_data(account, force_refresh=force_refresh)
        if not login_data:
            return None
        token = login_data.get('access_token')
        return str(token) if token else None

    def refresh_token(self, account: dict[str, Any] | None) -> str | None:
        return self.get_token(account, force_refresh=True)

    def auth_headers(self, account: dict[str, Any] | None) -> dict[str, str]:
        token = self.get_token(account)
        if not token:
            return {}
        return {'Blade-Auth': f'bearer {token}'}
