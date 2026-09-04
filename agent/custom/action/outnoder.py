import json
import traceback
from maa.custom_action import CustomAction
from maa.context import Context

class Outnoder(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        param_str = argv.custom_action_param
        target_node = None

        try:
            param = json.loads(param_str)
            if isinstance(param, dict):
                target_node = param.get("node")
            else:
                target_node = str(param)
        except json.JSONDecodeError:
            target_node = param_str

        if not target_node:
            print("[Outnoder] 缺少 node 名称")
            return CustomAction.RunResult(success=False)

        if not context.tasker.resource.get_node_data(target_node):
            print(f"[Outnoder] 节点 '{target_node}' 不存在于已加载的 pipeline 中")
            return CustomAction.RunResult(success=False)

        print(f"[Outnoder] 执行外部节点: '{target_node}'")

        try:
            task_detail = context.run_task(target_node)
            if task_detail is not None and task_detail.status is not None:
                success = task_detail.status.succeeded
                if not success:
                    print(f"[Outnoder] 节点 '{target_node}' 执行失败 (status.succeeded=False)")
            elif task_detail is None:
                success = False
                print(f"[Outnoder] run_task('{target_node}') 返回 None（可能原因：嵌套调用冲突 / 框架内部错误）")
            else:
                success = False
                print(f"[Outnoder] run_task('{target_node}') 返回了空 status")
        except Exception as e:
            print(f"[Outnoder] run_task('{target_node}') 抛出异常: {e}")
            traceback.print_exc()
            success = False

        print(f"[Outnoder] 外部节点完成, success={success}")
        return CustomAction.RunResult(success=success)


"""
===== outnoder 功能说明 =====

外部节点执行器：在当前 pipeline 流程中调用另一个 pipeline 节点（支持跨文件引用）。
执行成功后返回该节点的成功/失败状态。

===== 核心实现 =====

1. 参数解析：支持字符串（直接作为节点名）或 {"node": "xxx"} 格式。
2. 节点执行：调用 context.run_task(target_node) 同步执行目标节点。
3. 状态传递：目标节点执行成功 → success=True；失败或异常 → success=False。

===== 使用教程 =====

参数格式：
  字符串: "退出委托门"
  对象:   {"node": "退出委托门"}

===== Pipeline JSON 示例 =====

{
    "退出委托": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "outnoder",
        "custom_action_param": "退出委托门",
        "next": ["后续步骤"]
    }
}

===== 典型用途 =====

- 调用在其他 pipeline 文件中定义的公共节点（如 副本通用.json 中的节点）
- 将复杂流程拆分为可复用的子节点
- 作为流程跳转的桥梁
"""