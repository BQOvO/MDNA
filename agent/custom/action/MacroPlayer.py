import json
import os
import time
import sys
import traceback
from maa.context import Context
from maa.custom_action import CustomAction


def resolve_macro_path(file_path: str) -> str:
    if os.path.isabs(file_path):
        return file_path
    _project_root = os.getcwd()
    return os.path.join(_project_root, "resource", "macros", file_path)

# ========== 请根据你的游戏修改以下默认值 ==========
DEFAULT_JOYSTICK_CENTER_X = 205   # 摇杆中心 X 坐标（像素）
DEFAULT_JOYSTICK_CENTER_Y = 535   # 摇杆中心 Y 坐标（像素）
DEFAULT_MOVE_DISTANCE = 70        # 摇杆滑动距离（像素）
DEFAULT_MOVE_DURATION = 50        # 摇杆滑动耗时（毫秒）
# =================================================

class MacroPlayer(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        print("[MacroPlayer] run() 开始执行", flush=True)
        try:
            param_str = argv.custom_action_param
            # 尝试解析为 JSON
            try:
                param = json.loads(param_str)
            except json.JSONDecodeError:
                # 如果解析失败，则整个字符串视为文件路径
                param = param_str

            steps = None
            macro_file = None

            if isinstance(param, str):
                # 直接是文件路径
                macro_file = param
            elif isinstance(param, dict):
                # 对象格式：优先取 steps，否则取 file
                steps = param.get("steps")
                macro_file = param.get("file")
            else:
                print("[MacroPlayer] 参数格式错误，应为文件路径字符串或对象", flush=True)
                return CustomAction.RunResult(success=False)

            # 获取宏定义
            if steps is not None:
                macro = {"steps": steps}
            elif macro_file:
                resolved_path = resolve_macro_path(macro_file)
                print(f"[MacroPlayer] 从文件读取宏: {resolved_path}", flush=True)
                with open(resolved_path, "r", encoding="utf-8") as f:
                    macro = json.load(f)
                    if isinstance(macro, list):
                        macro = {"steps": macro}
            else:
                print("[MacroPlayer] 未指定 steps 或 file 参数", flush=True)
                return CustomAction.RunResult(success=False)

            controller = context.tasker.controller

            start_time = time.perf_counter()
            abs_time = 0

            def execute_step(step):
                nonlocal abs_time
                delay = step.get("delay", 0)
                abs_time += delay
                target_time = start_time + abs_time / 1000.0
                now = time.perf_counter()
                if now < target_time:
                    time.sleep(target_time - now)

                action = step["action"]
                if action == "click":
                    x, y = step["x"], step["y"]
                    repeat = step.get("repeat", 1)
                    repeat_interval = step.get("repeat_interval", 0)
                    for _ in range(repeat):
                        controller.post_click(x, y).wait()
                        if repeat_interval > 0:
                            time.sleep(repeat_interval / 1000.0)
                elif action == "fly":
                    controller.post_click(1107, 360).wait()
                elif action == "jump":
                    controller.post_click(997, 404).wait()
                elif action == "long_press":
                    x, y = step["x"], step["y"]
                    duration = step.get("duration", 1000)
                    controller.post_swipe(x, y, x, y, duration).wait()
                elif action == "swipe":
                    x1, y1 = step["x1"], step["y1"]
                    x2, y2 = step["x2"], step["y2"]
                    move_dur = step.get("move_duration", 200)
                    hold_dur = step.get("hold_duration", 0)
                    controller.post_swipe(x1, y1, x2, y2, move_dur).wait()
                    if hold_dur > 0:
                        time.sleep(hold_dur / 1000.0)
                elif action in ("up", "down", "left", "right", "move_up", "move_down", "move_left", "move_right"):
                    center_x = step.get("center_x", DEFAULT_JOYSTICK_CENTER_X)
                    center_y = step.get("center_y", DEFAULT_JOYSTICK_CENTER_Y)
                    distance = step.get("distance", DEFAULT_MOVE_DISTANCE)
                    duration = step.get("duration", DEFAULT_MOVE_DURATION)
                    endhold = step.get("endhold", 0)
                    if action in ("up", "move_up"):
                        end_x, end_y = center_x, center_y - distance
                    elif action in ("down", "move_down"):
                        end_x, end_y = center_x, center_y + distance
                    elif action in ("left", "move_left"):
                        end_x, end_y = center_x - distance, center_y
                    else:
                        end_x, end_y = center_x + distance, center_y
                    controller.post_swipe(center_x, center_y, end_x, end_y, duration, endhold).wait()
                elif action == "wait":
                    dur = step.get("duration", 0)
                    time.sleep(dur / 1000.0)
                elif action == "loop":
                    count = step.get("count", 1)
                    for _ in range(count):
                        for sub_step in step.get("steps", []):
                            execute_step(sub_step)
                else:
                    print(f"[MacroPlayer] 未知动作: {action}", flush=True)

            for step in macro.get("steps", []):
                execute_step(step)

            print("[MacroPlayer] 执行完成", flush=True)
            return CustomAction.RunResult(success=True)

        except Exception as e:
            print(f"[MacroPlayer] 未捕获的异常: {e}", flush=True)
            traceback.print_exc()
            return CustomAction.RunResult(success=False)


"""
===== MacroPlayer 功能说明 =====

宏播放器：执行预定义的宏操作序列，支持多种动作类型。
可从 JSON 文件读取宏定义，也可直接在 pipeline 参数中传入 steps 数组。

===== 核心实现 =====

1. 参数解析：支持三种格式 —— 文件路径字符串、{"file": "xxx.json"}、{"steps": [...]}。
2. 文件路径解析：纯文件名自动补全为 resource/macros/ 目录下的路径。
3. 时间轴执行：每个 step 有 delay(ms)，按绝对时间轴顺序执行，保证时序精确。
4. 支持的动作类型见下方。

===== 支持的动作类型 =====

click        - 点击指定坐标           {"action":"click","x":100,"y":200,"repeat":1,"repeat_interval":0}
long_press   - 长按指定坐标           {"action":"long_press","x":100,"y":200,"duration":1000}
swipe        - 滑动                   {"action":"swipe","x1":0,"y1":0,"x2":100,"y2":100,"move_duration":200,"hold_duration":0}
fly          - 点击飞行(1107,360)      {"action":"fly"}
jump         - 点击跳跃(997,404)       {"action":"jump"}
up/down/left/right - 摇杆移动         {"action":"up","distance":70,"duration":50,"endhold":0}
wait         - 等待                   {"action":"wait","duration":1000}
loop         - 循环子步骤             {"action":"loop","count":3,"steps":[...]}

===== 使用教程 =====

用法1：从文件读取
  custom_action_param: "夜航手册60.json"
  自动从 resource/macros/夜航手册60.json 加载。

用法2：内联 steps
  custom_action_param: {
      "steps": [
          {"delay":0,"action":"click","x":500,"y":300},
          {"delay":1000,"action":"swipe","x1":0,"y1":0,"x2":100,"y2":0}
      ]
  }

用法3：指定文件路径
  custom_action_param: {"file": "夜航手册60.json"}

===== Pipeline JSON 示例 =====

{
    "执行宏": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "MacroPlayer",
        "custom_action_param": "夜航手册60.json"
    }
}

===== 类常量配置 =====

DEFAULT_JOYSTICK_CENTER_X = 205    // 摇杆中心 X
DEFAULT_JOYSTICK_CENTER_Y = 535    // 摇杆中心 Y
DEFAULT_MOVE_DISTANCE     = 70     // 摇杆滑动距离（像素）
DEFAULT_MOVE_DURATION     = 50     // 摇杆滑动耗时（毫秒）
"""