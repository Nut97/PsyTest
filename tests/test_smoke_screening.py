from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_smoke_screening(default_account, screening_service_factory, task_statuses, random_seed, answer_mode):
    if not default_account:
        pytest.skip('未找到 data/account.json，跳过冒烟')
    service = screening_service_factory(default_account)
    result = service.run_smoke(statuses=task_statuses, seed=random_seed or 42, mode=answer_mode)
    assert result['success'] is True
    assert result['paper_summary']['subjects'] > 0