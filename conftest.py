from __future__ import annotations

import pytest

from core.settings import load_settings
from core.utils.answer_mode_plan import ANSWER_MODE_HELP, ANSWER_MODE_OPTION_CHOICES
from core.utils.datasets import load_accounts
from services.screening_service import ScreeningService


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('psytest')
    group.addoption('--env', action='store', choices=['dev', 'test', 'pre'], default='test', help='目标环境')
    group.addoption('--account-file', action='store', default='data/account.json', help='账号文件路径')
    group.addoption('--statuses', action='store', default='', help='任务状态列表，逗号分隔，例如 1,2')
    group.addoption('--submit-path', action='store', default='', help='覆盖 SCREENING_SUBMIT_PATH')
    group.addoption('--answer-mode', action='store', choices=ANSWER_MODE_OPTION_CHOICES, default='', help=ANSWER_MODE_HELP)
    group.addoption('--seed', action='store', default='', help='随机种子')
    group.addoption('--allow-empty-submit', action='store_true', help='无任务或无可提交结果时不失败')


@pytest.fixture(scope='session')
def env_name(pytestconfig: pytest.Config) -> str:
    return str(pytestconfig.getoption('--env'))


@pytest.fixture(scope='session')
def settings(pytestconfig: pytest.Config):
    overrides: dict[str, str] = {}
    statuses = str(pytestconfig.getoption('--statuses') or '').strip()
    submit_path = str(pytestconfig.getoption('--submit-path') or '').strip()
    if statuses:
        overrides['SCREENING_TASK_STATUSES'] = statuses
    if submit_path:
        overrides['SCREENING_SUBMIT_PATH'] = submit_path
    if pytestconfig.getoption('--allow-empty-submit'):
        overrides['ALLOW_EMPTY_SUBMIT'] = '1'
    return load_settings(str(pytestconfig.getoption('--env')), overrides=overrides)


@pytest.fixture(scope='session')
def accounts(pytestconfig: pytest.Config):
    return load_accounts(pytestconfig.getoption('--account-file'))


@pytest.fixture(scope='session')
def default_account(accounts):
    return accounts[0] if accounts else None


@pytest.fixture(scope='session')
def answer_mode(pytestconfig: pytest.Config):
    value = str(pytestconfig.getoption('--answer-mode') or '').strip()
    return value or None


@pytest.fixture(scope='session')
def random_seed(pytestconfig: pytest.Config):
    value = str(pytestconfig.getoption('--seed') or '').strip()
    return int(value) if value else None


@pytest.fixture(scope='session')
def allow_empty_submit(settings) -> bool:
    return bool(settings.allow_empty_submit)


@pytest.fixture(scope='session')
def task_statuses(settings):
    return settings.screening_task_statuses


@pytest.fixture
def screening_service_factory(settings):
    def _factory(account=None):
        return ScreeningService(settings=settings, account=account)
    return _factory
