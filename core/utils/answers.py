from __future__ import annotations

import os
import random
from typing import Any


OPTION_TEXT_KEYS = ('optionText', 'text', 'label', 'name', 'value')
OPTION_SCORE_KEYS = ('optionScore', 'score', 'weight', 'optionValue', 'value')
MODE_INDEX_MAP = {
    'first': 0,
    'second': 1,
    'third': 2,
    'fourth': 3,
    'fifth': 4,
    'sixth': 5,
    'seventh': 6,
}


def _resolve_mode(mode: str | None) -> str:
    return (mode or os.getenv('ANSWER_MODE') or 'random').strip().lower()


def _paper_data(paper_resp: dict[str, Any]) -> dict[str, Any]:
    return (paper_resp or {}).get('data') or {}


def iter_gauges(paper_resp: dict[str, Any]):
    for gauge in _paper_data(paper_resp).get('gaugeDtos') or []:
        if isinstance(gauge, dict):
            yield gauge


def iter_subjects(paper_resp: dict[str, Any]):
    for gauge in iter_gauges(paper_resp):
        for subject in gauge.get('gaugeSubjectVOList') or []:
            if isinstance(subject, dict):
                yield gauge, subject


def summarize_paper(paper_resp: dict[str, Any]) -> dict[str, Any]:
    gauge_count = 0
    subject_count = 0
    option_counts: list[int] = []
    for gauge in iter_gauges(paper_resp):
        gauge_count += 1
        subjects = gauge.get('gaugeSubjectVOList') or []
        subject_count += len(subjects)
        option_counts.extend(len(subject.get('gaugeSubjectOptionDtoList') or []) for subject in subjects)
    return {
        'gauges': gauge_count,
        'subjects': subject_count,
        'option_count_min': min(option_counts) if option_counts else 0,
        'option_count_max': max(option_counts) if option_counts else 0,
        'option_count_set': sorted(set(option_counts)),
    }


def _option_text(option: dict[str, Any] | None) -> str | None:
    if not option:
        return None
    for key in OPTION_TEXT_KEYS:
        value = option.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float)):
            return str(value)
    return None


def _fallback_answer_text(subject: dict[str, Any]) -> str:
    for key in ('defaultAnswer', 'answer', 'subjectDesc'):
        value = subject.get(key)
        if value is not None and str(value) != '':
            return str(value)
    return ''


def _option_score(option: dict[str, Any], index: int) -> float:
    for key in OPTION_SCORE_KEYS:
        value = option.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except Exception:
            pass
    return float(index)


def _weighted_pick(options: list[dict[str, Any]], rnd: random.Random, mode: str) -> dict[str, Any]:
    scores = [_option_score(option, index) for index, option in enumerate(options)]
    if mode == 'low':
        maximum = max(scores)
        weights = [maximum - score + 1.0 for score in scores]
    elif mode == 'high':
        minimum = min(scores)
        weights = [score - minimum + 1.0 for score in scores]
    elif mode == 'middle':
        center = (min(scores) + max(scores)) / 2.0
        weights = [1.0 / (1.0 + abs(score - center)) for score in scores]
    else:
        weights = [1.0 for _ in scores]
    return rnd.choices(options, weights=weights, k=1)[0]


def pick_answer_option(subject: dict[str, Any], rnd: random.Random, mode: str | None = None) -> dict[str, Any] | None:
    options = [option for option in (subject.get('gaugeSubjectOptionDtoList') or []) if isinstance(option, dict)]
    if not options:
        return None
    mode = _resolve_mode(mode)
    fixed_index = MODE_INDEX_MAP.get(mode)
    if fixed_index is not None:
        return options[min(fixed_index, len(options) - 1)]
    if mode == 'random':
        return rnd.choice(options)
    return _weighted_pick(options, rnd, mode)


def _build_subject_answer(subject: dict[str, Any], task_user_id: str, rnd: random.Random, mode: str) -> dict[str, Any]:
    subject_id = subject.get('id')
    if subject_id in (None, ''):
        raise ValueError(f'subject id missing: {subject}')
    selected = pick_answer_option(subject, rnd, mode=mode)
    answer = _option_text(selected) or _fallback_answer_text(subject)
    return {
        'subjectId': str(subject_id),
        'answer': answer,
        'taskUserId': str(task_user_id),
        'answerIntervalTime': rnd.randint(1, 2000),
        'identificationQuestion': str(subject.get('identificationQuestion') or '0'),
    }


def build_answer_list(
    paper_resp: dict[str, Any],
    *,
    task_user_id: str | int,
    seed: int | None = None,
    mode: str | None = None,
) -> list[dict[str, Any]]:
    rnd = random.Random(seed)
    final_mode = _resolve_mode(mode)
    results: list[dict[str, Any]] = []
    for gauge in iter_gauges(paper_resp):
        gauge_id = gauge.get('id') or gauge.get('gaugeId')
        if gauge_id in (None, ''):
            raise ValueError(f'gauge id missing: {gauge}')
        complete_answers = [
            _build_subject_answer(subject, str(task_user_id), rnd, final_mode)
            for subject in (gauge.get('gaugeSubjectVOList') or [])
            if isinstance(subject, dict)
        ]
        results.append(
            {
                'gaugeId': str(gauge_id),
                'completeAnswerDTOList': complete_answers,
            }
        )
    return results


def build_submit_payload(
    paper_resp: dict[str, Any],
    task_user_id: str | int,
    *,
    seed: int | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    gauge_answers = build_answer_list(
        paper_resp,
        task_user_id=task_user_id,
        seed=seed,
        mode=mode,
    )
    summary = summarize_paper(paper_resp)
    generated_subjects = sum(len(gauge.get('completeAnswerDTOList') or []) for gauge in gauge_answers)
    if generated_subjects != summary['subjects']:
        raise ValueError(
            f'generated subject count mismatch: expected={summary["subjects"]}, actual={generated_subjects}'
        )
    return {
        'taskUserId': str(task_user_id),
        'basicInfoData': None,
        'gaugeAnswerDTOList': gauge_answers,
    }