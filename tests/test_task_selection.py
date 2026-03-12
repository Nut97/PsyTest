from __future__ import annotations

from core.settings import load_settings
from services.screening_service import ScreeningService


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


def test_list_task_refs_keep_latest_by_time(monkeypatch):
    settings = load_settings('test')
    service = ScreeningService(settings=settings, account={'label': 'u1', 'username': 'u1'})

    def _fake_list_tasks(*, status: int):
        if status == 1:
            payload = {'data': [{'taskId': 'old', 'taskUserId': 'old-user', 'createTime': '2024-01-01 00:00:00'}]}
        else:
            payload = {'data': [{'taskId': 'new', 'taskUserId': 'new-user', 'createTime': '2025-01-01 00:00:00'}]}
        return _FakeResponse(payload)

    monkeypatch.setattr(service.api, 'list_tasks', _fake_list_tasks)
    task_refs = service.list_task_refs(statuses=(1, 2))

    assert len(task_refs) == 1
    assert task_refs[0].paper_task_id == 'new'
    assert task_refs[0].task_user_id == 'new-user'


def test_list_task_refs_keep_first_when_no_time(monkeypatch):
    settings = load_settings('test')
    service = ScreeningService(settings=settings, account={'label': 'u2', 'username': 'u2'})

    payload = {
        'data': [
            {'taskId': 'first', 'taskUserId': 'first-user'},
            {'taskId': 'second', 'taskUserId': 'second-user'},
        ]
    }

    monkeypatch.setattr(service.api, 'list_tasks', lambda *, status: _FakeResponse(payload))
    task_refs = service.list_task_refs(statuses=(1,))

    assert len(task_refs) == 1
    assert task_refs[0].paper_task_id == 'first'
    assert task_refs[0].task_user_id == 'first-user'
