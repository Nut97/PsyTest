from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from typing import Any

from apis.screening_api import ScreeningApi
from core.assertions import assert_http_ok, is_business_success, safe_json
from core.auth import TokenManager
from core.http import APIClient
from core.logger import log
from core.settings import Settings
from core.utils.answers import build_submit_payload, summarize_paper
from core.utils.datasets import user_label


def _short_text(value: Any, limit: int = 120) -> str:
    text = str(value or '').replace('\r', ' ').replace('\n', ' ').strip()
    if not text:
        return '-'
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + '...'


def _response_meta(payload: Any) -> tuple[Any | None, str]:
    if not isinstance(payload, dict):
        return None, '-'
    code = payload.get('code')
    message = payload.get('msg') or payload.get('message')
    return code, _short_text(message)


RECENT_TIME_FIELDS = (
    'updatedTime',
    'updateTime',
    'updatedAt',
    'modifyTime',
    'gmtModified',
    'screeningTime',
    'screeningDate',
    'screeningAt',
    'screeningDatetime',
    'createTime',
    'createdTime',
    'createdAt',
    'gmtCreate',
    'startTime',
    'startDate',
    'beginTime',
    'planTime',
    'executeTime',
    'taskTime',
)


def _parse_time_to_timestamp(value: Any) -> float | None:
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1_000_000_000_000:
            numeric = numeric / 1000.0
        return numeric

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        numeric = float(text)
        if numeric > 1_000_000_000_000:
            numeric = numeric / 1000.0
        return numeric

    iso_text = text.replace('Z', '+00:00')
    try:
        return dt.datetime.fromisoformat(iso_text).timestamp()
    except Exception:
        pass

    for fmt in (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M:%S',
        '%Y/%m/%d %H:%M',
        '%Y-%m-%d',
        '%Y/%m/%d',
    ):
        try:
            return dt.datetime.strptime(text, fmt).timestamp()
        except Exception:
            continue
    return None


@dataclass
class TaskRef:
    paper_task_id: str
    task_user_id: str
    raw: dict[str, Any]

    @property
    def task_id(self) -> str:
        """兼容旧代码的读取方式。"""
        return self.paper_task_id


class ScreeningService:
    def __init__(self, *, settings: Settings, account: dict[str, Any] | None = None) -> None:
        self.settings = settings
        self.token_manager = TokenManager(settings=settings)
        self.client = APIClient(settings=settings, token_manager=self.token_manager, account=account)
        self.api = ScreeningApi(self.client)

    def set_account(self, account: dict[str, Any] | None) -> None:
        self.client.set_account(account)

    def ensure_login(self, account: dict[str, Any] | None = None) -> str | None:
        if account is not None:
            self.set_account(account)
        return self.token_manager.get_token(self.client.account)

    def _task_timestamp(self, task: TaskRef) -> float | None:
        for field in RECENT_TIME_FIELDS:
            timestamp = _parse_time_to_timestamp(task.raw.get(field))
            if timestamp is not None:
                return timestamp
        return None

    def _pick_latest_task(self, task_refs: list[TaskRef]) -> TaskRef:
        # Prefer tasks with explicit time fields; fallback to first-in-list order.
        best_index = 0
        best_score = (0, float('-inf'), 0)
        for index, task in enumerate(task_refs):
            timestamp = self._task_timestamp(task)
            has_time = 1 if timestamp is not None else 0
            score = (has_time, timestamp if timestamp is not None else float('-inf'), -index)
            if score > best_score:
                best_index = index
                best_score = score
        return task_refs[best_index]

    def list_task_refs(self, statuses: tuple[int, ...] | list[int] | None = None) -> list[TaskRef]:
        task_refs: list[TaskRef] = []
        seen: set[tuple[str, str]] = set()
        statuses = tuple(statuses or self.settings.screening_task_statuses)
        for status in statuses:
            response = self.api.list_tasks(status=int(status))
            assert_http_ok(response)
            payload = safe_json(response)
            tasks = self.api.extract_tasks(payload)
            for task in tasks:
                paper_task_id = self.api.resolve_paper_task_id(task)
                task_user_id = self.api.resolve_task_user_id(task, fallback_paper_task_id=paper_task_id)
                if not paper_task_id or not task_user_id:
                    continue
                key = (paper_task_id, task_user_id)
                if key in seen:
                    continue
                seen.add(key)
                task_refs.append(TaskRef(paper_task_id=paper_task_id, task_user_id=task_user_id, raw=task))
        if not task_refs:
            return []
        if len(task_refs) == 1:
            return task_refs
        latest_task = self._pick_latest_task(task_refs)
        log.info(
            '[%s] multiple-plans detected: total=%s keep-latest task_id=%s task_user_id=%s',
            user_label(self.client.account),
            len(task_refs),
            latest_task.paper_task_id,
            latest_task.task_user_id,
        )
        return [latest_task]

    def fetch_paper(self, paper_task_id: str) -> dict[str, Any]:
        response = self.api.get_paper(paper_task_id)
        assert_http_ok(response)
        payload = safe_json(response)
        assert isinstance(payload, dict), f'getPaper 响应不是 JSON 对象: {response.text[:500]}'
        return payload

    def submit_task(
        self,
        task: TaskRef,
        *,
        seed: int | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        paper = self.fetch_paper(task.paper_task_id)
        payload = build_submit_payload(paper, task.task_user_id, seed=seed, mode=mode)
        response = self.api.submit_answers(payload)
        response_payload = safe_json(response)
        success = is_business_success(response, response_payload)
        business_code, business_message = _response_meta(response_payload)
        return {
            'paper_task_id': task.paper_task_id,
            'task_id': task.paper_task_id,
            'task_user_id': task.task_user_id,
            'paper_summary': summarize_paper(paper),
            'request_payload': payload,
            'response_payload': response_payload if response_payload is not None else response.text[:1000],
            'status_code': response.status_code,
            'business_code': business_code,
            'business_message': business_message,
            'success': success,
        }

    def run_smoke(
        self,
        *,
        statuses: tuple[int, ...] | list[int] | None = None,
        seed: int | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        token = self.ensure_login(self.client.account)
        assert token, f'登录失败: {user_label(self.client.account)}'
        tasks = self.list_task_refs(statuses=statuses)
        assert tasks, f'未找到可执行任务: {user_label(self.client.account)}'
        result = self.submit_task(tasks[0], seed=seed, mode=mode)
        assert result['success'], f'提交失败: {result}'
        return result

    def run_batch(
        self,
        accounts: list[dict[str, Any]],
        *,
        statuses: tuple[int, ...] | list[int] | None = None,
        seed: int | None = None,
        mode: str | None = None,
        allow_empty_submit: bool | None = None,
    ) -> dict[str, Any]:
        summary = {
            'accounts': len(accounts),
            'submitted': 0,
            'login_failed': [],
            'no_task_accounts': [],
            'submit_failures': [],
            'results': [],
        }
        allow_empty_submit = self.settings.allow_empty_submit if allow_empty_submit is None else allow_empty_submit
        resolved_statuses = tuple(statuses or self.settings.screening_task_statuses)
        for index, account in enumerate(accounts):
            self.set_account(account)
            label = user_label(account)
            log.info('========== [%s] batch-start (%s/%s) ==========', label, index + 1, len(accounts))
            token = self.ensure_login(account)
            if not token:
                summary['login_failed'].append(label)
                log.info('[%s] user-summary login=False tasks=0 submitted=0 failed=0', label)
                continue
            tasks = self.list_task_refs(statuses=resolved_statuses)
            log.info('[%s] list-tasks -> success=%s statuses=%s task_count=%s', label, bool(tasks), resolved_statuses, len(tasks))
            if not tasks:
                summary['no_task_accounts'].append(label)
                log.info('[%s] user-summary login=True tasks=0 submitted=0 failed=0', label)
                continue
            user_submitted = 0
            user_failed = 0
            for task_index, task in enumerate(tasks):
                task_seed = None if seed is None else seed + index * 1000 + task_index
                result = self.submit_task(task, seed=task_seed, mode=mode)
                summary['results'].append({'account': label, **result})
                if result['success']:
                    summary['submitted'] += 1
                    user_submitted += 1
                else:
                    summary['submit_failures'].append({'account': label, **result})
                    user_failed += 1
                log.info(
                    '[%s] submit-task -> task_id=%s task_user_id=%s success=%s http=%s code=%s msg=%s',
                    label,
                    result['task_id'],
                    result['task_user_id'],
                    result['success'],
                    result['status_code'],
                    result['business_code'] if result['business_code'] not in (None, '') else '-',
                    _short_text(result['business_message']),
                )
            log.info('[%s] user-summary login=True tasks=%s submitted=%s failed=%s', label, len(tasks), user_submitted, user_failed)
        log.info(
            'batch-summary accounts=%s submitted=%s login_failed=%s no_task=%s submit_failed=%s',
            summary['accounts'],
            summary['submitted'],
            len(summary['login_failed']),
            len(summary['no_task_accounts']),
            len(summary['submit_failures']),
        )
        if not allow_empty_submit:
            assert summary['submitted'] > 0, f'批量执行没有成功提交: {summary}'
        assert not summary['login_failed'], f'存在登录失败账号: {summary["login_failed"]}'
        assert not summary['submit_failures'], f'存在提交失败任务: {summary["submit_failures"]}'
        return summary
