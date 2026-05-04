import json
import time
import sys
import traceback
from maa.context import Context
from maa.custom_action import CustomAction

# ========== 请根据你的游戏修改以下默认值 ==========
DEFAULT_JOYSTICK_CENTER_X = 210   # 摇杆中心 X 坐标（像素）
DEFAULT_JOYSTICK_CENTER_Y = 540   # 摇杆中心 Y 坐标（像素）
DEFAULT_MOVE_DISTANCE = 60        # 摇杆滑动距离（像素）
DEFAULT_MOVE_DURATION = 50        # 摇杆滑动耗时（毫秒）
# =================================================

class MacroPlayer(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        # 第一步：打印日志，确认动作被调用
        print("[MacroPlayer] run() 开始执行", flush=True)
        try:
            # 解析参数
            param = json.loads(argv.custom_action_param)
            macro_file = param.get("file")
            print(f"[MacroPlayer] 宏文件路径: {macro_file}", flush=True)

            if not macro_file:
                print("[MacroPlayer] 未指定宏文件", flush=True)
                return CustomAction.RunResult(success=False)

            # 读取宏文件
            try:
                with open(macro_file, "r", encoding="utf-8") as f:
                    macro = json.load(f)
                    if isinstance(macro, list):
                        macro = {"steps": macro}
            except Exception as e:
                print(f"[MacroPlayer] 读取宏文件失败: {e}", flush=True)
                traceback.print_exc()
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
                    controller.post_click(x, y).wait()
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
                elif action in ("move_up", "move_down", "move_left", "move_right"):
                    center_x = step.get("center_x", DEFAULT_JOYSTICK_CENTER_X)
                    center_y = step.get("center_y", DEFAULT_JOYSTICK_CENTER_Y)
                    distance = step.get("distance", DEFAULT_MOVE_DISTANCE)
                    duration = step.get("duration", DEFAULT_MOVE_DURATION)

                    if action == "move_up":
                        end_x, end_y = center_x, center_y - distance
                    elif action == "move_down":
                        end_x, end_y = center_x, center_y + distance
                    elif action == "move_left":
                        end_x, end_y = center_x - distance, center_y
                    else:  # move_right
                        end_x, end_y = center_x + distance, center_y

                    controller.post_swipe(center_x, center_y, end_x, end_y, duration).wait()
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