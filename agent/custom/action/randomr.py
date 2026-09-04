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
        task_detail = context.run_task(selected)
        if task_detail is not None and task_detail.status is not None:
            if not task_detail.status.succeeded:
                print(f"[randomr] 节点 '{selected}' 执行失败")
        else:
            print(f"[randomr] run_task('{selected}') 返回异常")

        # 覆盖当前节点的 next 为空，防止 MAA 执行静态 next 列表
        context.override_next(node_name, [])

        return CustomAction.RunResult(success=True)


"""
===== randomr 功能说明 =====

随机节点选择器：从当前 pipeline 节点的 next 列表中随机选择一个节点执行。
覆盖当前节点的 next 为空，防止 MAA 执行静态 next 列表。

===== 核心实现 =====

1. 获取当前节点定义：通过 context.tasker.resource.get_node_data(node_name) 读取 pipeline JSON。
2. 随机选择：从 next 列表中 random.choice 一个节点。
3. 执行选中节点：context.run_task(selected) 同步执行。
4. 覆盖 next：context.override_next(node_name, []) 清空 next，防止 MAA 再执行原始列表。

===== 使用教程 =====

无需参数，直接在 pipeline 节点中配置多个 next 候选即可。

===== Pipeline JSON 示例 =====

{
    "随机技能": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "randomr",
        "next": [
            "释放技能A",
            "释放技能B",
            "释放技能C"
        ]
    }
}
每次进入该节点时，从技能A/B/C中随机选一个执行。

===== 注意 =====

- next 列表中的节点必须在同一 pipeline 中可访问。
- 每次调用都会重新随机选择，概率均匀分布。
"""