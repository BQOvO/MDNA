from maa.context import Context
from maa.custom_action import CustomAction
import json
from ..utils.logger import logger

"""计数：支持无限计数或达到目标次数后跳转"""

class Count(CustomAction):
    def run(
        self, context: Context, argv: CustomAction.RunArg
    ) -> CustomAction.RunResult:
        log = logger("Count", context)  # 修改变量名避免冲突
        """
        自定义动作：
        custom_action_param:
            {
                "count": 0,
                "target_count": 10,      # 若 <=0 则视为无限计数模式
                "next_node": ["node1", "node2"],
                "else_node": ["node3"],
                "next_node_msg": "已达到目标次数，执行下一节点 {next_node}",
                "else_node_msg": "未达到目标次数，执行备用节点 {else_node}",
                "count_msg": "当前次数: {count}, 目标次数: {target_count}"
            }
        """
        argv_dict: dict = json.loads(argv.custom_action_param)
        if not argv_dict:
            return CustomAction.RunResult(success=True)

        current_count: int = argv_dict.get("count", 0)
        target_count: int = argv_dict.get("target_count", 0)
        next_node_msg: str = argv_dict.get("next_node_msg", "")
        else_node_msg: str = argv_dict.get("else_node_msg", "")
        count_msg: str = argv_dict.get("count_msg", "")

        log.info(
            f"Count: current_count={current_count}, target_count={target_count}, "
            f"next_node_msg={next_node_msg}, else_node_msg={else_node_msg}, count_msg={count_msg}"
        )

        # 无限计数模式
        if target_count <= 0:
            new_count = current_count + 1
            argv_dict["count"] = new_count

            if count_msg:
                log.ui(count_msg.format(count=current_count, target_count="无限"))

            context.override_pipeline(
                {argv.node_name: {"custom_action_param": argv_dict}}
            )
            return CustomAction.RunResult(success=True)

        # 有限计数模式
        if current_count < target_count:
            new_count = current_count + 1
            argv_dict["count"] = new_count

            if count_msg:
                log.ui(count_msg.format(count=current_count, target_count=target_count))

            context.override_pipeline(
                {argv.node_name: {"custom_action_param": argv_dict}}
            )

            else_nodes = argv_dict.get("else_node")
            if else_node_msg and else_nodes:
                node_str = else_nodes if isinstance(else_nodes, str) else ", ".join(else_nodes)
                log.ui(else_node_msg.format(else_node=node_str))
            self._run_nodes(context, else_nodes)
        else:
            reset_params = {
                "count": 0,
                "target_count": target_count,
                "else_node": argv_dict.get("else_node"),
                "next_node": argv_dict.get("next_node"),
                "next_node_msg": next_node_msg,
                "else_node_msg": else_node_msg,
                "count_msg": count_msg,
            }

            context.override_pipeline(
                {argv.node_name: {"custom_action_param": reset_params}}
            )

            next_nodes = argv_dict.get("next_node")
            if next_node_msg and next_nodes:
                node_str = next_nodes if isinstance(next_nodes, str) else ", ".join(next_nodes)
                log.ui(next_node_msg.format(next_node=node_str))
            self._run_nodes(context, next_nodes)

        return CustomAction.RunResult(success=True)

    def _run_nodes(self, context: Context, nodes: str | list[str] | None):
        if not nodes:
            return
        if isinstance(nodes, str):
            nodes = [nodes]
        for node in nodes:
            context.run_task(node)