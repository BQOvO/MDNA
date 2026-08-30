import json
import time
import numpy as np
import cv2
from maa.context import Context
from maa.custom_action import CustomAction


class FishFight(CustomAction):
    """钓鱼博弈控制器：通过灰度轮廓检测鱼标和光标，使用 TouchDown/TouchUp 非阻塞触控实现光标追踪。

    核心思路：
      - 截图 → 灰度二值化 → 找最大轮廓(光标) + 次大轮廓(鱼标)
      - 根据鱼标相对光标的位置，动态决定按住/松开
      - 使用 TouchDown/TouchUp 非阻塞接口，主循环纯检测无阻塞

    控制区划分：
      ┌──────────────┐
      │   上控区      │ ← 鱼标在此 → TouchDown (按住，光标上升)
      ├──────────────┤
      │   中立区      │ ← 鱼标在此 → TouchUp (松开，光标减速)
      ├──────────────┤
      │   下控区      │ ← 鱼标在此 → TouchUp → 等3帧 → TouchDown (脉冲)
      └──────────────┘

    输出：
      - 永远返回 success=True，结果判断由 MAA 流水线后续 OCR 节点处理
    """

    _LOOP_SLEEP = 0.005
    _REFERENCE_HEIGHT = 1080

    _DEFAULT_GRAY_THRESHOLD = 200
    _DEFAULT_BAR_MIN_AREA = 1200
    _DEFAULT_ICON_MIN_AREA = 70
    _DEFAULT_ICON_MAX_AREA = 400
    _DEFAULT_CONTROL_ZONE_RATIO = 0.35
    _DEFAULT_MERGE_GRACE = 0.20
    _DEFAULT_BAR_MISSING_TIMEOUT = 2.5
    _DEFAULT_LOWER_PULSE_WAIT = 200
    _DEFAULT_UPPER_DEBOUNCE = 3
    _DEFAULT_NO_ICON_PULSE_INTERVAL = 80
    _DEFAULT_NEUTRAL_PULSE_INTERVAL = 18
    _DEFAULT_NEUTRAL_PULSE_HOLD = 3

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        """钓鱼博弈主循环。

        参数 (custom_action_param JSON):
            downtarget  - [x, y] 按压坐标 (必需)
            roi         - [x, y, w, h] 鱼条区域 (必需)
            max_time    - 博弈最大时长，默认 75s
            wait_time   - 等待鱼条出现的最大时长，默认 20s

        可选调参:
            gray_threshold       - 二值化阈值，默认 200。越小越敏感，但噪声多
            control_zone_ratio   - 中立区占比，默认 0.35。越大越早松手，防止过冲
            merge_grace          - 鱼标合并宽限时间，默认 0.20s
            bar_missing_timeout  - 鱼条丢失超时，默认 2.5s。超时视为溜鱼结束
            bar_min_area         - 光标最小面积，默认 1200
            icon_min_area        - 鱼标最小面积，默认 70
            icon_max_area        - 鱼标最大面积，默认 400
            lower_pulse_wait     - 下控区脉冲等待帧数，默认 200（约1000ms）。越大光标在下控区松手越久
        """
        try:
            param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            return CustomAction.RunResult(success=False)

        downtarget = param.get("downtarget")
        if not downtarget or len(downtarget) != 2:
            print("[FishFight] 缺少 downtarget")
            return CustomAction.RunResult(success=False)

        roi = param.get("roi")
        if not roi or len(roi) != 4:
            print("[FishFight] 缺少 roi [x,y,w,h]")
            return CustomAction.RunResult(success=False)

        max_time = param.get("max_time", 75.0)
        wait_time = param.get("wait_time", 20.0)

        gray_threshold = param.get("gray_threshold", self._DEFAULT_GRAY_THRESHOLD)
        bar_min_area = param.get("bar_min_area", self._DEFAULT_BAR_MIN_AREA)
        icon_min_area = param.get("icon_min_area", self._DEFAULT_ICON_MIN_AREA)
        icon_max_area = param.get("icon_max_area", self._DEFAULT_ICON_MAX_AREA)
        control_zone_ratio = param.get("control_zone_ratio", self._DEFAULT_CONTROL_ZONE_RATIO)
        merge_grace = param.get("merge_grace", self._DEFAULT_MERGE_GRACE)
        bar_missing_timeout = param.get("bar_missing_timeout", self._DEFAULT_BAR_MISSING_TIMEOUT)
        lower_pulse_wait_frames = param.get("lower_pulse_wait", self._DEFAULT_LOWER_PULSE_WAIT)
        upper_debounce = param.get("upper_debounce", self._DEFAULT_UPPER_DEBOUNCE)
        no_icon_pulse_interval = param.get("no_icon_pulse_interval", self._DEFAULT_NO_ICON_PULSE_INTERVAL)
        neutral_pulse_interval = param.get("neutral_pulse_interval", self._DEFAULT_NEUTRAL_PULSE_INTERVAL)
        neutral_pulse_hold = param.get("neutral_pulse_hold", self._DEFAULT_NEUTRAL_PULSE_HOLD)

        self._context = context
        self._roi = roi
        self._downtarget = downtarget
        self._action_counter = 0

        ctrl = context.tasker.controller

        print("[FishFight] 等待钓鱼界面出现...")
        start_wait = time.monotonic()
        ready = False
        while time.monotonic() - start_wait < wait_time:
            img = self._capture(ctrl)
            if img is None:
                time.sleep(0.2)
                continue
            (has_bar, bar_center, bar_rect, bar_area), (has_icon, icon_center, _) = \
                self._find_bar_and_icon(img, roi, gray_threshold, bar_min_area, icon_min_area, icon_max_area)
            if has_bar and has_icon:
                print(f"[FishFight] 就绪: bar={bar_center}, icon={icon_center}")
                ready = True
                break
            time.sleep(0.2)
        if not ready:
            print("[FishFight] 等待超时, 未检测到鱼条和鱼标")
            return CustomAction.RunResult(success=True)

        print(f"[FishFight] 开始博弈 (TouchDown/TouchUp, zone_ratio={control_zone_ratio:.3f})...")
        start_time = time.monotonic()
        last_log_time = start_time

        is_holding = False
        icon_was_visible = False
        last_known_icon_y_rel = 0.0
        bar_missing_start = None
        merge_start = None
        upper_debounce_cnt = 0
        no_icon_frames = 0
        zone_ratio_locked = False
        neutral_frames = 0

        while time.monotonic() - start_time < max_time:
            img = self._capture(ctrl)
            if img is None:
                time.sleep(self._LOOP_SLEEP)
                continue

            (has_bar, bar_center, bar_rect, bar_area), (has_icon, icon_center, _) = \
                self._find_bar_and_icon(img, roi, gray_threshold, bar_min_area, icon_min_area, icon_max_area)

            if not has_bar:
                if bar_missing_start is None:
                    bar_missing_start = time.monotonic()
                elif time.monotonic() - bar_missing_start >= bar_missing_timeout:
                    print(f"[FishFight] 鱼条丢失超过{bar_missing_timeout}秒 -> 溜鱼结束")
                    return CustomAction.RunResult(success=True)
                if is_holding:
                    self._do_action("TouchUp")
                    is_holding = False
                time.sleep(self._LOOP_SLEEP)
                continue

            bar_missing_start = None

            bar_top = bar_rect[1]
            bar_bottom = bar_rect[3]
            bar_height = bar_bottom - bar_top
            if bar_height <= 0:
                bar_height = 1

            if has_icon and not zone_ratio_locked:
                roi_area = roi[2] * roi[3]
                if bar_area > 0 and roi_area > 0:
                    calibrated = bar_area / roi_area
                    if calibrated > 0.05:
                        control_zone_ratio = max(0.15, calibrated)
                zone_ratio_locked = True
                print(f"[FishFight] 首次识别锁定 zone_ratio={control_zone_ratio:.3f}")

            control_height = int(bar_height * control_zone_ratio)
            control_top = bar_top + control_height
            control_bottom = bar_bottom - control_height

            if has_icon:
                merge_start = None
                no_icon_frames = 0
                icon_y = icon_center[1]
                icon_y_rel = icon_y - bar_center[1]
                last_known_icon_y_rel = icon_y_rel

                if icon_y < control_top:
                    upper_debounce_cnt += 1
                    neutral_frames = 0
                    if upper_debounce_cnt >= upper_debounce and not is_holding:
                        self._do_action("TouchDown")
                        is_holding = True
                elif icon_y > control_bottom:
                    upper_debounce_cnt = 0
                    neutral_frames = 0
                    if is_holding:
                        self._do_action("TouchUp")
                        is_holding = False
                else:
                    upper_debounce_cnt = 0
                    if icon_y_rel < 0:
                        neutral_frames += 1
                        if neutral_frames % neutral_pulse_interval < neutral_pulse_hold:
                            if not is_holding:
                                self._do_action("TouchDown")
                                is_holding = True
                        else:
                            if is_holding:
                                self._do_action("TouchUp")
                                is_holding = False
                    else:
                        neutral_frames = 0
                        if is_holding:
                            self._do_action("TouchUp")
                            is_holding = False

                now = time.monotonic()
                if now - last_log_time >= 2.0:
                    state = "按住" if is_holding else "松开"
                    zone = ""
                    if icon_y < control_top:
                        zone = "上控区"
                    elif icon_y > control_bottom:
                        zone = "下控区"
                    else:
                        zone = "中立区"
                    offset = icon_y - bar_center[1]
                    print(f"[FishFight] icon_y={icon_y} offset={offset:+d} bar=[{bar_top},{bar_bottom}] "
                          f"ctrl=[{control_top},{control_bottom}] {zone} {state} 耗时{now - start_time:.1f}秒")
                    last_log_time = now

            else:
                no_icon_frames += 1
                is_merged = icon_was_visible
                if is_merged:
                    if merge_start is None:
                        merge_start = time.monotonic()
                    if time.monotonic() - merge_start <= merge_grace:
                        upper_debounce_cnt = 0
                        if last_known_icon_y_rel < 0:
                            if not is_holding:
                                self._do_action("TouchDown")
                                is_holding = True
                        else:
                            if is_holding:
                                self._do_action("TouchUp")
                                is_holding = False
                    else:
                        merge_start = None
                        icon_was_visible = False
                else:
                    merge_start = None
                    pulse_phase = no_icon_frames % no_icon_pulse_interval
                    if pulse_phase < 5:
                        if not is_holding:
                            self._do_action("TouchDown")
                            is_holding = True
                    else:
                        if is_holding:
                            self._do_action("TouchUp")
                            is_holding = False

            icon_was_visible = has_icon
            time.sleep(self._LOOP_SLEEP)

        print(f"[FishFight] 博弈超时({max_time}秒) -> 正常结束")
        return CustomAction.RunResult(success=True)

    def _find_bar_and_icon(self, img, roi, gray_threshold, bar_min_area, icon_min_area, icon_max_area):
        """灰度轮廓检测：在 ROI 内同时找光标(最大亮斑)和鱼标(次大亮斑)。

        返回:
            (has_bar, bar_center, bar_rect, bar_area), (has_icon, icon_center, icon_rect)
        """
        if img is None or img.size == 0:
            return (False, None, None, 0.0), (False, None, None)
        if not img.flags.c_contiguous:
            img = np.ascontiguousarray(img)

        frame_height = img.shape[0]
        res_ratio = frame_height / self._REFERENCE_HEIGHT

        x, y, w, h = roi
        x = max(0, min(x, img.shape[1] - 1))
        y = max(0, min(y, img.shape[0] - 1))
        w = max(1, min(w, img.shape[1] - x))
        h = max(1, min(h, img.shape[0] - y))
        roi_img = img[y:y+h, x:x+w]

        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
        _, scene_bin = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(scene_bin, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        blobs = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > icon_min_area * res_ratio ** 2:
                blobs.append({"contour": contour, "area": area})

        blobs.sort(key=lambda b: b["area"], reverse=True)

        has_bar = False
        has_icon = False
        bar_center = None
        bar_rect = None
        bar_area = 0.0
        icon_center = None
        icon_rect = None
        bar_contour = None

        for blob in blobs:
            if blob["area"] > bar_min_area * res_ratio ** 2:
                contour = blob["contour"]
                moments = cv2.moments(contour)
                if moments["m00"] > 0:
                    has_bar = True
                    bar_contour = contour
                    bar_area = blob["area"]
                    bar_center = (
                        int(moments["m10"] / moments["m00"]),
                        int(moments["m01"] / moments["m00"]),
                    )
                    bx, by, bw, bh = cv2.boundingRect(contour)
                    bar_rect = (bx, by, bx + bw, by + bh)
                break

        for blob in blobs:
            if blob["contour"] is bar_contour:
                continue
            if icon_min_area * res_ratio ** 2 < blob["area"] < icon_max_area * res_ratio ** 2:
                contour = blob["contour"]
                moments = cv2.moments(contour)
                if moments["m00"] > 0:
                    has_icon = True
                    icon_center = (
                        int(moments["m10"] / moments["m00"]),
                        int(moments["m01"] / moments["m00"]),
                    )
                    ix, iy, iw, ih = cv2.boundingRect(contour)
                    icon_rect = (ix, iy, ix + iw, iy + ih)
                break

        return (has_bar, bar_center, bar_rect, bar_area), (has_icon, icon_center, icon_rect)

    def _do_action(self, action_type, duration=0):
        """通过 pipeline_override 构造并执行触控动作。

        支持:
            TouchDown  - 非阻塞按下 (contact=0)
            TouchUp    - 非阻塞松开 (contact=0)
            LongPress  - 阻塞长按 (保留兼容，duration 毫秒)
        """
        self._action_counter += 1
        entry = f"_fish_{id(self)}_{self._action_counter}"
        node = {
            "recognition": "DirectHit",
            "action": action_type,
            "target": self._downtarget,
        }
        if action_type == "LongPress":
            node["duration"] = duration
        elif action_type == "TouchDown":
            node["contact"] = 0
        elif action_type == "TouchUp":
            node["contact"] = 0
        return self._context.run_action(entry, pipeline_override={entry: node})

    def _capture(self, ctrl):
        """通过 MaaFramework 控制器截图，返回 numpy BGR 图像。"""
        try:
            img = ctrl.post_screencap().wait().get()
        except Exception:
            return None
        if img is None or img.size == 0:
            return None
        if not img.flags.c_contiguous:
            img = np.ascontiguousarray(img)
        return img


"""
===== FishFight 功能说明 =====

钓鱼博弈控制器：通过灰度轮廓检测识别鱼标和光标，使用 TouchDown/TouchUp 非阻塞触控实现光标追踪。

===== 核心实现 =====

1. 等待阶段：循环截图检测，直到同时识别到光标(最大亮斑)和鱼标(次大亮斑)。
2. 博弈阶段：每 5ms 一帧，灰度二值化 → 找轮廓 → 判断鱼标所在控制区 → 执行 TouchDown/TouchUp。
3. 首次校准：同时识别到鱼标和光标后，用 bar_area/roi_area 一次性锁定 zone_ratio（下限 0.15）。
4. 鱼标合并容错：短暂丢失鱼标时，按 merge_grace 时间内沿用上一次位置继续控制。
5. 鱼条丢失超时：连续丢失鱼条超过 bar_missing_timeout 秒，视为溜鱼结束，返回成功。

===== 控制区逻辑 =====

上控区 (icon_y < control_top):
  → 连续 upper_debounce 帧后 TouchDown，光标上升

中立区 (control_top <= icon_y <= control_bottom):
  → 上半区 (icon_y_rel < 0, 鱼标在光标中心上方): PWM 脉冲，每 N 帧按 hold 帧
  → 下半区 (icon_y_rel >= 0, 鱼标在光标中心下方): TouchUp，光标下坠
  → 防止光标在鱼标下方时继续按压导致过冲

下控区 (icon_y > control_bottom):
  → TouchUp 松开，光标自然下坠

===== Pipeline JSON 示例 =====

{
    "FishFight": {
        "recognition": "DirectHit",
        "action": "Custom",
        "custom_action": "FishFight",
        "custom_action_param": {
            "downtarget": [1146, 588],
            "roi": [1136, 147, 24, 317]
        },
        "next": ["FishFightCheck"]
    },
    "FishFightCheck": {
        "recognition": "OCR",
        "roi": [0, 0, 0, 0],
        "expected": ["钓鱼成功", "鱼跑了"],
        "next": ["FishResultSuccess", "FishResultFail"]
    }
}

===== 调参指南 =====

过冲 (光标超过鱼标太多):
  → 增大 control_zone_ratio (0.35 → 0.40)，让中立区更大，更早松手

欠冲 (光标追不上鱼标):
  → 减小 control_zone_ratio (0.35 → 0.25)，缩小中立区，按住更久

鱼标频繁丢失:
  → 降低 gray_threshold (200 → 180)，提高灰度敏感度
  → 或者增大 merge_grace (0.20 → 0.50)，延长合并宽限时间

错检（把其他亮斑当成鱼标）:
  → 增大 gray_threshold (200 → 220)，减少噪声
  → 调整 icon_min_area / icon_max_area 过滤面积范围

===== 调试版本 =====

需要详细诊断时，改用 FishFightDebug：
  - 保存每帧截图到 fish/ 目录
  - 输出 CSV 帧数据 + JSON 分析报告
  - 自动诊断参数问题并给出调整建议
"""