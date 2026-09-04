"""
GameHealthOverride - 在任务启动时统一给所有节点加上 on_error 游戏进程检查

像 focus_prefix 一样，在 on_node_pipeline_node(Starting) 时：
1. 扫描所有 pipeline 节点
2. 对没有 on_error 的节点，override 上 on_error: ["游戏进程检查"]
3. 通过 context.override_pipeline() 生效
"""

from typing import ClassVar

from maa.agent.agent_server import AgentServer
from maa.context import Context, ContextEventSink
from maa.event_sink import NotificationType
from ..utils.Logger import Logger

_log = Logger("GameHealthOverride")

ON_ERROR_CHAIN = ["游戏进程检查"]


@AgentServer.context_sink()
class GameHealthOverride(ContextEventSink):
    _applied_hash: ClassVar[str] = ""
    _cached_override: ClassVar[dict] = {}

    def on_node_pipeline_node(
        self,
        context: Context,
        noti_type: NotificationType,
        detail: ContextEventSink.NodePipelineNodeDetail,
    ):
        if noti_type != NotificationType.Starting:
            return

        resource = context.tasker.resource
        current_hash = resource.hash or ""

        if current_hash and current_hash == self._applied_hash:
            return

        override = {}
        for node_name in resource.node_list:
            node_data = resource.get_node_data(node_name)
            if not node_data:
                continue
            if node_data.get("on_error"):
                continue
            override[node_name] = {"on_error": ON_ERROR_CHAIN}

        if override:
            _log.info(f"GameHealth: 给 {len(override)} 个节点加上 on_error")
            context.override_pipeline(override)

        self._applied_hash = current_hash
        self._cached_override = override