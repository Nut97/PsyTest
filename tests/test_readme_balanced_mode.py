from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / 'readme.md'


def _read_readme() -> str:
    return README.read_text(encoding='utf-8')


def _extract_balanced_section(text: str) -> str:
    match = re.search(
        r'^###\s*11\.3\s*`?balanced`?.*?$(.*?)(?=^------\s*$|^###\s+|^##\s+|\Z)',
        text,
        flags=re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    assert match, '未找到 README 的 11.3 balanced 规则段落'
    return match.group(0)


def _normalize_for_regex(text: str) -> str:
    normalized = text.casefold()
    normalized = normalized.replace('（', '(').replace('）', ')')
    normalized = normalized.replace('`', '')
    normalized = re.sub(r'\s+', '', normalized)
    return normalized


def _assert_matches(section: str, pattern: str, message: str) -> None:
    normalized = _normalize_for_regex(section)
    assert re.search(pattern, normalized), message


def test_readme_balanced_mode_scope_semantics():
    section = _extract_balanced_section(_read_readme())

    _assert_matches(
        section,
        r'仅批量.*?(e2e/?run_batch|run_batch/?e2e).*?(未指定|不指定).*?--answer-mode.*?默认.*?balanced',
        '11.3 段落应说明：仅批量在未指定 --answer-mode 时默认 balanced',
    )
    _assert_matches(
        section,
        r'smoke.*?非批量.*?(不会默认|不默认).*?balanced',
        '11.3 段落应说明：smoke/非批量场景不默认 balanced',
    )


def test_readme_balanced_mode_small_n_semantics():
    section = _extract_balanced_section(_read_readme())

    _assert_matches(
        section,
        r'n<=10.*?(全|全部).*?random',
        '11.3 段落应说明：N<=10 全 random',
    )


def test_readme_balanced_mode_large_n_semantics():
    section = _extract_balanced_section(_read_readme())

    _assert_matches(
        section,
        r'n>10.*?半.*?random.*?半.*?(low/?middle/?high|lowmiddlehigh).*?等比',
        '11.3 段落应说明：N>10 半 random + 半 low/middle/high 等比',
    )


def test_readme_balanced_mode_odd_rule_semantics():
    section = _extract_balanced_section(_read_readme())

    _assert_matches(
        section,
        r'奇数.*?random.*?多1',
        '11.3 段落应说明：奇数时 random 多 1',
    )


def test_readme_balanced_mode_section_does_not_claim_global_default():
    section = _extract_balanced_section(_read_readme())
    normalized = _normalize_for_regex(section)

    misleading_patterns = [
        r'全场景.*?默认.*?balanced',
        r'所有场景.*?默认.*?balanced',
        r'任何场景.*?默认.*?balanced',
        r'全部场景.*?默认.*?balanced',
        r'balanced.*?(是|为).*?(全场景|所有场景|任何场景|全部场景).*?默认',
    ]

    for pattern in misleading_patterns:
        assert not re.search(pattern, normalized), f'11.3 段落不应包含误导性默认描述: {pattern}'
