import json
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
            print("outnoder: missing node name")
            return CustomAction.RunResult(success=False)

        print(f"outnoder: executing external node '{target_node}'")

        # 使用 run_task 同步执行（与 Looper 一致）
        task_detail = context.run_task(target_node)
        success = task_detail.status.succeeded if task_detail else False

        print(f"outnoder: external node finished, success={success}")
        return CustomAction.RunResult(success=success)