from __future__ import annotations

from pathlib import Path
import json
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _ensure_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def normalize_account(account: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(account)
    if 'username' not in normalized and 'studentNum' in normalized:
        normalized['username'] = normalized['studentNum']
    if 'label' not in normalized:
        normalized['label'] = normalized.get('数据集名称') or normalized.get('studentNum') or normalized.get('username')
    return normalized


def load_accounts(path: str | Path = 'data/account.json') -> list[dict[str, Any]]:
    target = resolve_path(path)
    if not target.exists():
        return []
    payload = json.loads(target.read_text(encoding='utf-8'))
    return [normalize_account(item) for item in _ensure_list(payload)]


def user_label(account: dict[str, Any] | None) -> str:
    if not account:
        return 'unknown-user'
    return str(
        account.get('label')
        or account.get('数据集名称')
        or account.get('username')
        or account.get('studentNum')
        or 'unknown-user'
    )