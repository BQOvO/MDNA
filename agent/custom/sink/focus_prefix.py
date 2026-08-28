import threading
from typing import ClassVar

from maa.agent.agent_server import AgentServer
from maa.event_sink import NotificationType
from maa.tasker import Tasker, TaskerEventSink
from ..utils.Logger import Logger


@AgentServer.tasker_sink()
class FocusPrefix(TaskerEventSink):
    _cached_hash: ClassVar[str] = ""
    _focus_cache: ClassVar[dict] = {}
    _last_override: ClassVar[dict] = {}
    _last_prefix: ClassVar[str] = ""
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def _ensure_cache_locked(cls, resource):
        current_hash = resource.hash
        if not current_hash or current_hash == cls._cached_hash:
            return
        new_cache = {}
        for node_name in resource.node_list:
            node_data = resource.get_node_data(node_name)
            if node_data and node_data.get("focus"):
                new_cache[node_name] = node_data["focus"]
        cls._focus_cache = new_cache
        cls._cached_hash = current_hash
        cls._last_prefix = ""

    @staticmethod
    def _add_prefix(focus, prefix):
        if isinstance(focus, str):
            return prefix + focus
        if isinstance(focus, dict):
            return {
                k: (prefix + v) if isinstance(v, str) else v
                for k, v in focus.items()
            }
        return focus

    def on_tasker_task(
        self,
        tasker: Tasker,
        noti_type: NotificationType,
        detail: TaskerEventSink.TaskerTaskDetail,
    ):
        if noti_type != NotificationType.Starting:
            return

        prefix = f"[{detail.entry}] "
        Logger.set_ui_prefix(prefix)

        with self._lock:
            resource = tasker.resource
            self._ensure_cache_locked(resource)

            if prefix == self._last_prefix:
                override = self._last_override
            else:
                override = {}
                for node_name, focus in self._focus_cache.items():
                    prefixed = self._add_prefix(focus, prefix)
                    if prefixed is not focus:
                        override[node_name] = {"focus": prefixed}
                self._last_prefix = prefix
                self._last_override = override

        if override:
            tasker.override_pipeline(detail.task_id, override)