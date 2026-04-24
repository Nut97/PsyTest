from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from core.utils import answer_mode_plan


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SEMANTICS = '仅 batch 默认 balanced'


def _normalize_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def _compact_whitespace(text: str) -> str:
    return re.sub(r'\s+', '', text)


def _run_command(*args: str) -> str:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    return completed.stdout


def _run_command_allow_failure(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _extract_option_help(help_text: str, option_name: str) -> str:
    lines = help_text.splitlines()
    collected: list[str] = []
    capturing = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(option_name):
            collecting_line = stripped
            collected.append(collecting_line)
            capturing = True
            continue
        if capturing and line.startswith(' ' * 20):
            collected.append(stripped)
            continue
        if capturing:
            break

    assert collected, f'未找到 {option_name} help 片段: {help_text}'
    return '\n'.join(collected)


def _assert_help_semantics(help_text: str) -> None:
    option_help = _extract_option_help(help_text, '--answer-mode')
    normalized = _normalize_whitespace(option_help)
    compact = _compact_whitespace(option_help)

    assert hasattr(answer_mode_plan, 'ANSWER_MODE_HELP')
    assert hasattr(answer_mode_plan, 'ANSWER_MODE_CHOICES')
    assert hasattr(answer_mode_plan, 'ANSWER_MODE_CHOICES_FRAGMENT')
    assert _compact_whitespace(REQUIRED_SEMANTICS) in compact
    assert _compact_whitespace(answer_mode_plan.ANSWER_MODE_HELP) in compact
    assert _compact_whitespace(answer_mode_plan.ANSWER_MODE_CHOICES_FRAGMENT) in compact
    assert normalized.startswith('--answer-mode')


def test_start_help_mentions_batch_only_balanced_default_and_supported_modes():
    help_text = _run_command('start.py', '--help')

    _assert_help_semantics(help_text)


def test_pytest_help_mentions_batch_only_balanced_default_and_supported_modes():
    help_text = _run_command('-m', 'pytest', '-c', 'pyproject.toml', '--help')

    _assert_help_semantics(help_text)


def test_start_rejects_invalid_answer_mode_choice():
    completed = _run_command_allow_failure('start.py', '--answer-mode', 'invalid-mode')

    assert completed.returncode != 0
    assert 'invalid choice' in (completed.stderr or completed.stdout)
