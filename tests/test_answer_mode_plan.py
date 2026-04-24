from __future__ import annotations

import pytest

from core.utils.answer_mode_plan import build_balanced_plan, resolve_batch_mode


def _assignment_counts(plan) -> dict[str, int]:
    buckets = {'random': 0, 'low': 0, 'middle': 0, 'high': 0}
    for mode in plan.assignment_by_index.values():
        buckets[mode] += 1
    return buckets


def _assert_assignment_keys_complete(plan, total: int) -> None:
    assert set(plan.assignment_by_index) == set(range(total))


def test_batch_default_mode_empty_value_resolves_to_balanced():
    assert resolve_batch_mode(None) == 'balanced'
    assert resolve_batch_mode('') == 'balanced'
    assert resolve_batch_mode('   ') == 'balanced'


@pytest.mark.parametrize('total', [1, 9, 10])
def test_balanced_plan_falls_back_to_all_random_when_total_is_not_greater_than_10(total: int):
    plan = build_balanced_plan(total_accounts=total, seed=123)

    assert plan.enabled is False
    assert plan.fallback_reason == 'insufficient_accounts'
    assert plan.total_accounts == total
    assert plan.threshold == 10
    assert plan.random_group_size == total
    assert plan.balanced_group_size == 0
    assert plan.mode_distribution == {'random': total, 'low': 0, 'middle': 0, 'high': 0}
    assert plan.seed_used == 123
    assert _assignment_counts(plan) == {'random': total, 'low': 0, 'middle': 0, 'high': 0}
    _assert_assignment_keys_complete(plan, total=total)


def test_balanced_plan_for_11_items_matches_expected_distribution():
    plan = build_balanced_plan(total_accounts=11, seed=123)

    assert plan.enabled is True
    assert plan.fallback_reason is None
    assert plan.total_accounts == 11
    assert plan.threshold == 10
    assert plan.random_group_size == 6
    assert plan.balanced_group_size == 5
    assert plan.mode_distribution == {'random': 6, 'low': 2, 'middle': 2, 'high': 1}
    assert plan.seed_used == 123
    assert _assignment_counts(plan) == {'random': 6, 'low': 2, 'middle': 2, 'high': 1}
    _assert_assignment_keys_complete(plan, total=11)


def test_balanced_plan_for_14_items_matches_expected_distribution():
    plan = build_balanced_plan(total_accounts=14, seed=123)

    assert plan.enabled is True
    assert plan.fallback_reason is None
    assert plan.total_accounts == 14
    assert plan.threshold == 10
    assert plan.random_group_size == 7
    assert plan.balanced_group_size == 7
    assert plan.mode_distribution == {'random': 7, 'low': 3, 'middle': 2, 'high': 2}
    assert plan.seed_used == 123
    assert _assignment_counts(plan) == {'random': 7, 'low': 3, 'middle': 2, 'high': 2}
    _assert_assignment_keys_complete(plan, total=14)


def test_balanced_plan_for_12_items_matches_expected_distribution():
    plan = build_balanced_plan(total_accounts=12, seed=123)

    assert plan.enabled is True
    assert plan.fallback_reason is None
    assert plan.total_accounts == 12
    assert plan.threshold == 10
    assert plan.random_group_size == 6
    assert plan.balanced_group_size == 6
    assert plan.mode_distribution == {'random': 6, 'low': 2, 'middle': 2, 'high': 2}
    assert plan.seed_used == 123
    assert _assignment_counts(plan) == {'random': 6, 'low': 2, 'middle': 2, 'high': 2}
    _assert_assignment_keys_complete(plan, total=12)


def test_balanced_plan_is_reproducible_with_same_seed():
    plan1 = build_balanced_plan(total_accounts=14, seed=2024)
    plan2 = build_balanced_plan(total_accounts=14, seed=2024)

    assert plan1 == plan2


def test_balanced_plan_changes_when_seed_changes():
    assignments = {
        tuple(sorted(build_balanced_plan(total_accounts=14, seed=seed).assignment_by_index.items()))
        for seed in range(2024, 2040)
    }

    assert len(assignments) > 1


def test_balanced_plan_with_none_seed_keeps_seed_used_none_and_complete_keys():
    plan = build_balanced_plan(total_accounts=14, seed=None)

    assert plan.enabled is True
    assert plan.fallback_reason is None
    assert plan.total_accounts == 14
    assert plan.threshold == 10
    assert plan.random_group_size == 7
    assert plan.balanced_group_size == 7
    assert plan.mode_distribution == {'random': 7, 'low': 3, 'middle': 2, 'high': 2}
    assert plan.seed_used is None
    _assert_assignment_keys_complete(plan, total=14)


@pytest.mark.parametrize(
    ('total_accounts', 'threshold'),
    [(-1, 10), (1, -1), (-1, -1)],
)
def test_balanced_plan_rejects_negative_inputs(total_accounts: int, threshold: int):
    with pytest.raises(ValueError):
        build_balanced_plan(total_accounts=total_accounts, seed=123, threshold=threshold)


@pytest.mark.parametrize(
    ('total_accounts', 'threshold'),
    [('14', 10), (14.5, 10), (14, '10'), (14, 10.5)],
)
def test_balanced_plan_rejects_non_integer_inputs(total_accounts, threshold):
    with pytest.raises(TypeError):
        build_balanced_plan(total_accounts=total_accounts, seed=123, threshold=threshold)
