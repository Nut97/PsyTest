from __future__ import annotations

import json
import time
from typing import Any, Mapping

import requests

from core.assertions import is_business_success
from core.logger import log
from core.settings import Settings
from core.utils.datasets import user_label

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


def _short_text(value: Any, limit: int = 120) -> str:
    text = str(value or '').replace('\r', ' ').replace('\n', ' ').strip()
    if not text:
        return '-'
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + '...'


def _compact_payload(value: Any, limit: int = 180) -> str:
    if value in (None, '', {}, []):
        return '-'
    try:
        text = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    except Exception:
        text = str(value)
    return _short_text(text, limit=limit)


def _extract_result_meta(payload: Any, response_text: str) -> tuple[str, str]:
    if isinstance(payload, dict):
        code = payload.get('code')
        message = payload.get('msg') or payload.get('message')
        code_text = str(code) if code not in (None, '') else '-'
        if message not in (None, ''):
            return code_text, _short_text(message, limit=180)
        return code_text, _compact_payload(payload, limit=180)
    if payload is not None:
        return '-', _compact_payload(payload, limit=180)
    return '-', _short_text(response_text, limit=180)


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
        account_label = user_label(self.account)
        request_headers = self._build_headers(
            headers=headers,
            use_auth=use_auth,
            json_body=json_body is not None,
            form_body=data is not None and json_body is None,
        )
        timeout = timeout or self.settings.timeout_seconds
        request_body = json_body if json_body is not None else data

        log.info(
            '[%s] REQ %s %s params=%s body=%s',
            account_label,
            method,
            path,
            _compact_payload(params, limit=140),
            _compact_payload(request_body, limit=180),
        )

        started = time.perf_counter()
        try:
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
        except requests.RequestException as exc:
            cost_ms = int((time.perf_counter() - started) * 1000)
            log.error(
                '[%s] RES %s %s -> http=- success=False code=- msg=%s (%sms)',
                account_label,
                method,
                path,
                _short_text(exc),
                cost_ms,
            )
            raise

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

        response_payload: Any | None = None
        try:
            response_payload = response.json()
        except Exception:
            response_payload = None
        success = is_business_success(response, response_payload)
        result_code, result_message = _extract_result_meta(response_payload, response.text[:1000])

        log.info(
            '[%s] RES %s %s -> http=%s success=%s code=%s msg=%s (%sms)',
            account_label,
            method,
            path,
            response.status_code,
            success,
            result_code,
            result_message,
            cost_ms,
        )
        log.debug(
            '[%s] headers=%s params=%s body=%s',
            account_label,
            sanitize_headers(request_headers),
            params,
            json_body or data,
        )

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
                if response_payload is not None:
                    allure.attach(
                        json.dumps(response_payload, ensure_ascii=False, indent=2),
                        name=f'{method} {path} response',
                        attachment_type=allure.attachment_type.JSON,
                    )
                else:
                    allure.attach(
                        response.text[:5000],
                        name=f'{method} {path} response',
                        attachment_type=allure.attachment_type.TEXT,
                    )
            except Exception:
                pass

        return response
