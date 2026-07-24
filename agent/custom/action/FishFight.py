import json
import time
import numpy as np
from maa.context import Context
from maa.custom_action import CustomAction
 
class FishFight(CustomAction):
    _counter = 0
 
    def run(self, context: Context, argv: CustomAction.RunArg):
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            return CustomAction.RunResult(success=False)
 
        downtarget = param.get("downtarget")
        if not downtarget or len(downtarget) != 2:
            print("[FishFight] 缺少 downtarget")
            return CustomAction.RunResult(success=False)
 
        roi = param.get("roi")
        max_time = param.get("max_time", 60.0)
        wait_time = param.get("wait_time", 20.0)
        threshold_y = param.get("threshold_y", 3)
        duration_scale = param.get("duration_scale", 14)    # 按压时长缩放
        duration_min = param.get("duration_min", 75)       # 最短按压 ms
        duration_max = param.get("duration_max", 700)      # 最长按压 ms
 
        cursor_lower = param.get("cursor_lower", [[90,0,181],[0,0,181]])
        cursor_upper = param.get("cursor_upper", [[179,14,255],[0,14,255]])
        target_lower = param.get("target_lower", [[4,21,82],[14,31,92]])
        target_upper = param.get("target_upper", [[26,51,118],[36,61,128]])
 
        ctrl = context.tasker.controller
        has_detected = False
 
        def do_action(action_type, duration=0):
            FishFight._counter += 1
            entry = f"_fish_{FishFight._counter}"
            node = {
                "recognition": "DirectHit",
                "action": action_type,
                "target": downtarget,
            }
            if action_type == "LongPress":
                node["duration"] = duration
            return context.run_action(entry, pipeline_override={entry: node})
 
        def get_center_y(lower, upper, img):
            if img is None or img.size == 0:
                return None
            if not img.flags.c_contiguous:
                img = np.ascontiguousarray(img)
            entry = "color_match"
            pipeline = {
                entry: {
                    "recognition": "ColorMatch",
                    "method": 40,
                    "lower": lower,
                    "upper": upper,
                    "roi": roi if roi else [0, 0, 0, 0],
                    "connected": False,
                    "count": 1,
                    "order_by": "Area",
                    "index": 0
                }
            }
            try:
                reco = context.run_recognition(entry, img, pipeline)
            except Exception:
                return None
            if reco and reco.hit and reco.box:
                box = reco.box
                return box[1] + box[3] // 2
            return None
 
        def capture():
            img = ctrl.post_screencap().wait().get()
            if img is None or img.size == 0:
                return None
            if not img.flags.c_contiguous:
                img = np.ascontiguousarray(img)
            return img
 
        # 等待钓鱼界面就绪
        print("[FishFight] 等待钓鱼界面出现...")
        start_wait = time.monotonic()
        ready = False
        while time.monotonic() - start_wait < wait_time:
            img = capture()
            if img is not None:
                cy_cursor = get_center_y(cursor_lower, cursor_upper, img)
                cy_target = get_center_y(target_lower, target_upper, img)
                if cy_cursor is not None and cy_target is not None:
                    print(f"[FishFight] 就绪: cursor={cy_cursor}, target={cy_target}")
                    ready = True
                    break
            time.sleep(0.2)
        if not ready:
            print("[FishFight] 等待超时")
            return CustomAction.RunResult(success=False)
 
        # 博弈循环
        print("[FishFight] 开始博弈...")
        start_time = time.monotonic()
        last_offset = 0
 
        while time.monotonic() - start_time < max_time:
            img = capture()
            if img is None:
                time.sleep(0.005)
                continue
 
            cy_cursor = get_center_y(cursor_lower, cursor_upper, img)
            cy_target = get_center_y(target_lower, target_upper, img)
            if cy_cursor is None or cy_target is None:
                time.sleep(0.005)
                continue
 
            has_detected = True
            offset = cy_cursor - cy_target
            abs_offset = abs(offset)
 
            # 计算趋势：正在靠近还是远离
            trend = offset - last_offset
            last_offset = offset
 
            if abs_offset <= threshold_y:
                # 重合区域 → 不操作，保持
                time.sleep(0.005)
                continue
 
            if offset < -threshold_y:
                # 光标在上方 → 按压
                # 距离大按久，距离小按短
                # 如果正在远离（trend < 0），加大力度；正在靠近，减小力度
                base_duration = int(abs_offset * duration_scale)
 
                # 趋势修正
                if trend < -2:
                    # 正在远离，加长
                    base_duration = int(base_duration * 1.3)
                elif trend > 2:
                    # 正在靠近，缩短
                    base_duration = int(base_duration * 0.6)
 
                duration = min(max(base_duration, duration_min), duration_max)
                do_action("LongPress", duration)
 
            elif offset > threshold_y:
                # 光标在下方 → 等重力拉回
                # 如果距离很大，轻点一下帮忙
                if abs_offset > 30:
                    do_action("LongPress", duration_min)
                time.sleep(0.005)
 
        print("[FishFight] 博弈结束")
        return CustomAction.RunResult(success=has_detected)