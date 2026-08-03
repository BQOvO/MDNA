from maa.custom_action import CustomAction
from maa.context import Context
import sys
import traceback


class VoyageClick(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            print("[VoyageClick] run() called", flush=True)

            box = argv.box
            if box is None:
                print("[VoyageClick] box is None", flush=True)
                return CustomAction.RunResult(success=False)

            # 兼容 Rect 对象和 list/tuple
            if hasattr(box, 'x'):
                x, y, w, h = box.x, box.y, box.w, box.h
            elif isinstance(box, (list, tuple)) and len(box) >= 4:
                x, y, w, h = box[0], box[1], box[2], box[3]
            else:
                print(f"[VoyageClick] unexpected box type: {type(box)}", flush=True)
                return CustomAction.RunResult(success=False)

            # 计算中心点 Y + 15
            center_y = y + h // 2
            click_y = center_y + 15
            fixed_x = 1183

            print(f"[VoyageClick] box=({x},{y},{w},{h}) -> fixed_x={fixed_x}, click_y={click_y} (center_y={center_y}+15)", flush=True)

            # 点击
            click_job = context.tasker.controller.post_click(fixed_x, click_y)
            click_job.wait()
            print("[VoyageClick] click completed", flush=True)

            return CustomAction.RunResult(success=True)

        except Exception as e:
            print(f"[VoyageClick] EXCEPTION: {e}", flush=True)
            traceback.print_exc(file=sys.stdout)
            return CustomAction.RunResult(success=False)


"""
===== VoyageClick 功能说明 =====

夜航点击器：根据识别到的目标 box 计算点击位置并执行点击。
专用于夜航手册场景，固定 X 坐标，Y 坐标根据 box 中心偏移。

===== 核心实现 =====

1. 从 argv.box 获取识别结果的位置信息。
2. 兼容 Rect 对象和 list/tuple 两种 box 格式。
3. 计算点击位置：fixed_x=1183, click_y=box_center_y+15。
4. 执行点击。

===== 使用教程 =====

无需额外参数，直接从 pipeline 节点的识别结果中获取 box。
该 action 通常配合 TemplateMatch 或 OCR 识别节点使用。

===== Pipeline JSON 示例 =====

{
    "夜航点击": {
        "recognition": "TemplateMatch",
        "template": ["目标图片.png"],
        "action": "Custom",
        "custom_action": "VoyageClick"
    }
}

===== 类常量配置 =====

fixed_x = 1183    // 固定 X 坐标
Y 偏移 = +15       // 在 box 中心 Y 的基础上加 15 像素
"""