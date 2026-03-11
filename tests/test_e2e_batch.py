from __future__ import annotations

import pytest


@pytest.mark.e2e
def test_e2e_batch(accounts, screening_service_factory, task_statuses, random_seed, answer_mode, allow_empty_submit):
    if not accounts:
        pytest.skip('未找到 data/account.json，跳过批量 E2E')
    service = screening_service_factory()
    summary = service.run_batch(
        accounts,
        statuses=task_statuses,
        seed=random_seed,
        mode=answer_mode,
        allow_empty_submit=allow_empty_submit,
    )
    assert summary['submitted'] > 0 or allow_empty_submit