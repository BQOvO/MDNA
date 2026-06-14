import json
import time
from maa.custom_action import CustomAction
from maa.context import Context

class Looper(CustomAction):
    """
    循环执行一组节点，直到时间耗尽或某个节点成功，且支持任务停止检查。
    参数：
        count (float): 循环持续时间（秒）
        nodes (list[str]): 要循环的节点列表（按顺序无限循环）
    行为：
        - 按顺序循环执行 nodes 中的节点，直到总耗时达到 count 秒。
        - 若某个节点执行成功，则立即结束循环，Looper 返回成功（触发 next）。
        - 若时间耗尽且没有任何节点成功，则 Looper 返回失败（触发 onerror）。
        - 若任务被外部停止（context.tasker.stopping()），则立即返回失败。
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

        start_time = time.monotonic()
        node_index = 0

        while time.monotonic() - start_time < total_duration:
            # 关键改进：检查任务是否被外部停止
            if context.tasker.stopping():
                print("[Looper] 任务被停止，退出循环")
                return CustomAction.RunResult(success=False)

            node_name = nodes[node_index]
            print(f"[Looper] 执行节点: {node_name}")

            # 使用异步 API 并等待结果
            job = context.tasker.post_task(node_name)
            job.wait()
            task_detail = job.get()
            success = task_detail.status.succeeded if task_detail else False

            if success:
                print(f"[Looper] 节点 {node_name} 成功，立即结束循环并返回成功")
                return CustomAction.RunResult(success=True)

            # 移动到下一个节点（循环列表）
            node_index = (node_index + 1) % len(nodes)

        print(f"[Looper] 持续 {total_duration} 秒，未检测到成功节点，返回失败")
        return CustomAction.RunResult(success=False)