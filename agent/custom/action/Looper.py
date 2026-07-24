import json
import time
import traceback
from maa.context import Context
from maa.custom_action import CustomAction

class Looper(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except json.JSONDecodeError:
            print("[Looper] 参数 JSON 解析失败")
            return CustomAction.RunResult(success=False)

        total_duration = float(param.get("count", 1))
        nodes = param.get("nodes", [])
        if not nodes:
            print("[Looper] 未指定 nodes 列表")
            return CustomAction.RunResult(success=False)

        start_time = time.monotonic()
        last_log_time = start_time
        node_index = 0

        while True:
            if context.tasker.stopping:
                print("[Looper] 任务被停止，退出")
                return CustomAction.RunResult(success=False)

            now = time.monotonic()
            elapsed = now - start_time
            if elapsed >= total_duration:
                break

            # 每秒输出一次剩余时间
            if now - last_log_time >= 5.0:
                remaining = total_duration - elapsed
                print(f"[Looper] 剩余 {remaining:.1f} 秒")
                last_log_time = now

            node_name = nodes[node_index]
            # 获取当前截图
            try:
                image = context.tasker.controller.post_screencap().wait().get()
            except Exception as e:
                print(f"[Looper] 截图失败: {e}")
                traceback.print_exc()
                return CustomAction.RunResult(success=False)

            if image is None:
                print("[Looper] 截图为空")
                return CustomAction.RunResult(success=False)

            # 仅执行识别，不执行动作
            try:
                reco_detail = context.run_recognition(node_name, image)
            except Exception as e:
                print(f"[Looper] 识别节点 '{node_name}' 失败: {e}")
                traceback.print_exc()
                return CustomAction.RunResult(success=False)

            success = reco_detail.hit if reco_detail else False

            if success:
                print(f"[Looper] {node_name} 识别成功，结束循环")
                return CustomAction.RunResult(success=True)

            node_index = (node_index + 1) % len(nodes)

        print(f"[Looper] 超时 ({total_duration}s)，返回失败")
        return CustomAction.RunResult(success=False)