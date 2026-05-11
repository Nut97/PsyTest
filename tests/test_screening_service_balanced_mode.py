from __future__ import annotations

import math
import random
from collections import Counter
from typing import Any

from core.utils.datasets import user_label
from services.screening_service import TaskRef


def _build_accounts(total: int) -> list[dict[str, Any]]:
    return [
        {
            'username': f'user-{index}',
            'label': f'user-{index}',
        }
        for index in range(total)
    ]


def _install_batch_stubs(monkeypatch, service, *, submitted_calls: list[dict[str, Any]]) -> None:
    def fake_ensure_login(account=None):
        return f"token-{user_label(account)}"

    def fake_list_task_refs(*, statuses=None):
        account = service.client.account
        label = user_label(account)
        return [TaskRef(paper_task_id=f'paper-{label}', task_user_id=f'task-user-{label}', raw={'label': label})]

    def fake_submit_task(task, *, seed=None, mode=None):
        account = service.client.account
        label = user_label(account)
        submitted_calls.append(
            {
                'account': label,
                'paper_task_id': task.paper_task_id,
                'task_user_id': task.task_user_id,
                'seed': seed,
                'mode': mode,
            }
        )
        return {
            'paper_task_id': task.paper_task_id,
            'task_id': task.paper_task_id,
            'task_user_id': task.task_user_id,
            'paper_summary': {'subjects': 1},
            'request_payload': {'mode': mode, 'seed': seed},
            'response_payload': {'code': 200},
            'status_code': 200,
            'business_code': 200,
            'business_message': 'ok',
            'success': True,
        }

    monkeypatch.setattr(service, 'ensure_login', fake_ensure_login)
    monkeypatch.setattr(service, 'list_task_refs', fake_list_task_refs)
    monkeypatch.setattr(service, 'submit_task', fake_submit_task)


def _expected_balanced_assignment_by_index(total: int, seed: int | None) -> dict[int, str]:
    indices = list(range(total))
    random.Random(seed).shuffle(indices)

    random_group = math.ceil(total / 2)
    balanced_group = total // 2
    base = balanced_group // 3
    remainder = balanced_group % 3
    distribution = {'low': base, 'middle': base, 'high': base}
    for key in ('low', 'middle', 'high')[:remainder]:
        distribution[key] += 1

    assignment_by_index: dict[int, str] = {}
    cursor = 0
    for index in indices[cursor : cursor + random_group]:
        assignment_by_index[index] = 'random'
    cursor += random_group

    for mode in ('low', 'middle', 'high'):
        group_size = distribution[mode]
        for index in indices[cursor : cursor + group_size]:
            assignment_by_index[index] = mode
        cursor += group_size

    return assignment_by_index


def _assert_summary_keys(summary: dict[str, Any], *keys: str) -> None:
    for key in keys:
        assert key in summary


def test_run_batch_defaults_to_balanced_mode_and_dispatches_plan_assignments(screening_service_factory, monkeypatch):
    service = screening_service_factory()
    accounts = _build_accounts(11)
    submitted_calls: list[dict[str, Any]] = []
    _install_batch_stubs(monkeypatch, service, submitted_calls=submitted_calls)

    summary = service.run_batch(accounts, seed=7, mode=None)

    expected_modes_by_account = {
        user_label(account): _expected_balanced_assignment_by_index(total=11, seed=7)[index]
        for index, account in enumerate(accounts)
    }

    _assert_summary_keys(summary, 'resolved_mode', 'balanced_plan')
    assert summary['resolved_mode'] == 'balanced'
    assert summary['balanced_plan']['mode_distribution'] == {'random': 6, 'low': 2, 'middle': 2, 'high': 1}
    assert summary['balanced_plan']['seed_used'] == 7
    assert {call['account']: call['mode'] for call in submitted_calls} == expected_modes_by_account
    assert len(submitted_calls) == 11
    assert all(call['mode'] != 'balanced' for call in submitted_calls)


def test_run_batch_with_default_mode_falls_back_to_random_when_accounts_are_insufficient(screening_service_factory, monkeypatch):
    service = screening_service_factory()
    accounts = _build_accounts(10)
    submitted_calls: list[dict[str, Any]] = []
    _install_batch_stubs(monkeypatch, service, submitted_calls=submitted_calls)

    summary = service.run_batch(accounts, seed=7, mode=None)

    _assert_summary_keys(summary, 'resolved_mode', 'balanced_plan')
    assert summary['resolved_mode'] == 'balanced'
    assert summary['balanced_plan']['fallback_reason'] == 'insufficient_accounts'
    assert len(submitted_calls) == 10
    assert {call['mode'] for call in submitted_calls} == {'random'}


def test_run_batch_with_explicit_balanced_mode_also_falls_back_to_random_when_accounts_are_insufficient(screening_service_factory, monkeypatch):
    service = screening_service_factory()
    accounts = _build_accounts(10)
    submitted_calls: list[dict[str, Any]] = []
    _install_batch_stubs(monkeypatch, service, submitted_calls=submitted_calls)

    summary = service.run_batch(accounts, seed=7, mode='balanced')

    _assert_summary_keys(summary, 'resolved_mode', 'balanced_plan')
    assert summary['resolved_mode'] == 'balanced'
    assert summary['balanced_plan']['fallback_reason'] == 'insufficient_accounts'
    assert len(submitted_calls) == 10
    assert {call['mode'] for call in submitted_calls} == {'random'}


def test_run_batch_with_high_mode_bypasses_balanced_distribution(screening_service_factory, monkeypatch):
    service = screening_service_factory()
    accounts = _build_accounts(11)
    submitted_calls: list[dict[str, Any]] = []
    _install_batch_stubs(monkeypatch, service, submitted_calls=submitted_calls)

    summary = service.run_batch(accounts, seed=7, mode='high')

    _assert_summary_keys(summary, 'resolved_mode')
    assert summary['resolved_mode'] == 'high'
    if 'balanced_plan' in summary:
        assert summary['balanced_plan']['fallback_reason'] is None
    assert len(submitted_calls) == 11
    assert {call['mode'] for call in submitted_calls} == {'high'}


def test_run_batch_with_none_seed_keeps_summary_seed_used_none(screening_service_factory, monkeypatch):
    service = screening_service_factory()
    accounts = _build_accounts(11)
    submitted_calls: list[dict[str, Any]] = []
    _install_batch_stubs(monkeypatch, service, submitted_calls=submitted_calls)

    summary = service.run_batch(accounts, seed=None, mode=None)

    _assert_summary_keys(summary, 'resolved_mode', 'balanced_plan')
    assert summary['resolved_mode'] == 'balanced'
    assert summary['balanced_plan']['seed_used'] is None
    assert summary['balanced_plan']['mode_distribution'] == {'random': 6, 'low': 2, 'middle': 2, 'high': 1}
    assert len(submitted_calls) == 11
    assert all(call['mode'] in {'random', 'low', 'middle', 'high'} for call in submitted_calls)


def test_run_smoke_with_none_mode_keeps_submit_mode_none(screening_service_factory, monkeypatch):
    service = screening_service_factory({'username': 'smoke-user', 'label': 'smoke-user'})
    submitted_calls: list[dict[str, Any]] = []
    _install_batch_stubs(monkeypatch, service, submitted_calls=submitted_calls)

    result = service.run_smoke(seed=7, mode=None)

    assert result['success'] is True
    assert [call['mode'] for call in submitted_calls] == [None]


def test_run_batch_balanced_distribution_uses_accounts_with_tasks_population(screening_service_factory, monkeypatch):
    service = screening_service_factory()
    accounts = _build_accounts(20)
    submitted_calls: list[dict[str, Any]] = []

    active_indices = {0, 2, 3, 6, 7, 11, 13, 14, 15, 17, 18, 19}

    def fake_ensure_login(account=None):
        return f"token-{user_label(account)}"

    def fake_list_task_refs(*, statuses=None):
        account = service.client.account
        label = user_label(account)
        index = int(str(label).split('-')[-1])
        if index not in active_indices:
            return []
        return [TaskRef(paper_task_id=f'paper-{label}', task_user_id=f'task-user-{label}', raw={'label': label})]

    def fake_submit_task(task, *, seed=None, mode=None):
        account = service.client.account
        label = user_label(account)
        submitted_calls.append(
            {
                'account': label,
                'paper_task_id': task.paper_task_id,
                'task_user_id': task.task_user_id,
                'seed': seed,
                'mode': mode,
            }
        )
        return {
            'paper_task_id': task.paper_task_id,
            'task_id': task.paper_task_id,
            'task_user_id': task.task_user_id,
            'paper_summary': {'subjects': 1},
            'request_payload': {'mode': mode, 'seed': seed},
            'response_payload': {'code': 200},
            'status_code': 200,
            'business_code': 200,
            'business_message': 'ok',
            'success': True,
        }

    monkeypatch.setattr(service, 'ensure_login', fake_ensure_login)
    monkeypatch.setattr(service, 'list_task_refs', fake_list_task_refs)
    monkeypatch.setattr(service, 'submit_task', fake_submit_task)

    summary = service.run_batch(accounts, seed=7, mode=None)

    _assert_summary_keys(summary, 'resolved_mode', 'balanced_plan')
    assert summary['resolved_mode'] == 'balanced'
    assert summary['balanced_plan']['total_accounts'] == 12
    assert summary['balanced_plan']['mode_distribution_population'] == 'accounts_with_tasks'
    assert summary['balanced_plan']['mode_distribution'] == {'random': 6, 'low': 2, 'middle': 2, 'high': 2}
    assert summary['risk_distribution_actual_accounts'] == {'low': 2, 'middle': 2, 'high': 2}
    assert summary['risk_distribution_actual_accounts_total'] == 6
    assert summary['risk_distribution_actual_accounts_ratio'] == {'low': 0.3333, 'middle': 0.3333, 'high': 0.3333}
    assert summary['mode_distribution_actual_accounts_ratio'] == {
        'random': 0.5,
        'low': 0.1667,
        'middle': 0.1667,
        'high': 0.1667,
    }
    assert summary['balanced_plan']['risk_distribution_actual_accounts'] == {'low': 2, 'middle': 2, 'high': 2}
    assert summary['balanced_plan']['risk_distribution_actual_accounts_total'] == 6
    assert summary['balanced_plan']['risk_distribution_actual_accounts_ratio'] == {
        'low': 0.3333,
        'middle': 0.3333,
        'high': 0.3333,
    }
    assert len(submitted_calls) == 12
    assert Counter(call['mode'] for call in submitted_calls) == {'random': 6, 'low': 2, 'middle': 2, 'high': 2}


def test_run_batch_balanced_threshold_is_based_on_accounts_with_tasks(screening_service_factory, monkeypatch):
    service = screening_service_factory()
    accounts = _build_accounts(20)
    submitted_calls: list[dict[str, Any]] = []

    active_indices = {0, 1, 2, 3, 4, 5, 6, 7}

    def fake_ensure_login(account=None):
        return f"token-{user_label(account)}"

    def fake_list_task_refs(*, statuses=None):
        account = service.client.account
        label = user_label(account)
        index = int(str(label).split('-')[-1])
        if index not in active_indices:
            return []
        return [TaskRef(paper_task_id=f'paper-{label}', task_user_id=f'task-user-{label}', raw={'label': label})]

    def fake_submit_task(task, *, seed=None, mode=None):
        account = service.client.account
        label = user_label(account)
        submitted_calls.append(
            {
                'account': label,
                'paper_task_id': task.paper_task_id,
                'task_user_id': task.task_user_id,
                'seed': seed,
                'mode': mode,
            }
        )
        return {
            'paper_task_id': task.paper_task_id,
            'task_id': task.paper_task_id,
            'task_user_id': task.task_user_id,
            'paper_summary': {'subjects': 1},
            'request_payload': {'mode': mode, 'seed': seed},
            'response_payload': {'code': 200},
            'status_code': 200,
            'business_code': 200,
            'business_message': 'ok',
            'success': True,
        }

    monkeypatch.setattr(service, 'ensure_login', fake_ensure_login)
    monkeypatch.setattr(service, 'list_task_refs', fake_list_task_refs)
    monkeypatch.setattr(service, 'submit_task', fake_submit_task)

    summary = service.run_batch(accounts, seed=7, mode=None)

    _assert_summary_keys(summary, 'resolved_mode', 'balanced_plan')
    assert summary['resolved_mode'] == 'balanced'
    assert summary['balanced_plan']['total_accounts'] == 8
    assert summary['balanced_plan']['fallback_reason'] == 'insufficient_accounts'
    assert summary['balanced_plan']['mode_distribution'] == {'random': 8, 'low': 0, 'middle': 0, 'high': 0}
    assert len(submitted_calls) == 8
    assert {call['mode'] for call in submitted_calls} == {'random'}
