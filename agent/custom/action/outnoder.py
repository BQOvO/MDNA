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
            print("outnoder: missing node name")
            return CustomAction.RunResult(success=False)

        print(f"outnoder: executing external node '{target_node}'")

        try:
            task_detail = context.run_task(target_node)
            if task_detail is not None and task_detail.status is not None:
                success = task_detail.status.succeeded
            else:
                success = False
                print(f"outnoder: run_task returned None or status is None for node '{target_node}'")
        except Exception as e:
            print(f"outnoder: run_task failed for node '{target_node}': {e}")
            traceback.print_exc()
            success = False

        print(f"outnoder: external node finished, success={success}")
        return CustomAction.RunResult(success=success)