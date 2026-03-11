from __future__ import annotations

from typing import Any

from core.http import APIClient


class ScreeningApi:
    def __init__(self, client: APIClient) -> None:
        self.client = client
        self.settings = client.settings

    def list_tasks(self, *, status: int):
        return self.client.request(
            'GET',
            self.settings.screening_task_list_path,
            params={'status': status},
        )

    def get_paper(self, paper_task_id: str | int):
        return self.client.request('GET', self.settings.format_get_paper_path(paper_task_id))

    def submit_answers(self, payload: dict[str, Any]):
        return self.client.request('POST', self.settings.screening_submit_path, json_body=payload)

    @staticmethod
    def extract_tasks(payload: dict[str, Any] | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        data = payload.get('data')
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ('records', 'list', 'rows', 'items', 'content', 'data'):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _resolve_first(task: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = task.get(key)
            if value not in (None, ''):
                return str(value)
        return None

    @classmethod
    def resolve_paper_task_id(cls, task: dict[str, Any]) -> str | None:
        """
        getPaper 路径参数。

        兼容老 JMX / 现网返回里常见的几种字段命名：
        - taskId：最标准的命名
        - taskUserId：部分链路里 getPaper 与 submit 复用同一值
        - id：列表接口只给主键时兜底
        """
        return cls._resolve_first(task, ('taskId', 'taskUserId', 'id'))

    @classmethod
    def resolve_task_user_id(cls, task: dict[str, Any], *, fallback_paper_task_id: str | None = None) -> str | None:
        """
        answerSubmit 顶层 taskUserId。

        优先取真正的 taskUserId；若列表接口未返回，则回退到 taskId / id。
        这样既兼容新版接口，也兼容 JMX 中“getPaper 的 taskId 同时作为 taskUserId 提交”的场景。
        """
        resolved = cls._resolve_first(task, ('taskUserId', 'taskId', 'id'))
        return resolved or fallback_paper_task_id