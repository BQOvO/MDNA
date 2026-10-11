import json
import time
import traceback
from maa.context import Context
from maa.custom_action import CustomAction


class SwipeToCenter(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            try:
                raw = argv.custom_action_param
                param = json.loads(raw) if raw else {}
                if not isinstance(param, dict):
                    param = {}
            except json.JSONDecodeError:
                param = {}

            tolerance = int(param.get("tolerance", 5))
            max_iterations = int(param.get("max_iterations", 20))
            swipe_duration = int(param.get("swipe_duration", 200))
            swipe_scale = float(param.get("swipe_scale", 0.25))
            swipe_origin = param.get("swipe_origin", None)
            center_coord = param.get("center", None)

            entry_name = argv.task_detail.entry
            ctrl = context.tasker.controller

            reco_config = self._extract_reco_config(context, entry_name)
            if reco_config is None:
                print("[SwipeToCenter] failed to extract recognition config from node")
                return CustomAction.RunResult(success=False)

            box = argv.box
            if box is None:
                print("[SwipeToCenter] initial detection failed, target not found")
                return CustomAction.RunResult(success=False)

            if hasattr(box, 'x'):
                x, y, w, h = box.x, box.y, box.w, box.h
            elif isinstance(box, (list, tuple)) and len(box) >= 4:
                x, y, w, h = box[0], box[1], box[2], box[3]
            else:
                print(f"[SwipeToCenter] unexpected box type: {type(box)}")
                return CustomAction.RunResult(success=False)

            target_cx = x + w // 2
            target_cy = y + h // 2

            if center_coord is None or len(center_coord) < 2:
                center_x = 640
                center_y = 360
            else:
                center_x = int(center_coord[0])
                center_y = int(center_coord[1])

            if swipe_origin is None or len(swipe_origin) < 2:
                origin_x = 900
                origin_y = 350
            else:
                origin_x = int(swipe_origin[0])
                origin_y = int(swipe_origin[1])

            print(f"[SwipeToCenter] center=({center_x},{center_y}) "
                  f"origin=({origin_x},{origin_y})")

            TEMP_ENTRY = "_swipe_reco"
            pipeline = {TEMP_ENTRY: reco_config}

            for iteration in range(1, max_iterations + 1):
                offset_x = target_cx - center_x
                offset_y = target_cy - center_y

                print(f"[SwipeToCenter] iteration {iteration}/{max_iterations} "
                      f"target=({target_cx},{target_cy}) offset=({offset_x},{offset_y})")

                if abs(offset_x) <= tolerance:
                    print(f"[SwipeToCenter] iteration {iteration}: centered")
                    return CustomAction.RunResult(success=True)

                swipe_px = int(offset_x * swipe_scale)
                swipe_from_x = origin_x
                swipe_from_y = origin_y
                swipe_to_x = origin_x + swipe_px
                swipe_to_y = origin_y
                desc = "left" if swipe_px < 0 else "right"

                print(f"[SwipeToCenter]   swipe horizontal({desc}) origin=({origin_x},{origin_y}) "
                      f"distance={swipe_px}px -> ({swipe_to_x},{swipe_to_y})")

                ctrl.post_swipe(swipe_from_x, swipe_from_y, swipe_to_x, swipe_to_y, swipe_duration).wait()
                time.sleep(0.3)

                image = ctrl.post_screencap().wait().get()
                if image is None:
                    print(f"[SwipeToCenter]   screenshot failed")
                    continue

                reco = context.run_recognition(TEMP_ENTRY, image, pipeline_override=pipeline)
                if reco is None or not reco.hit:
                    print(f"[SwipeToCenter]   recognition failed, target lost")
                    continue

                best = reco.best_result
                if best is None:
                    print(f"[SwipeToCenter]   no best_result")
                    continue

                new_box = None
                if hasattr(best, 'box'):
                    new_box = best.box
                elif isinstance(best, (list, tuple)) and len(best) >= 4:
                    new_box = best

                if new_box is None:
                    print(f"[SwipeToCenter]   cannot extract box from result")
                    continue

                if hasattr(new_box, 'x'):
                    target_cx = new_box.x + new_box.w // 2
                    target_cy = new_box.y + new_box.h // 2
                elif isinstance(new_box, (list, tuple)) and len(new_box) >= 4:
                    target_cx = new_box[0] + new_box[2] // 2
                    target_cy = new_box[1] + new_box[3] // 2
                else:
                    print(f"[SwipeToCenter]   unexpected new_box type")
                    continue

            print(f"[SwipeToCenter] max iterations ({max_iterations}) reached, not centered")
            return CustomAction.RunResult(success=False)

        except Exception as e:
            print(f"[SwipeToCenter] exception: {e}")
            traceback.print_exc()
            return CustomAction.RunResult(success=False)

    def _extract_reco_config(self, context, entry_name):
        node = context.tasker.resource.get_node_data(entry_name)
        if not node:
            print(f"[SwipeToCenter] get_node_data('{entry_name}') returned empty")
            return None
        recognition = node.get("recognition")
        if recognition is None:
            print(f"[SwipeToCenter] node has no recognition field")
            return None
        return {"recognition": recognition}