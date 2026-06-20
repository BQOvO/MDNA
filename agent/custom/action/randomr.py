import json
import random
from maa.context import Context
from maa.custom_action import CustomAction

class randomr(CustomAction):
    """
    随机执行当前节点 next 列表中的一个节点。
    概率均匀分布。节点可重复使用，每次进入时都会重新随机选择。
    """
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        node_name = argv.node_name
        # 获取当前节点的原始定义
        node_data_json = context.tasker.resource.get_node_data(node_name)
        if not node_data_json:
            print("[randomr] 无法获取当前节点数据")
            return CustomAction.RunResult(success=False)

        try:
            node_data = json.loads(node_data_json)
        except json.JSONDecodeError:
            print("[randomr] 解析节点数据失败")
            return CustomAction.RunResult(success=False)

        next_list = node_data.get("next", [])
        if not next_list:
            print("[randomr] next 列表为空，无节点可执行")
            return CustomAction.RunResult(success=True)

        # 随机选择一个节点
        selected = random.choice(next_list) if len(next_list) > 1 else next_list[0]
        print(f"[randomr] 从 {next_list} 中选中节点: {selected}")

        # 执行选中的节点（同步）
        context.run_task(selected)

        # 覆盖当前节点的 next 为空，防止 MAA 执行静态 next 列表
        context.override_next(node_name, [])

        return CustomAction.RunResult(success=True)