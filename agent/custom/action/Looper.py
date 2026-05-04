import json
import time
from maa.context import Context
from maa.custom_action import CustomAction

# MaaStatus 常量（根据 MaaDef.h 定义）
MaaStatus_Succeeded = 3000
MaaStatus_Timeout = 5000   # 等待超时返回的状态（如果 binding 支持）


class Looper(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError:
            print("[Looper] 参数 JSON 解析失败")
            return CustomAction.RunResult(success=False)

        total_rounds = param.get("count", 1)
        nodes = param.get("nodes", [])
        retry_config = param.get("retry", {})
        retry_default = param.get("retry_default", 1)
        node_timeout_ms = param.get("node_timeout", 200)   # 默认 200ms

        if not nodes:
            print("[Looper] 未指定 nodes 列表")
            return CustomAction.RunResult(success=False)

        for round_idx in range(total_rounds):
            print(f"[Looper] 开始第 {round_idx+1}/{total_rounds} 轮")
            node_index = 0
            fail_counts = {}

            while node_index < len(nodes):
                node_name = nodes[node_index]
                max_retry = retry_config.get(node_name, retry_default)
                current_fail = fail_counts.get(node_name, 0)

                print(f"[Looper] 执行节点 {node_name} (超时={node_timeout_ms}ms)")
                task_id = context.run_task(node_name)

                # 等待任务完成，带超时
                timeout_sec = node_timeout_ms / 1000.0
                # 注意：tasker.wait 返回值可能是状态码，也可能抛出异常；这里假设返回状态码
                try:
                    status = context.tasker.wait(task_id, timeout_sec)
                except Exception as e:
                    print(f"[Looper] 等待节点 {node_name} 时异常: {e}")
                    status = MaaStatus_Timeout  # 视为超时

                success = (status == MaaStatus_Succeeded)

                if not success:
                    current_fail += 1
                    fail_counts[node_name] = current_fail
                    print(f"[Looper] 节点 {node_name} 失败/超时，当前失败次数 {current_fail}/{max_retry}")
                    if current_fail < max_retry:
                        # 重试同一节点，不移动索引
                        continue
                    else:
                        print(f"[Looper] 节点 {node_name} 失败次数达到上限，跳过")
                        node_index += 1
                        continue
                else:
                    print(f"[Looper] 节点 {node_name} 执行成功")
                    # 检查是否需要重置循环索引（若该节点有 next 字段，则重置）
                    should_reset = False
                    node_data_json = context.tasker.resource.get_node_data(node_name)
                    if node_data_json:
                        try:
                            node_data = json.loads(node_data_json)
                            next_field = node_data.get("next")
                            if next_field and isinstance(next_field, list) and len(next_field) > 0:
                                should_reset = True
                                print(f"[Looper] 节点 {node_name} 有 next -> 重置循环索引")
                        except json.JSONDecodeError:
                            pass
                    if should_reset:
                        node_index = 0
                        fail_counts = {}
                    else:
                        node_index += 1

        print("[Looper] 所有循环完成")
        return CustomAction.RunResult(success=True)