import json
import time
from maa.context import Context
from maa.custom_action import CustomAction

class Looper(CustomAction):
    """
    循环执行一组节点，持续指定时间（秒），支持中断重置。

    参数：
        count: int                  # 循环持续时间（秒），例如 6 表示循环 6 秒
        nodes: list[str]            # 要循环的节点列表（按顺序无限循环）
        reset_nodes: list[str]      # 中断节点，成功时立即结束循环并执行 Looper 的 next

    行为：
        - 顺序执行 nodes 中的节点，无论成功失败都继续下一个（无限循环，循环列表直到时间用完）。
        - 若某个节点成功且属于 reset_nodes，则立即返回成功，MAA 执行 Looper 的 next。
        - 否则，持续循环直到总耗时达到 count 秒，然后返回成功，MAA 执行 Looper 的 next。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError:
            print("[Looper] 参数 JSON 解析失败")
            return CustomAction.RunResult(success=False)

        total_duration = param.get("count", 1)
        try:
            total_duration = float(total_duration)
        except (ValueError, TypeError):
            total_duration = 1.0

        nodes = param.get("nodes", [])
        if not nodes:
            print("[Looper] 未指定 nodes 列表")
            return CustomAction.RunResult(success=False)

        reset_nodes = param.get("reset_nodes", [])

        start_time = time.monotonic()
        node_index = 0

        while time.monotonic() - start_time < total_duration:
            node_name = nodes[node_index]
            print(f"[Looper] 执行节点: {node_name}")
            task_detail = context.run_task(node_name)
            success = task_detail.status.succeeded if task_detail else False

            if success:
                print(f"[Looper] {node_name} 成功")
                if node_name in reset_nodes:
                    print(f"[Looper] 命中重置节点 {node_name}，立即结束循环并执行 Looper 的 next")
                    return CustomAction.RunResult(success=True)
            else:
                print(f"[Looper] {node_name} 失败，继续下一个节点")

            # 移动到下一个节点（循环列表）
            node_index = (node_index + 1) % len(nodes)

        print(f"[Looper] 持续 {total_duration} 秒时间到，结束循环")
        return CustomAction.RunResult(success=True)