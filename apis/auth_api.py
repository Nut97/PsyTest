from __future__ import annotations

from typing import Any

import requests

from core.settings import Settings


class AuthApi:
    def __init__(self, *, settings: Settings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()

    @staticmethod
    def username_of(account: dict[str, Any] | None) -> str | None:
        if not account:
            return None
        return (
            account.get('username')
            or account.get('studentNum')
            or account.get('account')
            or account.get('userName')
        )

    def login(self, account: dict[str, Any] | None) -> requests.Response:
        username = self.username_of(account)
        if not username:
            raise ValueError('login account missing username/studentNum')
        payload = {
            'username': username,
            'password': (account or {}).get('password', ''),
            'grant_type': 'password',
            'scope': 'all',
            'user_code': 'screening',
        }
        headers = dict(self.settings.default_headers)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        return self.session.post(
            self.settings.build_url(self.settings.auth_path),
            data=payload,
            headers=headers,
            timeout=self.settings.timeout_seconds,
        )