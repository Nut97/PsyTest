from __future__ import annotations

from dataclasses import dataclass
import math
import random


BALANCED_MODE = 'balanced'
DEFAULT_BALANCED_THRESHOLD = 10
ANSWER_MODE_CHOICES = (
    'balanced',
    'random',
    'low',
    'high',
    'middle',
    'first',
    'second',
    'third',
    'fourth',
)
ANSWER_MODE_CHOICES_FRAGMENT = '/'.join(ANSWER_MODE_CHOICES)
ANSWER_MODE_OPTION_CHOICES = ('', *ANSWER_MODE_CHOICES)
ANSWER_MODE_HELP = f'答案模式 {ANSWER_MODE_CHOICES_FRAGMENT}，仅 batch 默认 balanced'


@dataclass(frozen=True)
class BalancedPlan:
    enabled: bool
    fallback_reason: str | None
    threshold: int
    total_accounts: int
    random_group_size: int
    balanced_group_size: int
    assignment_by_index: dict[int, str]
    mode_distribution: dict[str, int]
    seed_used: int | None

    @property
    def random_group(self) -> int:
        return self.random_group_size

    @property
    def balanced_group(self) -> int:
        return self.balanced_group_size


def resolve_batch_mode(mode: str | None) -> str:
    if mode is None:
        return BALANCED_MODE
    resolved = mode.strip().lower()
    return resolved or BALANCED_MODE


def _balanced_distribution(count: int) -> dict[str, int]:
    base = count // 3
    remainder = count % 3
    distribution = {'low': base, 'middle': base, 'high': base}
    for key in ('low', 'middle', 'high')[:remainder]:
        distribution[key] += 1
    return distribution


def build_balanced_plan(total_accounts: int, seed: int | None, threshold: int = DEFAULT_BALANCED_THRESHOLD) -> BalancedPlan:
    if not isinstance(total_accounts, int):
        raise TypeError('total_accounts must be an integer')
    if not isinstance(threshold, int):
        raise TypeError('threshold must be an integer')
    if total_accounts < 0:
        raise ValueError('total_accounts must be >= 0')
    if threshold < 0:
        raise ValueError('threshold must be >= 0')

    indices = list(range(total_accounts))
    random.Random(seed).shuffle(indices)

    assignment_by_index: dict[int, str] = {}

    if total_accounts <= threshold:
        for index in indices:
            assignment_by_index[index] = 'random'
        return BalancedPlan(
            enabled=False,
            fallback_reason='insufficient_accounts',
            threshold=threshold,
            total_accounts=total_accounts,
            random_group_size=total_accounts,
            balanced_group_size=0,
            assignment_by_index=assignment_by_index,
            mode_distribution={'random': total_accounts, 'low': 0, 'middle': 0, 'high': 0},
            seed_used=seed,
        )

    random_group = math.ceil(total_accounts / 2)
    balanced_group = math.floor(total_accounts / 2)
    balanced_distribution = _balanced_distribution(balanced_group)

    cursor = 0
    for index in indices[cursor : cursor + random_group]:
        assignment_by_index[index] = 'random'
    cursor += random_group

    for mode in ('low', 'middle', 'high'):
        group_size = balanced_distribution[mode]
        for index in indices[cursor : cursor + group_size]:
            assignment_by_index[index] = mode
        cursor += group_size

    return BalancedPlan(
        enabled=True,
        fallback_reason=None,
        threshold=threshold,
        total_accounts=total_accounts,
        random_group_size=random_group,
        balanced_group_size=balanced_group,
        assignment_by_index=assignment_by_index,
        mode_distribution={
            'random': random_group,
            'low': balanced_distribution['low'],
            'middle': balanced_distribution['middle'],
            'high': balanced_distribution['high'],
        },
        seed_used=seed,
    )
