from maa.custom_action import CustomAction
from maa.context import Context
import sys
import traceback


class VoyageClick(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        try:
            print("[VoyageClick] run() called", flush=True)

            box = argv.box
            if box is None:
                print("[VoyageClick] box is None", flush=True)
                return False

            # 兼容 Rect 对象和 list/tuple
            if hasattr(box, 'x'):
                x, y, w, h = box.x, box.y, box.w, box.h
            elif isinstance(box, (list, tuple)) and len(box) >= 4:
                x, y, w, h = box[0], box[1], box[2], box[3]
            else:
                print(f"[VoyageClick] unexpected box type: {type(box)}", flush=True)
                return False

            # 计算中心点 Y + 15
            center_y = y + h // 2
            click_y = center_y + 15
            fixed_x = 1183

            print(f"[VoyageClick] box=({x},{y},{w},{h}) -> fixed_x={fixed_x}, click_y={click_y} (center_y={center_y}+15)", flush=True)

            # 点击
            click_job = context.tasker.controller.post_click(fixed_x, click_y)
            click_job.wait()
            print("[VoyageClick] click completed", flush=True)

            return True

        except Exception as e:
            print(f"[VoyageClick] EXCEPTION: {e}", flush=True)
            traceback.print_exc(file=sys.stdout)
            return False