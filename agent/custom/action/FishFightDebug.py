# ═══════════════════════════════════════════════════════════════════════
#  FishFightDebug - 钓鱼博弈调试版
#  基于灰度轮廓检测，专为参数调优设计
#
#  用法：
#    1. 修改下方 DEBUG_PARAMS 中的参数
#    2. 跑一次 action
#    3. 看终端输出的诊断报告 + 参数建议
#    4. 按建议改参数，再跑
#    5. 重复直到成功率满意
#    6. 把最终参数填到 FishFight.py 的 custom_action_param 里
#
#  截图保存在 debug/screenshots/ 目录下
#  TXT 报告保存在 debug/fishfight_report.txt
#  历史数据保存在 debug/fishfight_results.json 和 .csv
# ═══════════════════════════════════════════════════════════════════════

import json
import time
import os
import csv
from datetime import datetime
from pathlib import Path
import numpy as np
import cv2
from maa.context import Context
from maa.custom_action import CustomAction


# ═══════════════════════════════════════════════════════════════════════
# ★★★ 调试参数区 - 直接在这里改数值，改完就跑 ★★★
# ═══════════════════════════════════════════════════════════════════════
DEBUG_PARAMS = {
    # ── 灰度检测 ──
    "gray_threshold": 140,

    # 鱼条最小面积 (基于1080p，自动按分辨率缩放)
    "bar_min_area": 1200,

    # 鱼标面积范围 (基于1080p，自动缩放)
    "icon_min_area": 70,
    "icon_max_area": 400,

    # ── 控制参数 ──
    # 控制区初始占比，运行时每帧动态计算为 bar_area / roi_area
    "control_zone_ratio": 0.35,

    # 动态按压时长：duration = min_hold + hold_k * |offset|，上限 max_hold
    # offset = 鱼标Y - 光标中心Y（像素），距离越远按得越久
    "min_hold_duration": 10,
    "max_hold_duration": 1050,
    "hold_k": 6.7,

    # 鱼标合并宽限时间 (秒)
    "merge_grace": 0.05,

    # 鱼条丢失超时 (秒)
    "bar_missing_timeout": 5.0,

    # ── 超时 ──
    "max_time": 60.0,
    "wait_time": 20.0
}

# ── 截图设置 ──
SAVE_SCREENSHOTS = True
SCREENSHOT_DIR = Path("debug/screenshots")
SAVE_EVERY_N_FRAMES = 3
MAX_SCREENSHOTS_PER_RUN = 200

# ── 结果保存 ──
RESULTS_DIR = Path("debug")
RESULTS_FILE = RESULTS_DIR / "fishfight_results.json"
RESULTS_CSV = RESULTS_DIR / "fishfight_results.csv"
REPORT_TXT = RESULTS_DIR / "fishfight_report.txt"

# ═══════════════════════════════════════════════════════════════════════


class FishFightDebug(CustomAction):
    _LOOP_SLEEP = 0.003
    _REFERENCE_HEIGHT = 1080

    def run(self, context: Context, argv: CustomAction.RunArg) -> CustomAction.RunResult:
        try:
            pipeline_param = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        except Exception:
            return CustomAction.RunResult(success=False)

        downtarget = pipeline_param.get("downtarget")
        if not downtarget or len(downtarget) != 2:
            print("[FishFightDebug] 缺少 downtarget")
            return CustomAction.RunResult(success=False)

        roi = pipeline_param.get("roi")
        if not roi or len(roi) != 4:
            print("[FishFightDebug] 缺少 roi [x,y,w,h]")
            return CustomAction.RunResult(success=False)

        gray_threshold = DEBUG_PARAMS["gray_threshold"]
        bar_min_area = DEBUG_PARAMS["bar_min_area"]
        icon_min_area = DEBUG_PARAMS["icon_min_area"]
        icon_max_area = DEBUG_PARAMS["icon_max_area"]
        control_zone_ratio = DEBUG_PARAMS["control_zone_ratio"]
        min_hold_duration = DEBUG_PARAMS["min_hold_duration"]
        max_hold_duration = DEBUG_PARAMS["max_hold_duration"]
        hold_k = DEBUG_PARAMS["hold_k"]
        merge_grace = DEBUG_PARAMS["merge_grace"]
        bar_missing_timeout = DEBUG_PARAMS["bar_missing_timeout"]
        max_time = DEBUG_PARAMS["max_time"]
        wait_time = DEBUG_PARAMS["wait_time"]

        self._context = context
        self._roi = roi
        self._downtarget = downtarget
        self._action_counter = 0

        ctrl = context.tasker.controller

        # ── 数据采集 ──
        frame_data = []
        bar_hits = 0
        bar_misses = 0
        icon_hits = 0
        icon_misses = 0
        merge_events = 0
        bar_lost_events = 0
        overshoot_events = []
        undershoot_events = []
        press_count = 0
        osc_transitions = 0
        last_zone = None
        screenshot_count = 0
        frame_index = 0

        def record_frame(ts, has_bar, has_icon, is_merged, icon_y, bar_cy, offset,
                         bar_top, bar_bottom, ctrl_top, ctrl_bottom,
                         action, duration, zone):
            frame_data.append({
                "frame": len(frame_data),
                "t": round(ts, 3),
                "has_bar": has_bar,
                "has_icon": has_icon,
                "is_merged": is_merged,
                "icon_y": icon_y,
                "bar_center_y": bar_cy,
                "offset": offset,
                "bar_top": bar_top,
                "bar_bottom": bar_bottom,
                "ctrl_top": ctrl_top,
                "ctrl_bottom": ctrl_bottom,
                "action": action,
                "duration": duration,
                "zone": zone,
            })

        # ── 等待就绪 ──
        print("[FishFightDebug] 等待钓鱼界面出现...")
        start_wait = time.monotonic()
        ready = False
        while time.monotonic() - start_wait < wait_time:
            img = self._capture(ctrl)
            if img is None:
                time.sleep(0.2)
                continue
            (has_bar, bar_center, bar_rect, bar_area), (has_icon, icon_center, _) = \
                self._find_bar_and_icon(img, roi, gray_threshold, bar_min_area, icon_min_area, icon_max_area)
            if has_bar:
                bar_hits += 1
            else:
                bar_misses += 1
            if has_icon:
                icon_hits += 1
            else:
                icon_misses += 1
            if has_bar and has_icon:
                print(f"[FishFightDebug] 就绪: bar_center={bar_center}, icon_center={icon_center}")
                ready = True
                break
            time.sleep(0.2)

        if not ready:
            print(f"[FishFightDebug] 等待超时, 未检测到鱼条和鱼标")
            self._print_wait_diag(bar_hits, bar_misses, icon_hits, icon_misses)
            return CustomAction.RunResult(success=False)

        # ── 主循环 ──
        print(f"[FishFightDebug] 开始博弈 (TouchDown/TouchUp 非阻塞模式, "
              f"zone_ratio={control_zone_ratio:.3f}, gray_th={gray_threshold})...")
        start_time = time.monotonic()
        fight_start_time = None
        success = False
        fail_reason = ""
        is_holding = False
        icon_was_visible = False
        last_known_icon_y_rel = 0.0
        bar_missing_start = None
        merge_start = None
        last_zone = None

        total_hold_ms = 0
        total_release_frames = 0
        hold_state_changes = 0
        duration_list = []
        hold_start_time = 0.0
        lower_pulse_wait = 0

        def fight_elapsed():
            ref = fight_start_time if fight_start_time is not None else start_time
            return time.monotonic() - ref

        while time.monotonic() - start_time < max_time:
            frame_index += 1
            img = self._capture(ctrl)
            if img is None:
                time.sleep(self._LOOP_SLEEP)
                continue

            (has_bar, bar_center, bar_rect, bar_area), (has_icon, icon_center, icon_rect) = \
                self._find_bar_and_icon(img, roi, gray_threshold, bar_min_area, icon_min_area, icon_max_area)

            if has_bar:
                bar_hits += 1
            else:
                bar_misses += 1
            if has_icon:
                icon_hits += 1
            else:
                icon_misses += 1

            if fight_start_time is None and has_bar and has_icon:
                fight_start_time = time.monotonic()
                print(f"[FishFightDebug] 首次同时检测到鱼条+鱼标，开始计时 "
                      f"(距节点启动 {fight_start_time - start_time:.1f}s)")

            if not has_bar:
                bar_lost_events += 1
                if bar_missing_start is None:
                    bar_missing_start = time.monotonic()
                elif time.monotonic() - bar_missing_start >= bar_missing_timeout:
                    fail_reason = f"鱼条丢失超过{bar_missing_timeout}秒"
                    break
                if is_holding:
                    self._do_action("TouchUp")
                    hold_ms = (time.monotonic() - hold_start_time) * 1000
                    total_hold_ms += hold_ms
                    duration_list.append(hold_ms)
                    is_holding = False
                    hold_state_changes += 1
                record_frame(fight_elapsed(),
                             False, False, False, None, None, None,
                             None, None, None, None,
                             "none", 0, "bar_lost")
                if SAVE_SCREENSHOTS and screenshot_count < MAX_SCREENSHOTS_PER_RUN and frame_index % SAVE_EVERY_N_FRAMES == 0:
                    self._save_frame_screenshot(img, roi, None, None, None, None,
                                                None, None, None, "bar_lost",
                                                screenshot_count, frame_index)
                    screenshot_count += 1
                time.sleep(self._LOOP_SLEEP)
                continue

            bar_missing_start = None

            bar_top = bar_rect[1]
            bar_bottom = bar_rect[3]
            bar_height = bar_bottom - bar_top
            if bar_height <= 0:
                bar_height = 1

            roi_area = roi[2] * roi[3]
            if bar_area > 0 and roi_area > 0:
                new_ratio = bar_area / roi_area
                if abs(new_ratio - control_zone_ratio) / max(control_zone_ratio, 0.001) > 0.1:
                    control_zone_ratio = new_ratio

            control_height = int(bar_height * control_zone_ratio)
            control_top = bar_top + control_height
            control_bottom = bar_bottom - control_height

            action = "none"
            duration = 0
            zone = "neutral"
            is_merged = False
            icon_y = None
            offset = None

            if has_icon:
                merge_start = None
                icon_y = icon_center[1]
                icon_y_rel = icon_y - bar_center[1]
                last_known_icon_y_rel = icon_y_rel
                offset = icon_y_rel

                if icon_y < control_top:
                    zone = "upper"
                    lower_pulse_wait = 0
                    if not is_holding:
                        self._do_action("TouchDown")
                        hold_start_time = time.monotonic()
                        is_holding = True
                        hold_state_changes += 1
                    action = "press"
                elif icon_y > control_bottom:
                    zone = "lower"
                    if is_holding:
                        self._do_action("TouchUp")
                        hold_ms = (time.monotonic() - hold_start_time) * 1000
                        total_hold_ms += hold_ms
                        duration_list.append(hold_ms)
                        is_holding = False
                        hold_state_changes += 1
                        lower_pulse_wait = 3
                    elif lower_pulse_wait > 0:
                        lower_pulse_wait -= 1
                        if lower_pulse_wait == 0 and not is_holding:
                            self._do_action("TouchDown")
                            hold_start_time = time.monotonic()
                            is_holding = True
                            hold_state_changes += 1
                    action = "press" if is_holding else "release"
                else:
                    zone = "neutral"
                    if is_holding:
                        self._do_action("TouchUp")
                        hold_ms = (time.monotonic() - hold_start_time) * 1000
                        total_hold_ms += hold_ms
                        duration_list.append(hold_ms)
                        is_holding = False
                        hold_state_changes += 1
                    action = "release"

            else:
                is_merged = icon_was_visible
                if is_merged:
                    merge_events += 1
                    if merge_start is None:
                        merge_start = time.monotonic()
                    if time.monotonic() - merge_start <= merge_grace:
                        if last_known_icon_y_rel < 0:
                            if not is_holding:
                                self._do_action("TouchDown")
                                hold_start_time = time.monotonic()
                                is_holding = True
                                hold_state_changes += 1
                            action = "press"
                        else:
                            if is_holding:
                                self._do_action("TouchUp")
                                hold_ms = (time.monotonic() - hold_start_time) * 1000
                                total_hold_ms += hold_ms
                                duration_list.append(hold_ms)
                                is_holding = False
                                hold_state_changes += 1
                            action = "release"
                        zone = "merge"
                    else:
                        merge_start = None
                        icon_was_visible = False
                        zone = "merge_expired"
                else:
                    merge_start = None
                    zone = "no_icon"

            if zone != last_zone and last_zone is not None:
                if (zone == "upper" and last_zone == "lower") or (zone == "lower" and last_zone == "upper"):
                    osc_transitions += 1
            if zone in ("upper", "lower", "neutral"):
                last_zone = zone

            if offset is not None:
                ft = fight_elapsed()
                if offset < 0:
                    overshoot_events.append({"offset": abs(offset), "t": round(ft, 3)})
                elif offset > 0:
                    undershoot_events.append({"offset": abs(offset), "t": round(ft, 3)})

            if action == "press":
                press_count += 1
            elif action == "release":
                total_release_frames += 1

            icon_was_visible = has_icon

            record_frame(fight_elapsed(),
                         True, has_icon, is_merged, icon_y, bar_center[1] if has_icon else None, offset,
                         bar_top, bar_bottom, control_top, control_bottom,
                         action, duration, zone)

            if SAVE_SCREENSHOTS and screenshot_count < MAX_SCREENSHOTS_PER_RUN and frame_index % SAVE_EVERY_N_FRAMES == 0:
                self._save_frame_screenshot(
                    img, roi, bar_rect, icon_rect if has_icon else None,
                    bar_center, control_top, control_bottom,
                    offset, zone, action, screenshot_count, frame_index,
                )
                screenshot_count += 1

            time.sleep(self._LOOP_SLEEP)

        if is_holding:
            hold_ms = (time.monotonic() - hold_start_time) * 1000
            total_hold_ms += hold_ms
            duration_list.append(hold_ms)

        elapsed = time.monotonic() - start_time

        # ── 诊断 ──
        analysis = self._analyze(
            frame_data, overshoot_events, undershoot_events,
            bar_hits, bar_misses, icon_hits, icon_misses,
            merge_events, bar_lost_events, osc_transitions,
            press_count, total_hold_ms, total_release_frames, hold_state_changes,
            duration_list, elapsed, success, fail_reason,
            gray_threshold, bar_min_area, icon_min_area, icon_max_area,
            control_zone_ratio, min_hold_duration, max_hold_duration, hold_k,
            merge_grace, bar_missing_timeout, max_time,
        )

        report_text = self._print_report(
            success, fail_reason, elapsed, frame_index,
            bar_hits, bar_misses, icon_hits, icon_misses,
            merge_events, bar_lost_events, osc_transitions,
            overshoot_events, undershoot_events,
            press_count, total_hold_ms, total_release_frames, hold_state_changes,
            duration_list, screenshot_count,
            gray_threshold, control_zone_ratio,
            min_hold_duration, max_hold_duration, hold_k,
            merge_grace, bar_missing_timeout,
            analysis,
        )

        self._save_txt_report(report_text)

        result = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "fail_reason": fail_reason,
            "elapsed": round(elapsed, 1),
            "total_frames": frame_index,
            "press_count": press_count,
            "total_hold_ms": total_hold_ms,
            "total_release_frames": total_release_frames,
            "hold_state_changes": hold_state_changes,
            "avg_hold_duration": round(total_hold_ms / max(press_count, 1), 1),
            "bar_hit_rate": f"{100 * bar_hits // max(bar_hits + bar_misses, 1)}%",
            "icon_hit_rate": f"{100 * icon_hits // max(icon_hits + icon_misses, 1)}%",
            "merge_events": merge_events,
            "bar_lost_events": bar_lost_events,
            "osc_transitions": osc_transitions,
            "max_overshoot": max([e["offset"] for e in overshoot_events]) if overshoot_events else 0,
            "max_undershoot": max([e["offset"] for e in undershoot_events]) if undershoot_events else 0,
            "avg_overshoot": round(sum(e["offset"] for e in overshoot_events) / max(len(overshoot_events), 1), 1),
            "params_used": {
                "gray_threshold": gray_threshold,
                "bar_min_area": bar_min_area,
                "icon_min_area": icon_min_area,
                "icon_max_area": icon_max_area,
                "control_zone_ratio": control_zone_ratio,
                "min_hold_duration": min_hold_duration,
                "max_hold_duration": max_hold_duration,
                "hold_k": hold_k,
                "merge_grace": merge_grace,
                "bar_missing_timeout": bar_missing_timeout,
            },
            "recommendations": analysis,
        }
        self._save_results(result)

        return CustomAction.RunResult(success=True)

    # ═══════════════════════════════════════════════════════════════
    #  分析引擎
    # ═══════════════════════════════════════════════════════════════

    def _analyze(self, frame_data, overshoots, undershoots,
                 bar_hits, bar_misses, icon_hits, icon_misses,
                 merge_events, bar_lost_events, osc_transitions,
                 press_count, total_hold_ms, total_release_frames, hold_state_changes,
                 duration_list, elapsed, success, fail_reason,
                 gray_threshold, bar_min_area, icon_min_area, icon_max_area,
                 control_zone_ratio, min_hold_duration, max_hold_duration, hold_k,
                 merge_grace, bar_missing_timeout, max_time):
        recs = []

        bar_total = bar_hits + bar_misses
        icon_total = icon_hits + icon_misses
        bar_rate = bar_hits / max(bar_total, 1)
        icon_rate = icon_hits / max(icon_total, 1)

        if bar_rate < 0.5:
            recs.append({
                "priority": "★★★ 高",
                "param": "gray_threshold",
                "current": str(gray_threshold),
                "suggested": str(max(100, gray_threshold - 20)),
                "reason": f"鱼条命中率仅 {bar_rate:.0%}，灰度阈值可能太高，建议降低",
            })
        if bar_rate < 0.3:
            recs.append({
                "priority": "★★★ 高",
                "param": "roi (pipeline参数)",
                "current": "当前值",
                "suggested": "重新量取",
                "reason": f"鱼条命中率极低 ({bar_rate:.0%})，ROI 区域可能没有准确框住鱼条",
            })

        if icon_rate < 0.5 and bar_rate >= 0.7:
            recs.append({
                "priority": "★★☆ 中",
                "param": "icon_min_area / icon_max_area",
                "current": f"{icon_min_area} / {icon_max_area}",
                "suggested": f"{max(30, icon_min_area - 20)} / {icon_max_area + 50}",
                "reason": f"鱼标命中率仅 {icon_rate:.0%} (鱼条正常 {bar_rate:.0%})，鱼标面积范围可能不合适",
            })

        if icon_rate < 0.3 and bar_rate >= 0.7:
            recs.append({
                "priority": "★★☆ 中",
                "param": "gray_threshold",
                "current": str(gray_threshold),
                "suggested": str(max(100, gray_threshold - 30)),
                "reason": f"鱼标命中率极低 ({icon_rate:.0%})，灰度阈值可能太高导致鱼标轮廓丢失",
            })

        total_frames = len(frame_data)
        if total_frames > 0 and merge_events / total_frames > 0.3:
            recs.append({
                "priority": "★★☆ 中",
                "param": "merge_grace",
                "current": str(merge_grace),
                "suggested": str(round(merge_grace * 1.5, 2)),
                "reason": f"合并事件占比 {merge_events / total_frames:.0%}，鱼标频繁消失，建议增大合并宽限时间",
            })

        if bar_lost_events > 10:
            recs.append({
                "priority": "★★☆ 中",
                "param": "bar_missing_timeout",
                "current": str(bar_missing_timeout),
                "suggested": str(round(bar_missing_timeout * 1.5, 1)),
                "reason": f"鱼条丢失 {bar_lost_events} 次，可能提前误判结束，建议增大鱼条丢失超时",
            })

        if overshoots:
            max_os = max(e["offset"] for e in overshoots)
            avg_os = sum(e["offset"] for e in overshoots) / len(overshoots)

            if avg_os > 30:
                new_ratio = round(control_zone_ratio * 1.5, 2)
                recs.append({
                    "priority": "★★★ 高",
                    "param": "control_zone_ratio",
                    "current": str(control_zone_ratio),
                    "suggested": str(min(0.45, new_ratio)),
                    "reason": f"平均过冲 {avg_os:.0f}px (最大 {max_os}px)，中立区太小，增大 control_zone_ratio 可吸收过冲",
                })

        if undershoots and not overshoots:
            max_us = max(e["offset"] for e in undershoots)
            avg_us = sum(e["offset"] for e in undershoots) / len(undershoots)

            if avg_us > 20:
                new_ratio = round(control_zone_ratio * 0.7, 2)
                recs.append({
                    "priority": "★★★ 高",
                    "param": "control_zone_ratio",
                    "current": str(control_zone_ratio),
                    "suggested": str(max(0.1, new_ratio)),
                    "reason": f"平均欠冲 {avg_us:.0f}px (最大 {max_us}px)，光标追不上，缩小中立区让系统更早开始按压",
                })

        if osc_transitions > 5 and total_frames > 0:
            osc_rate = osc_transitions / (total_frames / 10)
            if osc_rate > 1.0:
                new_ratio = min(0.45, round(control_zone_ratio * 1.3, 2))
                recs.append({
                    "priority": "★★★ 高",
                    "param": "control_zone_ratio",
                    "current": str(control_zone_ratio),
                    "suggested": str(new_ratio),
                    "reason": f"检测到 {osc_transitions} 次上下控制区切换 (振荡)，增大中立区可减少来回摆动",
                })

        if press_count > 0:
            hold_pct = total_hold_ms / max(elapsed * 1000, 1) * 100

            if hold_pct < 15 and press_count > 5:
                new_ratio = max(0.1, round(control_zone_ratio * 0.7, 2))
                recs.append({
                    "priority": "★★★ 高",
                    "param": "control_zone_ratio",
                    "current": str(control_zone_ratio),
                    "suggested": str(new_ratio),
                    "reason": f"按压时间仅占 {hold_pct:.1f}%，光标几乎没在追，缩小中立区让系统更频繁按压",
                })

            if hold_pct > 80:
                new_ratio = min(0.45, round(control_zone_ratio * 1.4, 2))
                recs.append({
                    "priority": "★★☆ 中",
                    "param": "control_zone_ratio",
                    "current": str(control_zone_ratio),
                    "suggested": str(new_ratio),
                    "reason": f"按压时间占比 {hold_pct:.1f}%，几乎一直在按，增大中立区",
                })

        if not success and fail_reason and "鱼条丢失" in fail_reason:
            recs.append({
                "priority": "★★☆ 中",
                "param": "bar_missing_timeout",
                "current": str(bar_missing_timeout),
                "suggested": str(round(bar_missing_timeout * 2, 1)),
                "reason": f"因鱼条丢失超时结束，可能博弈还在进行中，建议大幅增大超时",
            })

        if success and elapsed > 30:
            if overshoots:
                avg_os = sum(e["offset"] for e in overshoots) / len(overshoots)
                new_ratio = round(control_zone_ratio * 1.2, 2)
                recs.append({
                    "priority": "★☆☆ 低",
                    "param": "control_zone_ratio",
                    "current": str(control_zone_ratio),
                    "suggested": str(min(0.45, new_ratio)),
                    "reason": f"成功但耗时 {elapsed:.0f}秒，过冲平均 {avg_os:.0f}px，增大中立区可加快收敛",
                })

        if not recs:
            recs.append({
                "priority": "---",
                "param": "当前参数",
                "current": "-",
                "suggested": "保持不变",
                "reason": "本次运行数据正常，建议再跑 2~3 次确认稳定性",
            })

        return recs

    # ═══════════════════════════════════════════════════════════════
    #  报告打印
    # ═══════════════════════════════════════════════════════════════

    def _print_report(self, success, fail_reason, elapsed, total_frames,
                      bar_hits, bar_misses, icon_hits, icon_misses,
                      merge_events, bar_lost_events, osc_transitions,
                      overshoots, undershoots,
                      press_count, total_hold_ms, total_release_frames, hold_state_changes,
                      duration_list, screenshot_count,
                      gray_threshold, control_zone_ratio,
                      min_hold_duration, max_hold_duration, hold_k,
                      merge_grace, bar_missing_timeout,
                      analysis):
        bar_total = bar_hits + bar_misses
        icon_total = icon_hits + icon_misses

        lines = []

        def emit(s):
            print(s)
            lines.append(s)

        emit(f"\n{'=' * 65}")
        emit(f"  FishFightDebug 诊断报告 (TouchDown/TouchUp 非阻塞)")
        emit(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        emit(f"{'=' * 65}")

        emit(f"\n  ── 基本结果 ──")
        status = "成功" if success else f"失败"
        if fail_reason:
            status += f" ({fail_reason})"
        emit(f"    结果:     {status}")
        emit(f"    耗时:     {elapsed:.1f} 秒")
        emit(f"    总帧数:   {total_frames}")
        emit(f"    按压次数: {press_count}")
        if press_count > 0:
            avg_dur = total_hold_ms / press_count
            hold_pct = total_hold_ms / max(elapsed * 1000, 1) * 100
            emit(f"    总按压时长: {total_hold_ms:.0f} ms ({hold_pct:.1f}% 占比)")
            emit(f"    平均按压时长: {avg_dur:.0f} ms/次")
            emit(f"    状态切换: {hold_state_changes} 次")
            if duration_list:
                emit(f"    按压时长范围: {min(duration_list)} ~ {max(duration_list)} ms")
        if SAVE_SCREENSHOTS:
            emit(f"    截图数:   {screenshot_count} 张 (保存在 {SCREENSHOT_DIR})")

        emit(f"\n  ── 检测命中率 ──")
        emit(f"    鱼条:     {bar_hits}/{bar_total} ({100 * bar_hits // max(bar_total, 1)}%)")
        emit(f"    鱼标:     {icon_hits}/{icon_total} ({100 * icon_hits // max(icon_total, 1)}%)")
        if bar_hits / max(bar_total, 1) < 0.5:
            emit(f"    !! 鱼条命中率过低，检查 roi 或 gray_threshold")
        if icon_hits / max(icon_total, 1) < 0.5:
            emit(f"    !! 鱼标命中率过低，检查 icon_min_area / icon_max_area")

        emit(f"\n  ── 事件统计 ──")
        emit(f"    合并事件: {merge_events} 次 (鱼标短暂消失)")
        emit(f"    鱼条丢失: {bar_lost_events} 次")
        emit(f"    振荡切换: {osc_transitions} 次 (上下控制区来回切换)")

        emit(f"\n  ── 偏移分析 ──")
        if overshoots:
            vals = [e["offset"] for e in overshoots]
            emit(f"    过冲次数: {len(overshoots)}")
            emit(f"    过冲最大值: {max(vals):.0f} px")
            emit(f"    过冲平均值: {sum(vals) / len(vals):.0f} px")
            emit(f"    过冲中位数: {sorted(vals)[len(vals) // 2]:.0f} px")
            early = [e for e in overshoots if e["t"] < elapsed * 0.3]
            late = [e for e in overshoots if e["t"] > elapsed * 0.7]
            if early:
                emit(f"    前期过冲: {len(early)} 次 (前30%时间)")
            if late:
                emit(f"    后期过冲: {len(late)} 次 (后30%时间)")
        else:
            emit(f"    过冲: 无")

        if undershoots:
            vals = [e["offset"] for e in undershoots]
            emit(f"    欠冲次数: {len(undershoots)}")
            emit(f"    欠冲最大值: {max(vals):.0f} px")
            emit(f"    欠冲平均值: {sum(vals) / len(vals):.0f} px")
        else:
            emit(f"    欠冲: 无")

        emit(f"\n  ── 当前参数 ──")
        emit(f"    控制模式:              TouchDown/TouchUp (非阻塞)")
        emit(f"    gray_threshold:        {gray_threshold}")
        emit(f"    control_zone_ratio:    {control_zone_ratio}")
        emit(f"    merge_grace:           {merge_grace} s")
        emit(f"    bar_missing_timeout:   {bar_missing_timeout} s")

        emit(f"\n{'=' * 65}")
        emit(f"  参数调整建议")
        emit(f"{'=' * 65}")

        if analysis:
            for i, rec in enumerate(analysis, 1):
                emit(f"\n  [{rec['priority']}] 建议 #{i}")
                emit(f"    参数:   {rec['param']}")
                emit(f"    当前值: {rec['current']}")
                emit(f"    建议值: {rec['suggested']}")
                emit(f"    原因:   {rec['reason']}")
        emit("")

        return "\n".join(lines)

    def _print_wait_diag(self, bar_hits, bar_misses, icon_hits, icon_misses):
        print(f"\n  [等待就绪阶段 识别诊断]")
        bar_total = bar_hits + bar_misses
        icon_total = icon_hits + icon_misses
        if bar_total > 0:
            print(f"    鱼条: {bar_hits}/{bar_total} ({100 * bar_hits // max(bar_total, 1)}%)")
        if icon_total > 0:
            print(f"    鱼标: {icon_hits}/{icon_total} ({100 * icon_hits // max(icon_total, 1)}%)")
        if bar_hits / max(bar_total, 1) < 0.3:
            print(f"    !! 鱼条几乎检测不到，请检查 roi 是否准确框住了鱼条区域")
            print(f"    !! 或降低 gray_threshold (当前 {DEBUG_PARAMS['gray_threshold']})")
        if icon_hits / max(icon_total, 1) < 0.3:
            print(f"    !! 鱼标几乎检测不到，请检查 icon_min_area / icon_max_area")
        print()

    # ═══════════════════════════════════════════════════════════════
    #  TXT 报告
    # ═══════════════════════════════════════════════════════════════

    def _save_txt_report(self, text):
        try:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            REPORT_TXT.write_text(text, encoding="utf-8")
            print(f"[FishFightDebug] TXT 报告已保存: {REPORT_TXT}")
        except Exception as e:
            print(f"[FishFightDebug] TXT 保存失败: {e}")

    # ═══════════════════════════════════════════════════════════════
    #  截图保存
    # ═══════════════════════════════════════════════════════════════

    def _save_frame_screenshot(self, img, roi, bar_rect, icon_rect,
                               bar_center, control_top, control_bottom,
                               offset, zone, action, shot_idx, frame_idx):
        try:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            vis = img.copy()

            rx, ry, rw, rh = roi

            if bar_rect is not None:
                bx1, by1, bx2, by2 = bar_rect
                bx1 += rx
                by1 += ry
                bx2 += rx
                by2 += ry
                cv2.rectangle(vis, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
                cv2.putText(vis, "BAR", (bx1, by1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            if icon_rect is not None:
                ix1, iy1, ix2, iy2 = icon_rect
                ix1 += rx
                iy1 += ry
                ix2 += rx
                iy2 += ry
                cv2.rectangle(vis, (ix1, iy1), (ix2, iy2), (255, 0, 0), 2)
                cv2.putText(vis, "ICON", (ix1, iy1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

            if control_top is not None and control_bottom is not None:
                cty = ry + control_top
                cby = ry + control_bottom
                cv2.line(vis, (rx, cty), (rx + rw, cty), (0, 0, 255), 1, cv2.LINE_AA)
                cv2.line(vis, (rx, cby), (rx + rw, cby), (0, 0, 255), 1, cv2.LINE_AA)
                cv2.putText(vis, "CTRL_TOP", (rx + 2, cty - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
                cv2.putText(vis, "CTRL_BOT", (rx + 2, cby + 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

            cv2.rectangle(vis, (rx, ry), (rx + rw, ry + rh), (255, 255, 0), 1)

            info_lines = [
                f"Frame: {frame_idx}",
                f"Zone: {zone}",
                f"Action: {action}",
            ]
            if offset is not None:
                info_lines.append(f"Offset: {offset:+.0f}px")
            y0 = ry + rh + 20
            for i, line in enumerate(info_lines):
                cv2.putText(vis, line, (rx, y0 + i * 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            filename = SCREENSHOT_DIR / f"frame_{frame_idx:04d}_shot_{shot_idx:03d}.png"
            cv2.imwrite(str(filename), vis)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    #  结果持久化
    # ═══════════════════════════════════════════════════════════════

    def _save_results(self, result):
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        history = []
        if RESULTS_FILE.exists():
            try:
                history = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.append(result)
        RESULTS_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        self._save_csv(history)
        self._print_history(history)

    def _save_csv(self, history):
        fieldnames = [
            "序号", "时间", "成功", "耗时(秒)", "总帧数", "按压次数",
            "总按压ms", "平均按压ms", "按压占比%", "状态切换",
            "gray_threshold", "control_zone_ratio",
            "min_hold", "max_hold", "hold_k",
            "merge_grace", "bar_missing_timeout",
            "鱼条命中率", "鱼标命中率",
            "合并事件", "鱼条丢失", "振荡切换",
            "最大过冲", "平均过冲", "最大欠冲",
            "建议参数", "建议值", "建议原因",
        ]
        rows = []
        for i, r in enumerate(history, 1):
            p = r.get("params_used", {})
            recs = r.get("recommendations", [])
            rec_param = ""
            rec_to = ""
            rec_reason = ""
            if recs:
                r0 = recs[0]
                if r0["param"] != "当前参数":
                    rec_param = r0["param"]
                    rec_to = r0["suggested"]
                    rec_reason = r0["reason"]
                else:
                    rec_param = "OK"
                    rec_to = "保持不变"
                    rec_reason = "参数合适"
            rows.append({
                "序号": i,
                "时间": r.get("timestamp", "")[:19],
                "成功": "Y" if r.get("success") else "N",
                "耗时(秒)": r.get("elapsed", 0),
                "总帧数": r.get("total_frames", 0),
                "按压次数": r.get("press_count", 0),
                "总按压ms": r.get("total_hold_ms", 0),
                "平均按压ms": r.get("avg_hold_duration", 0),
                "按压占比%": round(r.get("total_hold_ms", 0) / max(r.get("elapsed", 1) * 1000, 1) * 100, 1),
                "状态切换": r.get("hold_state_changes", 0),
                "gray_threshold": p.get("gray_threshold", ""),
                "control_zone_ratio": p.get("control_zone_ratio", ""),
                "min_hold": p.get("min_hold_duration", ""),
                "max_hold": p.get("max_hold_duration", ""),
                "hold_k": p.get("hold_k", ""),
                "merge_grace": p.get("merge_grace", ""),
                "bar_missing_timeout": p.get("bar_missing_timeout", ""),
                "鱼条命中率": r.get("bar_hit_rate", ""),
                "鱼标命中率": r.get("icon_hit_rate", ""),
                "合并事件": r.get("merge_events", 0),
                "鱼条丢失": r.get("bar_lost_events", 0),
                "振荡切换": r.get("osc_transitions", 0),
                "最大过冲": r.get("max_overshoot", 0),
                "平均过冲": r.get("avg_overshoot", 0),
                "最大欠冲": r.get("max_undershoot", 0),
                "建议参数": rec_param,
                "建议值": rec_to,
                "建议原因": rec_reason,
            })
        with open(RESULTS_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[FishFightDebug] CSV 已保存: {RESULTS_CSV}")

    def _print_history(self, history):
        if len(history) < 2:
            return
        print(f"\n{'=' * 65}")
        print(f"  历史测试汇总 (共 {len(history)} 次)")
        print(f"{'=' * 65}")
        header = f"  {'#':<4} {'结果':<5} {'耗时':<8} {'hold_k':<7} {'按压%':<7} {'gray':<5} {'bar%':<6} {'icon%':<6} {'建议'}"
        print(header)
        print(f"  {'-' * 65}")
        for i, r in enumerate(history, 1):
            p = r.get("params_used", {})
            succ = "Y" if r.get("success") else "N"
            t = r.get("elapsed", 0)
            hk = p.get("hold_k", "-")
            hp = round(r.get("total_hold_ms", 0) / max(r.get("elapsed", 1) * 1000, 1) * 100, 1)
            gt = p.get("gray_threshold", "-")
            br = r.get("bar_hit_rate", "-")
            ir = r.get("icon_hit_rate", "-")
            recs = r.get("recommendations", [])
            tip = recs[0]["param"] if recs else "-"
            if tip == "当前参数":
                tip = "OK"
            print(f"  {i:<4} {succ:<5} {t:<8.1f} {str(hk):<7} {str(hp):<7} {str(gt):<5} {str(br):<6} {str(ir):<6} {tip}")
        print()

    # ═══════════════════════════════════════════════════════════════
    #  核心检测
    # ═══════════════════════════════════════════════════════════════

    def _find_bar_and_icon(self, img, roi, gray_threshold, bar_min_area, icon_min_area, icon_max_area):
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
        roi_img = img[y:y + h, x:x + w]

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
        self._action_counter += 1
        entry = f"_fishdbg_{id(self)}_{self._action_counter}"
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
        try:
            img = ctrl.post_screencap().wait().get()
        except Exception:
            return None
        if img is None or img.size == 0:
            return None
        if not img.flags.c_contiguous:
            img = np.ascontiguousarray(img)
        return img