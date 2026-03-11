from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_DIR = PROJECT_ROOT / 'envs'
DEFAULT_ENV = 'test'
DEFAULT_BASE_URLS = {
    'dev': 'http://192.168.110.14:8080',
    'test': 'http://society-platform-test.scqtkj.com',
    'pre': 'https://society-platform-proe.scqtkj.com',
}


def _parse_int(value: object, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _parse_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if text in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return default


def _parse_statuses(value: object, default: tuple[int, ...] = (1,)) -> tuple[int, ...]:
    if value is None:
        return default
    out: list[int] = []
    for item in str(value).split(','):
        item = item.strip()
        if item.isdigit():
            out.append(int(item))
    return tuple(out) or default


@dataclass(frozen=True)
class Settings:
    env: str
    base_url: str
    timeout_seconds: int
    basic_auth: str
    tenant_id: str
    auth_token: str
    blade_request_usercode: str
    blade_requested_with: str
    auth_path: str
    screening_task_list_path: str
    screening_get_paper_path: str
    screening_submit_path: str
    screening_task_statuses: tuple[int, ...]
    allow_empty_submit: bool

    @property
    def default_headers(self) -> dict[str, str]:
        return {
            'Authorization': self.basic_auth,
            'Tenant-Id': self.tenant_id,
            'blade-request-usercode': self.blade_request_usercode,
            'blade-requested-with': self.blade_requested_with,
        }

    def build_url(self, path: str) -> str:
        if path.startswith('http://') or path.startswith('https://'):
            return path
        if not path.startswith('/'):
            path = '/' + path
        return self.base_url.rstrip('/') + path

    def format_get_paper_path(self, paper_task_id: str | int) -> str:
        template = self.screening_get_paper_path
        value = str(paper_task_id)
        for placeholder in ('{task_id}', '{paper_task_id}', '{taskId}'):
            if placeholder in template:
                return template.replace(placeholder, value)
        return template.rstrip('/') + f'/{value}'


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def load_settings(env: str = DEFAULT_ENV, *, overrides: dict[str, str] | None = None) -> Settings:
    env = env or DEFAULT_ENV
    env_file = ENV_DIR / f'{env}.env'
    file_values = _read_env_file(env_file)

    values: dict[str, object] = {}
    values.update(file_values)
    values.update({k: v for k, v in os.environ.items() if k in {
        'BASE_URL', 'TIMEOUT_SECONDS', 'BASIC_AUTH', 'TENANT_ID', 'AUTH_TOKEN',
        'BLADE_REQUEST_USERCODE', 'BLADE_REQUESTED_WITH', 'AUTH_PATH',
        'SCREENING_TASK_LIST_PATH', 'SCREENING_GET_PAPER_PATH', 'SCREENING_SUBMIT_PATH',
        'SCREENING_TASK_STATUSES', 'ALLOW_EMPTY_SUBMIT',
    }})
    if overrides:
        values.update(overrides)

    base_url = str(values.get('BASE_URL') or DEFAULT_BASE_URLS.get(env, DEFAULT_BASE_URLS[DEFAULT_ENV]))
    return Settings(
        env=env,
        base_url=base_url,
        timeout_seconds=_parse_int(values.get('TIMEOUT_SECONDS'), 30),
        basic_auth=str(values.get('BASIC_AUTH') or 'Basic c2FiZXIzOnNhYmVyM19zZWNyZXQ='),
        tenant_id=str(values.get('TENANT_ID') or '000000'),
        auth_token=str(values.get('AUTH_TOKEN') or ''),
        blade_request_usercode=str(values.get('BLADE_REQUEST_USERCODE') or 'screening'),
        blade_requested_with=str(values.get('BLADE_REQUESTED_WITH') or 'BladeHttpRequest'),
        auth_path=str(values.get('AUTH_PATH') or '/api/blade-auth/oauth/token/login/userCode/internalUse'),
        screening_task_list_path=str(values.get('SCREENING_TASK_LIST_PATH') or '/api/qt-scale/app/screening/task/page'),
        screening_get_paper_path=str(values.get('SCREENING_GET_PAPER_PATH') or '/api/qt-scale/app/screening/getPaper/{task_id}'),
        screening_submit_path=str(values.get('SCREENING_SUBMIT_PATH') or '/api/qt-scale/app/screening/answerSubmit'),
        screening_task_statuses=_parse_statuses(values.get('SCREENING_TASK_STATUSES')),
        allow_empty_submit=_parse_bool(values.get('ALLOW_EMPTY_SUBMIT'), False),
    )