from maa.agent.agent_server import AgentServer
from maa.context import Context, ContextEventSink
from maa.event_sink import NotificationType
from ..utils.Logger import Logger


@AgentServer.context_sink()
class OptionValidationSink(ContextEventSink):

    def on_node_pipeline_node(
        self,
        context: Context,
        noti_type: NotificationType,
        detail: ContextEventSink.NodePipelineNodeDetail,
    ):
        if noti_type != NotificationType.Starting:
            return

        node_name = detail.name or ""
        if not node_name.endswith("-启动"):
            return

        rules = [
            {
                "check_node": "轮次",
                "max": 100,
                "message": "轮次目标大于100，请重新输入",
            },
        ]

        for rule in rules:
            node_data = context.get_node_data(rule["check_node"])
            if not node_data or not isinstance(node_data, dict):
                continue

            target = node_data.get("custom_action_param", {})
            if isinstance(target, dict):
                target = target.get("target")
            else:
                target = None

            if target is None:
                action = node_data.get("action", {})
                if isinstance(action, dict):
                    param = action.get("param", {})
                    if isinstance(param, dict):
                        cap = param.get("custom_action_param", {})
                        if isinstance(cap, dict):
                            target = cap.get("target")

            if target is None:
                continue

            try:
                target = int(target)
            except (ValueError, TypeError):
                continue

            if target > rule["max"]:
                logger = Logger("OptionValidation", context)
                logger.ui(rule["message"], color="red")
                print(f"[OptionValidation] {rule['message']}")
                context.tasker.post_stop()
                return