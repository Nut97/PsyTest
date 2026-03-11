from __future__ import annotations

import argparse
import subprocess


SUITE_TO_TARGET = {
    'smoke': ['tests/test_smoke_screening.py'],
    'e2e': ['tests/test_e2e_batch.py'],
    'all': ['tests/test_smoke_screening.py', 'tests/test_e2e_batch.py'],
}


def build_pytest_command(args: argparse.Namespace) -> list[str]:
    cmd = ['pytest', '-c', 'pyproject.toml', '--env', args.env]
    cmd.extend(SUITE_TO_TARGET[args.suite])

    if args.account_file:
        cmd.extend(['--account-file', args.account_file])
    if args.statuses:
        cmd.extend(['--statuses', args.statuses])
    if args.submit_path:
        cmd.extend(['--submit-path', args.submit_path])
    if args.answer_mode:
        cmd.extend(['--answer-mode', args.answer_mode])
    if args.seed is not None:
        cmd.extend(['--seed', str(args.seed)])
    if args.allow_empty_submit:
        cmd.append('--allow-empty-submit')
    if args.allure:
        cmd.extend(['--alluredir', 'reports/allure'])

    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Psytest 单入口启动器')
    parser.add_argument('--env', choices=['dev', 'test', 'pre'], default='test')
    parser.add_argument('--suite', choices=['smoke', 'e2e', 'all'], default='smoke')
    parser.add_argument('--account-file', default='data/account.json')
    parser.add_argument('--statuses', default='')
    parser.add_argument('--submit-path', default='')
    parser.add_argument('--answer-mode', default='')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--allow-empty-submit', action='store_true')
    parser.add_argument('--allure', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    arguments = parse_args()
    command = build_pytest_command(arguments)
    raise SystemExit(subprocess.call(command))