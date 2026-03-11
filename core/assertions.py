from __future__ import annotations

from typing import Any


SUCCESS_CODES = {0, 200}
SUCCESS_TEXT = ('成功', 'success', '提交完成', 'ok')


def short_body(payload: Any, limit: int = 500) -> str:
    text = str(payload)
    return text[:limit]


def safe_json(response) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def is_business_success(response, payload: Any | None = None) -> bool:
    if response.status_code not in (200, 201, 202):
        return False
    payload = payload if payload is not None else safe_json(response)
    if payload is None:
        return True
    if isinstance(payload, dict):
        if payload.get('success') is True:
            return True
        code = payload.get('code')
        if code in SUCCESS_CODES:
            return True
        message = ' '.join(str(payload.get(key, '')) for key in ('msg', 'message'))
        lowered = message.lower()
        return any(token.lower() in lowered for token in SUCCESS_TEXT)
    return True


def assert_http_ok(response) -> None:
    assert response.status_code in (200, 201, 202), f'HTTP {response.status_code}: {response.text[:500]}'


def assert_business_ok(response, payload: Any | None = None) -> Any:
    payload = payload if payload is not None else safe_json(response)
    assert is_business_success(response, payload), f'业务失败: status={response.status_code}, body={short_body(payload or response.text)}'
    return payload