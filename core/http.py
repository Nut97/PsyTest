from __future__ import annotations

import json
import time
from typing import Any, Mapping

import requests

from core.logger import log
from core.settings import Settings

try:
    import allure  # type: ignore
    HAS_ALLURE = True
except Exception:  # pragma: no cover - optional
    HAS_ALLURE = False


SENSITIVE_HEADERS = {'Authorization', 'Blade-Auth'}


def mask_secret(value: str | None) -> str | None:
    if value is None:
        return value
    if len(value) <= 8:
        return '****'
    return f'{value[:4]}****{value[-4:]}'


def sanitize_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    safe = dict(headers or {})
    for key in list(safe.keys()):
        if key in SENSITIVE_HEADERS:
            safe[key] = mask_secret(str(safe[key])) or '****'
    return safe


class APIClient:
    def __init__(
        self,
        *,
        settings: Settings,
        token_manager=None,
        account: dict[str, Any] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.settings = settings
        self.token_manager = token_manager
        self.account = account
        self.session = session or requests.Session()

    def set_account(self, account: dict[str, Any] | None) -> None:
        self.account = account

    def _build_headers(
        self,
        *,
        headers: Mapping[str, str] | None = None,
        use_auth: bool = True,
        json_body: bool = False,
        form_body: bool = False,
    ) -> dict[str, str]:
        merged = dict(self.settings.default_headers)
        if use_auth and self.token_manager and self.account:
            merged.update(self.token_manager.auth_headers(self.account))
        if json_body:
            merged['Content-Type'] = 'application/json'
        elif form_body:
            merged['Content-Type'] = 'application/x-www-form-urlencoded'
        if headers:
            merged.update(headers)
        return merged

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        use_auth: bool = True,
        retry_on_401: bool = True,
        timeout: int | None = None,
    ) -> requests.Response:
        method = method.upper()
        url = self.settings.build_url(path)
        request_headers = self._build_headers(
            headers=headers,
            use_auth=use_auth,
            json_body=json_body is not None,
            form_body=data is not None and json_body is None,
        )
        timeout = timeout or self.settings.timeout_seconds

        started = time.perf_counter()
        response = self.session.request(
            method,
            url,
            params=params,
            json=json_body,
            data=data,
            headers=request_headers,
            timeout=timeout,
        )
        cost_ms = int((time.perf_counter() - started) * 1000)

        if response.status_code == 401 and retry_on_401 and use_auth and self.token_manager and self.account:
            refreshed = self.token_manager.refresh_token(self.account)
            if refreshed:
                request_headers = self._build_headers(
                    headers=headers,
                    use_auth=use_auth,
                    json_body=json_body is not None,
                    form_body=data is not None and json_body is None,
                )
                response = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    data=data,
                    headers=request_headers,
                    timeout=timeout,
                )
                cost_ms = int((time.perf_counter() - started) * 1000)

        log.info('%s %s -> %s (%sms)', method, path, response.status_code, cost_ms)
        log.debug('headers=%s params=%s body=%s', sanitize_headers(request_headers), params, json_body or data)

        if HAS_ALLURE:
            try:
                allure.attach(
                    json.dumps(
                        {
                            'method': method,
                            'url': url,
                            'headers': sanitize_headers(request_headers),
                            'params': dict(params or {}),
                            'json': json_body,
                            'data': data,
                            'status_code': response.status_code,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    name=f'{method} {path} request',
                    attachment_type=allure.attachment_type.JSON,
                )
                try:
                    body = response.json()
                    allure.attach(
                        json.dumps(body, ensure_ascii=False, indent=2),
                        name=f'{method} {path} response',
                        attachment_type=allure.attachment_type.JSON,
                    )
                except Exception:
                    allure.attach(
                        response.text[:5000],
                        name=f'{method} {path} response',
                        attachment_type=allure.attachment_type.TEXT,
                    )
            except Exception:
                pass

        return response