from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apis.screening_api import ScreeningApi
from core.assertions import assert_http_ok, is_business_success, safe_json
from core.auth import TokenManager
from core.http import APIClient
from core.logger import log
from core.settings import Settings
from core.utils.answers import build_submit_payload, summarize_paper
from core.utils.datasets import user_label


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
        return task_refs

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
        return {
            'paper_task_id': task.paper_task_id,
            'task_id': task.paper_task_id,
            'task_user_id': task.task_user_id,
            'paper_summary': summarize_paper(paper),
            'request_payload': payload,
            'response_payload': response_payload if response_payload is not None else response.text[:1000],
            'status_code': response.status_code,
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
        for index, account in enumerate(accounts):
            self.set_account(account)
            label = user_label(account)
            log.info('开始处理账号: %s', label)
            token = self.ensure_login(account)
            if not token:
                summary['login_failed'].append(label)
                continue
            tasks = self.list_task_refs(statuses=statuses)
            if not tasks:
                summary['no_task_accounts'].append(label)
                continue
            for task_index, task in enumerate(tasks):
                task_seed = None if seed is None else seed + index * 1000 + task_index
                result = self.submit_task(task, seed=task_seed, mode=mode)
                summary['results'].append({'account': label, **result})
                if result['success']:
                    summary['submitted'] += 1
                else:
                    summary['submit_failures'].append({'account': label, **result})
        if not allow_empty_submit:
            assert summary['submitted'] > 0, f'批量执行没有成功提交: {summary}'
        assert not summary['login_failed'], f'存在登录失败账号: {summary["login_failed"]}'
        assert not summary['submit_failures'], f'存在提交失败任务: {summary["submit_failures"]}'
        return summary