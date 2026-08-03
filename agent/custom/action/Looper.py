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
        interval = float(param.get("interval", 1.0))
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

            if now - last_log_time >= 5.0:
                remaining = total_duration - elapsed
                print(f"[Looper] 剩余 {remaining:.1f} 秒")
                last_log_time = now

            node_name = nodes[node_index]
            try:
                image = context.tasker.controller.post_screencap().wait().get()
            except Exception as e:
                print(f"[Looper] 截图失败: {e}")
                traceback.print_exc()
                return CustomAction.RunResult(success=False)

            if image is None:
                print("[Looper] 截图为空")
                return CustomAction.RunResult(success=False)

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
            time.sleep(interval)

        print(f"[Looper] 超时 ({total_duration}s)，返回失败")
        return CustomAction.RunResult(success=False)


"""
===== Looper 功能说明 =====

通用轮询器：在指定时间内循环检测 pipeline 节点是否识别成功。
任意节点识别成功 → success=True → Pipeline 走 next
超时全部未识别 → success=False → Pipeline 走 on_error

===== 核心实现 =====

1. 时间循环：在 count 秒内，每隔 interval 秒截图一次。
2. 节点轮询：按 nodes 列表顺序循环检测，每次检测一个节点。
3. 识别方式：调用 context.run_recognition(node_name, image)，使用 pipeline 中已定义的识别配置。
4. 命中即停：任意节点识别成功立即返回 True。

===== 使用教程 =====

参数格式：
{
    "count": 3.0,           // 总时长（秒），超时后返回失败
    "nodes": ["委托完成"],   // 要轮询的 pipeline 节点名列表
    "interval": 1.0         // 每次检测间隔（秒），默认 1.0
}

===== Pipeline JSON 示例 =====

{
    "检测是否完成委托": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "Looper",
        "custom_action_param": {
            "count": 3,
            "nodes": ["委托完成"]
        },
        "next": ["结束计时"],
        "on_error": ["超时处理"]
    }
}

===== 注意 =====

Looper 依赖 pipeline JSON 中已定义的节点（如 "委托完成" 需在 副本通用.json 中定义）。
如果只需检测单一文本，推荐使用 TextWatcher（更简洁，不依赖外部 pipeline 节点定义）。
"""