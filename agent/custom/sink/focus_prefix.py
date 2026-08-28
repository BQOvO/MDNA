import json
import os
import threading
from typing import ClassVar

from maa.agent.agent_server import AgentServer
from maa.context import Context, ContextEventSink
from maa.event_sink import NotificationType
from ..utils.Logger import Logger

TASKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "tasks")


def _build_entry_to_name() -> dict:
    mapping = {}
    try:
        for root, _, files in os.walk(TASKS_DIR):
            for f in files:
                if not f.endswith(".json"):
                    continue
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                for task in data.get("task", []):
                    entry = task.get("entry")
                    name = task.get("name")
                    if entry and name:
                        mapping[entry] = name
    except Exception:
        pass
    return mapping


@AgentServer.context_sink()
class FocusPrefix(ContextEventSink):
    _cached_hash: ClassVar[str] = ""
    _focus_cache: ClassVar[dict] = {}
    _entry_to_name: ClassVar[dict] = {}
    _last_override: ClassVar[dict] = {}
    _last_prefix: ClassVar[str] = ""
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def _ensure_cache_locked(cls, resource):
        if not cls._entry_to_name:
            cls._entry_to_name = _build_entry_to_name()

        current_hash = resource.hash
        if not current_hash or current_hash == cls._cached_hash:
            if not cls._focus_cache:
                pass
            else:
                return
        new_cache = {}
        for node_name in resource.node_list:
            node_data = resource.get_node_data(node_name)
            if node_data and node_data.get("focus"):
                new_cache[node_name] = node_data["focus"]
        cls._focus_cache = new_cache
        cls._cached_hash = current_hash if current_hash else "__forced__"
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

    def on_node_pipeline_node(
        self,
        context: Context,
        noti_type: NotificationType,
        detail: ContextEventSink.NodePipelineNodeDetail,
    ):
        if noti_type != NotificationType.Starting:
            return

        entry = detail.name or ""
        if not entry.endswith("-启动"):
            return

        task_name = self._entry_to_name.get(entry, entry.rsplit("-启动", 1)[0])
        prefix = f"[{task_name}] "
        Logger.set_ui_prefix(prefix)

        with self._lock:
            resource = context.tasker.resource
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
            context.override_pipeline(override)