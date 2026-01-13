#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACT伤害统计UI界面 - Cyberpunk 2077风格
显示从Flask服务器获取的实时伤害数据
"""

import ctypes
import queue
import tkinter as tk
from tkinter import ttk
import requests
import json
import threading
import time
import os
import sys
import re
import colorsys
import random
from datetime import datetime
import tempfile
import base64
import zipfile
import urllib.request
from urllib.parse import urljoin
import webbrowser
import io
import winreg  # 用于注册表操作
import subprocess
import shutil

try:
    import psutil
except ImportError:
    psutil = None

# 可选：用于抗锯齿的圆角绘制
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter
except Exception:
    Image = ImageTk = ImageDraw = ImageFilter = None


class ACTDamageUI:

    def get_resource_path(self, relative_path):
        """获取资源文件的正确路径，兼容PyInstaller打包"""
        try:
            # PyInstaller打包后的临时路径
            base_path = sys._MEIPASS
        except Exception:
            # 开发环境中的路径
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def check_font_registry(self):
        """检查注册表中是否已安装Orbitron字体"""
        try:
            # 检查注册表标识
            key_path = r"SOFTWARE\StarResonanceDamageCounter"
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    value, _ = winreg.QueryValueEx(
                        key, "OrbitronFontInstalled")
                    if value == "1":
                        print("[FONT_INFO] 注册表显示Orbitron字体已安装")
                        return True
            except (FileNotFoundError, OSError):
                pass

            # 检查系统字体注册表
            font_key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, font_key_path) as key:
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            if "orbitron" in name.lower():
                                print(f"[FONT_INFO] 系统中已安装Orbitron字体: {name}")
                                self.set_font_registry_flag()
                                return True
                            i += 1
                        except OSError:
                            break
            except (FileNotFoundError, OSError):
                pass

            return False
        except Exception as e:
            print(f"[FONT_WARNING] 检查字体注册表失败: {e}")
            return False

    def set_font_registry_flag(self):
        """在注册表中设置字体安装标识"""
        try:
            key_path = r"SOFTWARE\StarResonanceDamageCounter"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValueEx(key, "OrbitronFontInstalled",
                                  0, winreg.REG_SZ, "1")
                winreg.SetValueEx(key, "InstallDate", 0, winreg.REG_SZ,
                                  datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print("[FONT_INFO] 已设置字体安装注册表标识")
            return True
        except Exception as e:
            print(f"[FONT_WARNING] 设置注册表标识失败: {e}")
            return False

    def install_bundled_fonts(self):
        """安装打包的字体文件"""
        try:
            font_dir = self.get_resource_path("fonts")
            if not os.path.exists(font_dir):
                print("[FONT_WARNING] 未找到打包的字体文件夹")
                return False

            # 获取系统字体目录
            system_fonts_dir = os.path.join(os.environ['WINDIR'], 'Fonts')

            # 字体文件列表
            font_files = [
                "orbitron-black.otf",
                "orbitron-bold.otf",
                "Orbitron-Embedded.ttf",
                "orbitron-light.otf",
                "orbitron-medium.otf"
            ]

            installed_count = 0
            for font_file in font_files:
                src_path = os.path.join(font_dir, font_file)
                if os.path.exists(src_path):
                    dst_path = os.path.join(system_fonts_dir, font_file)

                    # 检查字体是否已存在
                    if os.path.exists(dst_path):
                        print(f"[FONT_INFO] 字体已存在: {font_file}")
                        installed_count += 1
                        continue

                    try:
                        # 复制字体文件到系统字体目录
                        shutil.copy2(src_path, dst_path)
                        print(f"[FONT_INFO] 已安装字体: {font_file}")
                        installed_count += 1

                        # 注册字体到注册表
                        self.register_font_in_registry(font_file, dst_path)

                    except Exception as e:
                        print(f"[FONT_ERROR] 安装字体失败 {font_file}: {e}")

            if installed_count > 0:
                # 刷新字体缓存
                self.refresh_font_cache()
                # 设置注册表标识
                self.set_font_registry_flag()
                print(f"[FONT_INFO] 成功安装 {installed_count} 个字体文件")
                return True
            else:
                print("[FONT_WARNING] 没有安装任何字体文件")
                return False

        except Exception as e:
            print(f"[FONT_ERROR] 安装打包字体失败: {e}")
            return False

    def register_font_in_registry(self, font_file, font_path):
        """在注册表中注册字体"""
        try:
            # 确定字体名称
            font_name = font_file.replace('.ttf', '').replace('.otf', '')
            font_name = font_name.replace('-', ' ').title()

            # 注册到字体注册表
            font_key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, font_key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(
                    key, f"{font_name} (TrueType)", 0, winreg.REG_SZ, font_file)

            print(f"[FONT_INFO] 已在注册表中注册字体: {font_name}")
        except Exception as e:
            print(f"[FONT_WARNING] 注册字体到注册表失败: {e}")

    def refresh_font_cache(self):
        """刷新系统字体缓存"""
        try:
            # 通知系统字体更改
            ctypes.windll.gdi32.AddFontResourceW(None)

            # 广播字体更改消息
            HWND_BROADCAST = 0xFFFF
            WM_FONTCHANGE = 0x001D
            ctypes.windll.user32.SendMessageW(
                HWND_BROADCAST, WM_FONTCHANGE, 0, 0)

            print("[FONT_INFO] 已刷新系统字体缓存")
        except Exception as e:
            print(f"[FONT_WARNING] 刷新字体缓存失败: {e}")

    def show_messagebox(self, message, title="提示", color=None, duration=1800):
        """自定义无边框弹窗，Cyberpunk风格"""
        color = color or self.colors["neon_cyan"]
        msg_win = tk.Toplevel(self.root)
        msg_win.overrideredirect(True)
        msg_win.wm_attributes("-topmost", True)
        msg_win.configure(bg=self.colors["bg_primary"])
        msg_win.wm_attributes("-alpha", 0.97)
        # 居中
        msg_win.update_idletasks()
        w, h = 320, 120
        x = self.root.winfo_x() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - h) // 2
        msg_win.geometry(f"{w}x{h}+{x}+{y}")
        # 边框
        border = tk.Frame(msg_win, bg=color, bd=0)
        border.pack(fill="both", expand=True, padx=2, pady=2)
        frame = tk.Frame(border, bg=self.colors["bg_primary"], bd=0)
        frame.pack(fill="both", expand=True, padx=6, pady=6)
        # 标题
        tk.Label(
            frame,
            text=title,
            font=self.get_font(13, "bold"),
            bg=self.colors["bg_primary"],
            fg=color,
        ).pack(pady=(8, 2))
        # 内容
        tk.Label(
            frame,
            text=message,
            font=self.get_font(11, "bold"),
            bg=self.colors["bg_primary"],
            fg=self.colors["text_primary"],
            wraplength=280,
            justify="center",
        ).pack(pady=(0, 8))
        # 自动关闭
        msg_win.after(duration, msg_win.destroy)
        # 支持拖动
        drag = {"x": 0, "y": 0}

        def start_drag(event):
            drag["x"] = event.x
            drag["y"] = event.y

        def drag_win(event):
            x = msg_win.winfo_x() + (event.x - drag["x"])
            y = msg_win.winfo_y() + (event.y - drag["y"])
            msg_win.geometry(f"+{x}+{y}")

        msg_win.bind("<Button-1>", start_drag)
        msg_win.bind("<B1-Motion>", drag_win)

    """ACT伤害统计UI界面 - Cyberpunk风格"""

    def setup_fonts(self):
        """设置字体配置 - 强制优先使用 Orbitron"""
        # 直接使用 Orbitron 作为首选字体（延迟验证）
        primary_font = "Orbitron"

        # 先设置字体配置，稍后验证
        self.fonts = {
            "title": (primary_font, 16, "bold"),
            "header": (primary_font, 10, "bold"),
            "normal": (primary_font, 9, "normal"),
            "small": (primary_font, 8, "normal"),
            "tiny": (primary_font, 7, "normal"),
            "ui_title": (primary_font, 14, "bold"),
            "ui_header": (primary_font, 10, "bold"),
            "ui_normal": (primary_font, 8, "normal"),
        }

        print(f"[FONT_INFO] 字体配置完成，将使用: {primary_font}")

    def delayed_font_verification(self):
        """延迟字体验证（在窗口创建后）"""
        try:
            # 尝试加载 Orbitron 字体
            self.load_embedded_font()

            # 验证 Orbitron 是否真正可用
            if self.verify_font_available("Orbitron"):
                print("[FONT_SUCCESS] Orbitron 字体验证成功")
                return
            else:
                print("[FONT_WARNING] Orbitron 字体验证失败，但将继续尝试使用")
                # 即使验证失败，也继续使用 Orbitron，让系统自动回退
                return

        except Exception as e:
            print(f"[FONT_ERROR] 字体验证过程出错: {e}")
            # 出错时使用备用字体
            self.use_fallback_font()

    def use_fallback_font(self):
        """使用备用字体"""
        backup_fonts = ["Consolas", "Courier New", "monospace"]
        selected_font = self.get_available_font(backup_fonts)

        # 更新所有字体配置
        for key in self.fonts:
            size = self.fonts[key][1]
            weight = self.fonts[key][2]
            self.fonts[key] = (selected_font, size, weight)

        print(f"[FONT_FALLBACK] 切换到备用字体: {selected_font}")

    def verify_font_available(self, font_name):
        """验证指定字体是否可用（需要在窗口创建后调用）"""
        try:
            import tkinter.font as tkFont
            test_font = tkFont.Font(family=font_name, size=12)
            actual_family = test_font.actual("family")

            # 检查实际字体是否匹配（不区分大小写）
            if font_name.lower() in actual_family.lower():
                print(f"[FONT_DEBUG] {font_name} 验证成功 -> {actual_family}")
                return True
            else:
                print(f"[FONT_DEBUG] {font_name} 映射到不同字体 -> {actual_family}")
                return False
        except Exception as e:
            print(f"[FONT_ERROR] 字体验证失败 {font_name}: {e}")
            return False

    def get_font(self, size, weight="normal"):
        """动态获取配置的字体"""
        if hasattr(self, 'fonts') and self.fonts:
            # 获取基础字体名称
            font_family = self.fonts["normal"][0]
            return (font_family, size, weight)
        else:
            # 如果字体还未初始化，强制使用 Orbitron
            return ("Orbitron", size, weight)

    def create_shadow_text_canvas(self, parent, text, font_tuple, fg_color, bg_color, height=None, width=None, anchor="center"):
        """创建带阴影效果的文字Canvas"""
        # 自动计算高度
        if height is None:
            height = font_tuple[1] + 8  # 字体大小 + 边距

        canvas = tk.Canvas(
            parent,
            height=height,
            width=width,
            bg=bg_color,
            highlightthickness=0,
            bd=0
        )

        def draw_shadow_text():
            canvas.delete("all")

            # 获取画布尺寸
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                # 计算文字位置
                if anchor == "center":
                    x = canvas_width // 2
                    y = canvas_height // 2
                elif anchor == "w":
                    x = 10
                    y = canvas_height // 2
                elif anchor == "e":
                    x = canvas_width - 10
                    y = canvas_height // 2
                else:
                    x = canvas_width // 2
                    y = canvas_height // 2

                # 绘制多层阴影（渐变效果）
                shadow_layers = [
                    (3, 3, "#000000", 0.8),
                    (2, 2, "#111111", 0.6),
                    (1, 1, "#222222", 0.4)
                ]

                for dx, dy, shadow_color, alpha in shadow_layers:
                    canvas.create_text(
                        x + dx, y + dy,
                        text=text,
                        font=font_tuple,
                        fill=shadow_color,
                        anchor=anchor
                    )

                # 绘制边框效果（使用深灰色）
                border_color = "#333333"
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    canvas.create_text(
                        x + dx, y + dy,
                        text=text,
                        font=font_tuple,
                        fill=border_color,
                        anchor=anchor
                    )

                # 绘制主文字
                canvas.create_text(
                    x, y,
                    text=text,
                    font=font_tuple,
                    fill=fg_color,
                    anchor=anchor
                )

        # 绑定配置事件以重绘
        def safe_draw():
            try:
                if canvas.winfo_exists():
                    draw_shadow_text()
            except:
                pass

        canvas.bind("<Configure>", lambda e: safe_draw())
        canvas.after(10, safe_draw)

        return canvas

    def get_available_font(self, font_list):
        """检测系统中可用的字体"""
        import tkinter.font as tkFont

        # 首先尝试加载 Orbitron 字体
        if "Orbitron" in font_list:
            self.load_embedded_font()

        for font_name in font_list:
            try:
                # 尝试创建字体对象来测试是否可用
                test_font = tkFont.Font(family=font_name, size=12)
                actual_family = test_font.actual("family")

                # 如果实际字体家族与请求的相同（或者是已知的映射），则字体可用
                if font_name.lower() in actual_family.lower() or actual_family != "TkDefaultFont":
                    return font_name
            except:
                continue

        # 如果都不可用，返回系统默认等宽字体
        return "monospace"

    def load_jason_config(self):
        """加载统一的ACT副本配置文件"""
        import json
        import os

        # 优先加载新的统一配置文件
        config_paths = [
            "act_raid_config.json",           # 新的统一配置文件
            "jason_raid_config.json",         # 旧的JASON配置文件（向后兼容）
            "act_example_raid.json"           # 旧的ACT示例配置（向后兼容）
        ]

        for config_file in config_paths:
            config_path = os.path.join(os.path.dirname(__file__), config_file)
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"[DEBUG] 配置文件加载成功: {config_file}")

                    # 确保配置包含必要的结构
                    if 'jason_phases' not in config:
                        config['jason_phases'] = {
                            "current_phase": 1,
                            "auto_advance": False,
                            "phase_definitions": [
                                {"id": 1, "name": "一阶段机制", "color": "#00ff00"},
                                {"id": 2, "name": "二阶段机制", "color": "#ffff00"},
                                {"id": 3, "name": "三阶段机制", "color": "#ff0000"}
                            ]
                        }

                    if 'hotkeys' not in config:
                        config['hotkeys'] = {
                            "advance_phase": "Prior",
                            "reset_rage_time": "Next"
                        }

                    return config
            except Exception as e:
                print(f"[DEBUG] 尝试加载配置文件 {config_file} 失败: {e}")
                continue

        print("[DEBUG] 所有配置文件加载失败，使用默认配置")
        # 返回默认配置
        return {
            "name": "默认配置",
            "description": "默认的ACT副本配置",
            "total_duration": 300,
            "hotkeys": {
                "advance_phase": "Prior",
                "reset_rage_time": "Next",
                "phase_1": "F1",
                "phase_2": "F2",
                "phase_3": "F3"
            },
            "jason_phases": {
                "current_phase": 1,
                "auto_advance": False,
                "auto_advance_by_time": False,
                "auto_advance_by_damage": False,
                "phase_definitions": [
                    {"id": 1, "name": "一阶段机制", "color": "#00ff00"},
                    {"id": 2, "name": "二阶段机制", "color": "#ffff00"},
                    {"id": 3, "name": "三阶段机制", "color": "#ff0000"}
                ]
            },
            "alerts": [],
            "damage_thresholds": [],
            "phases": []
        }

    def advance_jason_phase(self):
        """推进JASON阶段"""
        # 获取最大阶段数
        max_phases = 3  # 默认值
        if self.current_act_config and 'jason_phases' in self.current_act_config:
            max_phases = len(self.current_act_config['jason_phases'])

        if self.current_jason_phase < max_phases:
            # 先清理当前（旧）阶段的警告状态
            current_phase = self.current_jason_phase

            # 清空当前阶段的警告状态（旧的单次触发）
            if hasattr(self, 'triggered_warnings'):
                phase_warnings_to_remove = [
                    key for key in self.triggered_warnings
                    if key.startswith(f"phase_{current_phase}_warning_")
                ]
                for key in phase_warnings_to_remove:
                    self.triggered_warnings.discard(key)

            # 清空当前阶段的重复警告状态
            if hasattr(self, 'warning_triggers'):
                phase_warning_triggers_to_remove = [
                    key for key in self.warning_triggers
                    if key.startswith(f"phase_{current_phase}_warning_")
                ]
                for key in phase_warning_triggers_to_remove:
                    del self.warning_triggers[key]

            # 然后推进到下一阶段
            self.current_jason_phase += 1
            self.jason_phase_start_time = time.time()
            self.jason_phases_completed.append({
                "phase": self.current_jason_phase - 1,
                "completed_at": time.time()
            })
            print(f"[DEBUG] JASON阶段推进到: {self.current_jason_phase}")

            # 更新所有显示JASON信息的窗口
            self.update_jason_displays()
        else:
            print(f"[DEBUG] JASON已达到最高阶段 ({max_phases})")

    def reset_jason_rage_time(self):
        """重置JASON暴走时间"""
        current_time = time.time()
        self.jason_rage_start_time = current_time
        self.current_jason_phase = 1
        self.jason_phase_start_time = current_time
        self.jason_phases_completed = []
        self.jason_combat_start_time = current_time

        # 清空所有警告状态
        if hasattr(self, 'triggered_warnings'):
            self.triggered_warnings.clear()
        if hasattr(self, 'warning_triggers'):
            self.warning_triggers.clear()
        # 安全获取total_damage
        self.jason_phase_damage_start = getattr(self, 'total_damage', 0)
        # 清空已触发的警告
        self.triggered_warnings = set()
        print("[DEBUG] JASON暴走时间已重置")
        # 更新所有显示JASON信息的窗口
        self.update_jason_displays()

    def set_jason_phase(self, phase_id):
        """直接设置JASON阶段"""
        if 1 <= phase_id <= 3:
            self.current_jason_phase = phase_id
            self.jason_phase_start_time = time.time()
            print(f"[DEBUG] JASON阶段设置为: {self.current_jason_phase}")
            self.update_jason_displays()

    def get_jason_phase_info(self):
        """获取当前JASON阶段信息"""
        # 首先检查动态加载的配置
        if self.current_act_config and 'jason_phases' in self.current_act_config:
            jason_phases = self.current_act_config['jason_phases']

            # 检查新格式：直接的阶段数组
            if isinstance(jason_phases, list):
                if 0 < self.current_jason_phase <= len(jason_phases):
                    return jason_phases[self.current_jason_phase - 1]

            # 检查旧格式：包含phase_definitions的对象
            elif isinstance(jason_phases, dict) and 'phase_definitions' in jason_phases:
                phase_definitions = jason_phases['phase_definitions']
                for phase in phase_definitions:
                    if phase.get("id") == self.current_jason_phase:
                        return phase

        # 回退到旧的配置格式（兼容性）
        phase_definitions = self.jason_config.get(
            "jason_phases", {}).get("phase_definitions", [])
        for phase in phase_definitions:
            if phase["id"] == self.current_jason_phase:
                return phase
        return {"id": self.current_jason_phase, "name": f"阶段{self.current_jason_phase}", "color": "#ffffff"}

    def get_team_total_damage(self):
        """获取队伍总伤害"""
        try:
            if hasattr(self, 'current_data') and self.current_data:
                user_data = self.current_data.get("user", {})
                team_total = 0
                for uid, user_info in user_data.items():
                    total_damage = user_info.get(
                        "total_damage", {}).get("total", 0)
                    team_total += total_damage
                return team_total
            return 0
        except Exception:
            return 0

    def format_damage_number(self, damage):
        """格式化伤害数字，超过1000显示K，超过1000000显示M"""
        try:
            if damage >= 1000000:
                # 超过100万，显示为M
                return f"{damage / 1000000:.1f}M"
            elif damage >= 1000:
                # 超过1000，显示为K
                return f"{damage / 1000:.1f}K"
            else:
                # 小于1000，直接显示
                return str(int(damage))
        except:
            return "0"

    def update_jason_displays(self):
        """更新所有显示JASON信息的窗口"""
        # 更新所有timer窗口中的JASON信息
        for timer_window in self.timer_windows:
            if hasattr(timer_window, 'update_jason_info'):
                try:
                    timer_window.update_jason_info()
                except:
                    pass

            # 更新明显模式的JASON信息
            if hasattr(timer_window, 'update_prominent_jason_info'):
                try:
                    timer_window.update_prominent_jason_info()
                except:
                    pass

    def check_jason_auto_advance(self):
        """检查JASON阶段自动推进条件"""
        # 使用动态加载的配置，而不是旧的jason_config
        if not self.current_act_config or 'jason_phases' not in self.current_act_config:
            return

        jason_phases = self.current_act_config.get("jason_phases", {})
        if not jason_phases:
            return

        current_time = time.time()

        # 初始化战斗开始时间
        if self.jason_combat_start_time is None:
            self.jason_combat_start_time = current_time
            self.jason_phase_start_time = current_time
            return

        # 检查阶段警告
        self.check_phase_warnings(current_time)

        # 检查时间推进（如果启用）
        time_config = jason_phases.get("time_based_advance", {})
        if time_config.get("enabled", False):
            self.check_time_based_advance(current_time)

        # 检查伤害推进（如果启用）
        damage_config = jason_phases.get("damage_based_advance", {})
        if damage_config.get("enabled", False) and self.jason_auto_advance_enabled:
            print(f"[DEBUG] 调用伤害推进检查，当前阶段={self.current_jason_phase}")
            self.check_damage_based_advance()

    def check_phase_warnings(self, current_time):
        """检查当前阶段的警告（支持重复触发）"""
        # 使用战斗开始时间而不是阶段开始时间
        if self.jason_combat_start_time is None:
            return

        # 获取当前阶段信息
        phase_info = self.get_jason_phase_info()
        if not phase_info:
            return

        # 计算战斗开始以来经过的时间（这是警告时间的基准）
        combat_elapsed = current_time - self.jason_combat_start_time

        # 初始化警告触发记录
        if not hasattr(self, 'warning_triggers'):
            self.warning_triggers = {}

        # 检查当前阶段的警告
        warnings = phase_info.get("warnings", [])
        for i, warning in enumerate(warnings):
            warning_time = warning.get("time", 0)  # 相对于战斗开始的时间
            warning_message = warning.get("message", "")
            warning_color = warning.get("color", "yellow")
            warning_sound = warning.get("sound", False)
            warning_interval = warning.get("interval", None)  # 重复间隔（秒）

            # 创建警告的唯一标识符
            warning_key = f"phase_{self.current_jason_phase}_warning_{i}"

            # 检查是否到了首次触发时间
            if combat_elapsed >= warning_time:

                # 如果没有interval，使用旧的单次触发逻辑
                if warning_interval is None:
                    if not hasattr(self, 'triggered_warnings'):
                        self.triggered_warnings = set()

                    if warning_key not in self.triggered_warnings:
                        self.triggered_warnings.add(warning_key)
                        print(
                            f"[DEBUG] 触发单次警告: {warning_message} (战斗时间: {combat_elapsed:.1f}s)")
                        self._trigger_warning(
                            warning_message, warning_color, warning_sound)

                else:
                    # 使用重复触发逻辑
                    time_since_first_trigger = combat_elapsed - warning_time

                    # 只在第一次触发时间之后处理重复
                    if time_since_first_trigger >= 0:
                        # 计算应该触发的次数（包括首次）
                        expected_triggers = int(
                            time_since_first_trigger / warning_interval) + 1

                        # 检查实际触发次数
                        actual_triggers = self.warning_triggers.get(
                            warning_key, 0)

                        # 如果需要触发
                        if expected_triggers > actual_triggers:
                            # 检查当前时间是否正好在触发点附近（±0.5秒容差）
                            trigger_points = [
                                warning_time + n * warning_interval for n in range(expected_triggers)]
                            should_trigger = any(
                                abs(combat_elapsed - point) < 0.5 for point in trigger_points)

                            if should_trigger:
                                self.warning_triggers[warning_key] = expected_triggers
                                print(
                                    f"[DEBUG] 触发重复警告: {warning_message} (战斗时间: {combat_elapsed:.1f}s, 第{expected_triggers}次)")
                                self._trigger_warning(
                                    warning_message, warning_color, warning_sound)

    def _trigger_warning(self, message, color, sound):
        """触发警告的通用方法"""
        # 显示警告消息
        print(f"[PHASE WARNING] {message}")

        # 播放TTS警告（如果启用声音）- 使用排队系统避免冲突
        if sound:
            try:
                self.speak_text(message, priority=25,
                                source_type="phase_warning")
            except Exception as e:
                print(f"[ERROR] TTS警告播放失败: {e}")

        # 在明显模式窗口中显示警告 - 使用原有的alert系统
        self._show_warning_in_prominent_mode(message, color)

        # 在界面上显示警告（如果有通知系统）
        try:
            # 尝试显示通知
            if hasattr(self, 'show_notification'):
                self.show_notification(message, color)
        except:
            pass

    def _show_warning_in_prominent_mode(self, message, color):
        """在明显模式窗口中显示警告"""
        try:
            print(f"[DEBUG] 尝试在明显模式显示警告: {message}")

            # 使用全局timer窗口列表查找
            if hasattr(self, 'timer_windows') and self.timer_windows:
                print(f"[DEBUG] 找到 {len(self.timer_windows)} 个timer窗口")
                for i, timer_window in enumerate(self.timer_windows):
                    try:
                        print(f"[DEBUG] 检查timer窗口 {i}")
                        if timer_window and timer_window.winfo_exists():
                            print(f"[DEBUG] timer窗口 {i} 存在")

                            if hasattr(timer_window, 'prominent_window'):
                                print(
                                    f"[DEBUG] timer窗口 {i} 有prominent_window属性: {timer_window.prominent_window}")

                                if timer_window.prominent_window:
                                    if hasattr(timer_window, 'prominent_alert_enabled'):
                                        enabled = timer_window.prominent_alert_enabled.get()
                                        print(
                                            f"[DEBUG] timer窗口 {i} prominent_alert_enabled: {enabled}")

                                        if enabled:
                                            print(
                                                f"[DEBUG] 找到活动的明显模式窗口，使用alert系统显示警告")

                                            # 使用原有的alert系统，避免警告覆盖问题
                                            color_map = {
                                                'yellow': self.colors["neon_yellow"],
                                                'red': self.colors["neon_red"],
                                                'orange': self.colors["neon_orange"],
                                                'cyan': self.colors["neon_cyan"],
                                                'blue': self.colors["neon_blue"],
                                                'green': self.colors["neon_green"],
                                                'purple': self.colors["neon_purple"]
                                            }
                                            warning_color = color_map.get(
                                                color, self.colors.get(color, self.colors["neon_yellow"]))

                                            # 使用现有的alert队列系统，确保警告不会覆盖
                                            self.show_alert_with_duration(
                                                timer_window, message, warning_color, 3.0)
                                            return
                                        else:
                                            print(
                                                f"[DEBUG] timer窗口 {i} 明显模式未启用")
                                    else:
                                        print(
                                            f"[DEBUG] timer窗口 {i} 没有prominent_alert_enabled属性")
                                else:
                                    print(
                                        f"[DEBUG] timer窗口 {i} prominent_window为None")
                            else:
                                print(
                                    f"[DEBUG] timer窗口 {i} 没有prominent_window属性")
                        else:
                            print(f"[DEBUG] timer窗口 {i} 不存在或已销毁")
                    except (tk.TclError, AttributeError) as e:
                        print(f"[DEBUG] timer窗口 {i} 检查失败: {e}")
                        continue
            else:
                print(f"[DEBUG] 没有timer_windows属性或列表为空")

            print(f"[DEBUG] 没有找到可用的明显模式窗口")

        except Exception as e:
            print(f"[ERROR] 在明显模式显示警告失败: {e}")
            import traceback
            traceback.print_exc()

    def check_time_based_advance(self, current_time):
        """检查基于时间的阶段推进"""
        if self.jason_phase_start_time is None:
            return

        if not self.current_act_config:
            return

        jason_phases = self.current_act_config.get("jason_phases", {})
        time_config = jason_phases.get("time_based_advance", {})

        # 检查暴走前60秒自动推进到三阶段
        rage_auto_advance = time_config.get(
            "phase_3_auto_advance_before_rage", {})
        if rage_auto_advance.get("enabled", False) and self.current_jason_phase < 3:
            self.check_rage_countdown_advance(current_time, rage_auto_advance)

        # 原有的时间推进逻辑（如果启用）
        if not time_config.get("enabled", False):
            return

        phase_duration = 0
        if self.current_jason_phase == 1:
            phase_duration = time_config.get("phase_1_duration", 120)
        elif self.current_jason_phase == 2:
            phase_duration = time_config.get("phase_2_duration", 180)
        elif self.current_jason_phase == 3:
            phase_duration = time_config.get("phase_3_duration", 300)

        # 检查是否到达阶段时间
        elapsed_time = current_time - self.jason_phase_start_time
        if elapsed_time >= phase_duration and self.current_jason_phase < 3:
            print(
                f"[DEBUG] 时间推进: 阶段{self.current_jason_phase}持续{elapsed_time:.1f}秒，推进到下一阶段")
            self.advance_jason_phase()

    def check_rage_countdown_advance(self, current_time, rage_config):
        """检查暴走倒计时自动推进"""
        if self.jason_rage_start_time is None:
            return

        # 获取总战斗时长
        total_duration = self.current_act_config.get(
            "total_duration", 600) if self.current_act_config else 600
        seconds_before_rage = rage_config.get("seconds_before_rage", 60)

        # 计算从战斗开始的总时间
        total_elapsed = current_time - self.jason_rage_start_time
        time_to_rage = total_duration - total_elapsed

        # 如果距离暴走时间还有指定秒数，且当前不在三阶段，则自动推进
        if time_to_rage <= seconds_before_rage and self.current_jason_phase < 3:
            print(f"[DEBUG] 暴走倒计时推进: 距离暴走还有{time_to_rage:.1f}秒，自动推进到三阶段")
            self.current_jason_phase = 3
            self.jason_phase_start_time = current_time
            self.update_jason_displays()

            # 播放TTS提醒
            if hasattr(self, 'tts_engine') and self.tts_engine:
                try:
                    self.tts_engine.say(f"暴走前{seconds_before_rage}秒，进入三阶段！")
                    self.tts_engine.runAndWait()
                except:
                    pass

    def check_damage_based_advance(self):
        """检查基于总伤害的阶段推进"""
        if not self.current_act_config:
            print("[DEBUG] 没有ACT配置，跳过伤害检查")
            return

        jason_phases = self.current_act_config.get("jason_phases", {})
        damage_config = jason_phases.get("damage_based_advance", {})

        if not damage_config.get("enabled", False):
            print("[DEBUG] 伤害推进未启用，跳过检查")
            return

        current_total_damage = self.total_damage
        print(f"[DEBUG] 伤害检查配置: {damage_config}")

        # 检查伤害阈值
        if self.current_jason_phase == 1:
            threshold = damage_config.get("phase_1_damage_threshold", 30000)
            print(
                f"[DEBUG] 阶段1检查: 当前伤害={current_total_damage}, 阈值={threshold}")
            if current_total_damage >= threshold:
                print(
                    f"[DEBUG] 伤害推进: 总伤害{current_total_damage}达到阈值{threshold}，推进到阶段2")
                self.advance_jason_phase()
        elif self.current_jason_phase == 2:
            threshold = damage_config.get("phase_2_damage_threshold", 80000)
            print(
                f"[DEBUG] 阶段2检查: 当前伤害={current_total_damage}, 阈值={threshold}")
            if current_total_damage >= threshold:
                print(
                    f"[DEBUG] 伤害推进: 总伤害{current_total_damage}达到阈值{threshold}，推进到阶段3")
                self.advance_jason_phase()

    def start_jason_combat(self):
        """开始JASON战斗"""
        self.jason_combat_start_time = time.time()
        self.jason_phase_start_time = time.time()
        self.current_jason_phase = 1
        self.jason_phase_damage_start = self.total_damage
        print("[DEBUG] JASON战斗开始")
        self.update_jason_displays()

    def check_time_based_advance_for_phase(self, current_time, phase_config, auto_advance):
        """检查基于阶段配置的时间推进"""
        if self.jason_phase_start_time is None:
            return

        # 获取阶段持续时间
        phase_duration = auto_advance.get("duration_seconds", 300)  # 默认5分钟

        # 检查是否到达阶段时间
        elapsed_time = current_time - self.jason_phase_start_time
        if elapsed_time >= phase_duration and self.current_jason_phase < 3:
            phase_name = phase_config.get(
                "name", f"阶段{self.current_jason_phase}")
            print(f"[DEBUG] 时间推进: {phase_name}持续{elapsed_time:.1f}秒，推进到下一阶段")
            self.advance_jason_phase()

        # 检查暴走倒计时推进
        rage_advance = auto_advance.get("rage_countdown_advance")
        if rage_advance and rage_advance.get("enabled") and self.current_jason_phase < 3:
            self.check_rage_countdown_advance_new(current_time, rage_advance)

    def check_rage_countdown_advance_new(self, current_time, rage_config):
        """检查新版本的暴走倒计时自动推进"""
        if self.jason_rage_start_time is None:
            return

        # 获取总战斗时长（从动态配置中获取）
        total_duration = 600  # 默认10分钟
        if self.current_act_config:
            total_duration = self.current_act_config.get("total_duration", 600)

        seconds_before_rage = rage_config.get("seconds_before_rage", 60)

        # 计算从战斗开始的总时间
        total_elapsed = current_time - self.jason_rage_start_time
        time_to_rage = total_duration - total_elapsed

        # 如果距离暴走时间还有指定秒数，且当前不在三阶段，则自动推进
        if time_to_rage <= seconds_before_rage and self.current_jason_phase < 3:
            print(f"[DEBUG] 暴走倒计时推进: 距离暴走还有{time_to_rage:.1f}秒，自动推进到三阶段")
            self.current_jason_phase = 3
            self.jason_phase_start_time = current_time
            self.update_jason_displays()

            # 播放TTS提醒
            if hasattr(self, 'tts_engine') and self.tts_engine:
                try:
                    self.tts_engine.say(f"暴走前{seconds_before_rage}秒，进入三阶段！")
                    self.tts_engine.runAndWait()
                except:
                    pass

    def check_damage_based_advance_for_phase(self, damage_config):
        """检查基于阶段配置的伤害推进"""
        current_total_damage = self.total_damage

        # 获取当前阶段的伤害阈值
        threshold = damage_config.get("damage_threshold", 50000)

        if current_total_damage >= threshold and self.current_jason_phase < 3:
            print(
                f"[DEBUG] 伤害推进: 总伤害{current_total_damage}达到阈值{threshold}，推进到下一阶段")
            self.advance_jason_phase()

    def toggle_jason_auto_advance(self):
        """切换JASON自动推进状态"""
        self.jason_auto_advance_enabled = not self.jason_auto_advance_enabled
        status = "启用" if self.jason_auto_advance_enabled else "禁用"
        print(f"[DEBUG] JASON自动推进已{status}")
        self.update_jason_displays()

    def create_jason_control_panel(self, parent, timer_window):
        """创建JASON阶段控制面板"""
        # JASON控制面板
        jason_outer, jason_frame = self.create_rounded_frame(
            parent,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_purple"],
            padding=3,
        )
        jason_outer.configure(height=120)
        jason_outer.pack(fill="x", pady=(0, 8))
        jason_outer.pack_propagate(False)

        # 标题
        title_label = tk.Label(
            jason_frame,
            text="▓▓ JASON阶段控制 ▓▓",
            font=self.get_font(10, "bold"),
            bg=self.colors["bg_secondary"],
            fg=self.colors["neon_purple"]
        )
        title_label.pack(pady=(5, 8))

        # 当前阶段显示
        phase_info_frame = tk.Frame(
            jason_frame, bg=self.colors["bg_secondary"])
        phase_info_frame.pack(fill="x", padx=10, pady=(0, 5))

        # 阶段信息标签
        timer_window.jason_phase_label = tk.Label(
            phase_info_frame,
            text=f"当前阶段: {self.current_jason_phase} - {self.get_jason_phase_info()['name']}",
            font=self.get_font(9, "bold"),
            bg=self.colors["bg_secondary"],
            fg=self.get_jason_phase_info()["color"]
        )
        timer_window.jason_phase_label.pack(side="left")

        # 按钮区域
        button_frame = tk.Frame(jason_frame, bg=self.colors["bg_secondary"])
        button_frame.pack(fill="x", padx=10, pady=(0, 5))

        # 阶段按钮
        phase_buttons_frame = tk.Frame(
            button_frame, bg=self.colors["bg_secondary"])
        phase_buttons_frame.pack(side="left", fill="x", expand=True)

        for i in range(1, 4):
            phase_info = None
            if self.current_act_config:
                for phase in self.current_act_config.get("jason_phases", {}).get("phase_definitions", []):
                    if phase["id"] == i:
                        phase_info = phase
                        break

            if not phase_info:
                continue

            btn = self.create_enhanced_button(
                phase_buttons_frame,
                f"阶段{i}",
                lambda p=i: self.set_jason_phase(p),
                phase_info["color"],
                width=8,
                height=1
            )
            btn.pack(side="left", padx=2)

        # 控制按钮
        control_frame = tk.Frame(button_frame, bg=self.colors["bg_secondary"])
        control_frame.pack(side="right")

        advance_btn = self.create_enhanced_button(
            control_frame,
            "推进阶段",
            self.advance_jason_phase,
            self.colors["neon_cyan"],
            width=8,
            height=1
        )
        advance_btn.pack(side="left", padx=2)

        reset_btn = self.create_enhanced_button(
            control_frame,
            "重置暴走",
            self.reset_jason_rage_time,
            self.colors["neon_orange"],
            width=8,
            height=1
        )
        reset_btn.pack(side="left", padx=2)

        # 自动推进开关
        auto_advance_btn = self.create_enhanced_button(
            control_frame,
            "自动推进",
            self.toggle_jason_auto_advance,
            self.colors["neon_green"] if self.jason_auto_advance_enabled else self.colors["neon_red"],
            width=8,
            height=1
        )
        auto_advance_btn.pack(side="left", padx=2)
        timer_window.jason_auto_advance_btn = auto_advance_btn

        # 添加更新方法到timer窗口
        def update_jason_info():
            """更新JASON阶段信息显示"""
            try:
                phase_info = self.get_jason_phase_info()
                timer_window.jason_phase_label.config(
                    text=f"当前阶段: {self.current_jason_phase} - {phase_info['name']}",
                    fg=phase_info["color"]
                )
                # 更新自动推进按钮状态
                if hasattr(timer_window, 'jason_auto_advance_btn'):
                    btn_color = self.colors["neon_green"] if self.jason_auto_advance_enabled else self.colors["neon_red"]
                    timer_window.jason_auto_advance_btn.config(fg=btn_color)
            except:
                pass

        timer_window.update_jason_info = update_jason_info

    def load_embedded_font(self):
        """尝试加载嵌入的 Orbitron 字体数据，如果没有则自动安装打包的字体"""
        try:
            # 首先检查注册表标识
            if self.check_font_registry():
                return True

            # 检查 Orbitron 字体是否已经在系统中
            import tkinter.font as tkFont
            try:
                test_font = tkFont.Font(family="Orbitron", size=12)
                actual_family = test_font.actual("family")
                if "orbitron" in actual_family.lower():
                    print("[FONT_INFO] 系统中已有 Orbitron 字体")
                    self.set_font_registry_flag()
                    return True
            except:
                pass

            # 尝试安装打包的字体
            print("[FONT_INFO] 未检测到Orbitron字体，尝试安装打包的字体...")
            if self.install_bundled_fonts():
                print("[FONT_INFO] 打包字体安装成功")
                return True

            # 如果打包字体安装失败，显示安装指导
            print("[FONT_INFO] 打包字体安装失败，显示手动安装指导")
            font_dir = self.get_resource_path("fonts")
            local_fonts = self.check_local_font_files(font_dir)
            if local_fonts:
                print(f"[FONT_INFO] 找到本地字体文件: {local_fonts}")
                self.show_font_install_guide(font_dir)
            else:
                # 如果没有打包字体，尝试下载
                print("[FONT_INFO] 未找到打包字体，尝试下载...")
                if self.download_and_install_orbitron():
                    print("[FONT_INFO] 下载字体安装成功")
                    return True
                else:
                    print("[FONT_WARNING] 字体安装失败，将使用备用字体")

            return False

        except Exception as e:
            print(f"[FONT_ERROR] 加载字体时出错: {e}")
            return False

    def check_local_font_files(self, font_dir):
        """检查本地字体文件"""
        try:
            if not os.path.exists(font_dir):
                return []

            font_files = []
            for file in os.listdir(font_dir):
                if file.lower().endswith(('.ttf', '.otf', '.woff', '.woff2')) and 'orbitron' in file.lower():
                    font_files.append(file)

            return font_files
        except Exception as e:
            print(f"[FONT_WARNING] 检查本地字体文件失败: {e}")
            return []

    def create_download_flag(self, flag_path):
        """创建下载完成标识文件"""
        try:
            os.makedirs(os.path.dirname(flag_path), exist_ok=True)

            # 创建标识文件，包含下载时间和状态信息
            flag_content = f"""# Orbitron 字体下载标识文件
# 此文件用于防止重复下载字体
# 如需重新下载，请删除此文件

下载时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
状态: 下载尝试已完成
版本: 1.0

# 手动安装说明:
# 1. 双击 fonts 文件夹中的 .ttf 字体文件
# 2. 点击"安装"按钮
# 3. 重启程序即可使用 Orbitron 字体

# 要重新触发自动下载，请删除此文件
"""

            with open(flag_path, 'w', encoding='utf-8') as f:
                f.write(flag_content)

            print(f"[FONT_INFO] 已创建下载标识: {os.path.basename(flag_path)}")

        except Exception as e:
            print(f"[FONT_WARNING] 创建下载标识失败: {e}")

    def reset_font_download(self):
        """重置字体下载标识（用于开发调试）"""
        try:
            font_dir = self.get_resource_path("fonts")
            download_flag = os.path.join(font_dir, ".font_download_completed")

            if os.path.exists(download_flag):
                os.remove(download_flag)
                print("[FONT_INFO] 字体下载标识已重置")
                return True
            else:
                print("[FONT_INFO] 下载标识不存在，无需重置")
                return False

        except Exception as e:
            print(f"[FONT_ERROR] 重置下载标识失败: {e}")
            return False

            return False

        except Exception as e:
            print(f"[FONT_WARNING] 字体处理失败: {e}")
            return False

    def download_and_install_orbitron(self):
        """自动从多个源下载并安装Orbitron字体"""
        try:
            print("[FONT_INFO] 开始下载 Orbitron 字体...")

            # 尝试多个字体源
            font_sources = [
                {
                    "name": "Google Fonts Archive",
                    "urls": [
                        "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron-VariableFont_wght.ttf"
                    ]
                },
                {
                    "name": "Font Squirrel (备用)",
                    "urls": [
                        "https://www.fontsquirrel.com/fonts/download/orbitron",
                    ]
                },
                {
                    "name": "CDN字体源",
                    "urls": [
                        "https://fonts.gstatic.com/s/orbitron/v31/yMJMMIlzdpvBhQQL_SC3X9yhF25-T1nyGy6xoWgz.woff2"
                    ]
                }
            ]

            # 创建字体文件夹
            font_dir = self.get_resource_path("fonts")
            os.makedirs(font_dir, exist_ok=True)

            # 尝试各个源
            for source in font_sources:
                print(f"[FONT_INFO] 尝试从 {source['name']} 下载...")

                for url in source['urls']:
                    try:
                        success = self.download_font_from_url(url, font_dir)
                        if success:
                            return True
                    except Exception as e:
                        print(f"[FONT_WARNING] {source['name']} 下载失败: {e}")
                        continue

            # 如果所有源都失败，使用嵌入的字体数据
            print("[FONT_INFO] 尝试使用嵌入的字体数据...")
            return self.install_embedded_orbitron(font_dir)

        except Exception as e:
            print(f"[FONT_ERROR] 下载 Orbitron 字体时出错: {e}")
            return self.install_orbitron_simple()

    def download_font_from_url(self, url, font_dir):
        """从指定URL下载字体文件"""
        try:
            print(f"[FONT_INFO] 正在下载: {url}")

            # 创建请求，模拟浏览器
            req = urllib.request.Request(url)
            req.add_header(
                'User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            req.add_header(
                'Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8')
            req.add_header('Accept-Language',
                           'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7')
            req.add_header('Cache-Control', 'no-cache')

            # 下载文件
            response = urllib.request.urlopen(req, timeout=30)
            font_data = response.read()

            # 检查文件大小
            if len(font_data) < 5000:
                print(f"[FONT_WARNING] 文件太小 ({len(font_data)} bytes)，可能不是字体文件")
                return False

            print(f"[FONT_INFO] 下载完成，文件大小: {len(font_data)} bytes")

            # 检查文件类型
            if font_data[:2] == b'PK':  # ZIP文件
                print("[FONT_INFO] 检测到ZIP文件，正在解压...")
                return self.extract_font_from_zip(font_data, font_dir)
            elif font_data[:4] == b'\x00\x01\x00\x00':  # TTF文件
                print("[FONT_INFO] 检测到TTF字体文件")
                return self.save_font_file(font_data, font_dir, ".ttf")
            elif font_data[:4] == b'wOFF':  # WOFF文件
                print("[FONT_INFO] 检测到WOFF字体文件")
                return self.save_font_file(font_data, font_dir, ".woff")
            elif font_data[:4] == b'wOF2':  # WOFF2文件
                print("[FONT_INFO] 检测到WOFF2字体文件")
                return self.save_font_file(font_data, font_dir, ".woff2")
            elif font_data[:4] == b'OTTO':  # OTF文件
                print("[FONT_INFO] 检测到OTF字体文件")
                return self.save_font_file(font_data, font_dir, ".otf")
            else:
                print(f"[FONT_WARNING] 未知文件类型，文件头: {font_data[:8]}")
                # 尝试作为HTML页面处理
                if b'<html' in font_data[:100].lower():
                    print("[FONT_WARNING] 下载的是HTML页面，可能是重定向")
                    return False
                # 尝试保存为TTF
                return self.save_font_file(font_data, font_dir, ".ttf")

        except Exception as e:
            print(f"[FONT_WARNING] 下载失败: {e}")
            return False

    def extract_font_from_zip(self, zip_data, font_dir):
        """从ZIP数据中提取字体文件"""
        try:
            import io
            zip_buffer = io.BytesIO(zip_data)

            with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                font_files = []
                for file_name in zip_ref.namelist():
                    if file_name.lower().endswith(('.ttf', '.otf')):
                        print(f"[FONT_INFO] 找到字体文件: {file_name}")
                        font_data = zip_ref.read(file_name)

                        # 保存字体文件
                        clean_name = os.path.basename(file_name)
                        font_path = os.path.join(font_dir, clean_name)

                        with open(font_path, 'wb') as f:
                            f.write(font_data)

                        font_files.append(font_path)
                        print(
                            f"[FONT_INFO] 已解压: {clean_name} ({len(font_data)} bytes)")

                if font_files:
                    # 尝试安装字体
                    if self.install_font_files(font_files):
                        print("[FONT_INFO] Orbitron 字体安装成功！")
                        return True
                    else:
                        print("[FONT_WARNING] 字体解压成功但安装失败")
                        self.show_font_install_guide(font_dir)
                        return False
                else:
                    print("[FONT_WARNING] ZIP文件中未找到字体文件")
                    return False

        except Exception as e:
            print(f"[FONT_ERROR] 解压ZIP文件失败: {e}")
            return False

    def save_font_file(self, font_data, font_dir, extension):
        """保存字体文件"""
        try:
            font_filename = f"Orbitron-Downloaded{extension}"
            font_path = os.path.join(font_dir, font_filename)

            with open(font_path, 'wb') as f:
                f.write(font_data)

            print(f"[FONT_INFO] 已保存: {font_filename} ({len(font_data)} bytes)")

            # 尝试安装字体
            if self.install_font_files([font_path]):
                print("[FONT_INFO] Orbitron 字体安装成功！")
                return True
            else:
                print("[FONT_WARNING] 字体下载成功但安装失败")
                self.show_font_install_guide(font_dir)
                return False

        except Exception as e:
            print(f"[FONT_ERROR] 保存字体文件失败: {e}")
            return False

    def install_embedded_orbitron(self, font_dir):
        """安装嵌入的简化Orbitron字体数据"""
        try:
            print("[FONT_INFO] 使用嵌入的字体数据...")

            # 这是一个简化的Orbitron字体数据（Base64编码的TTF片段）
            # 注意：这只是一个最小的字体示例，实际效果可能有限
            embedded_font_data = """
VFRUUAAAAAEAAAwAAAABAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAEA
AAABAAAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEA
AAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAA
AAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAAAAQAAAAEAAAABAAA=
"""

            try:
                # 解码Base64数据
                font_data = base64.b64decode(embedded_font_data.strip())

                # 保存嵌入字体
                font_filename = "Orbitron-Embedded.ttf"
                font_path = os.path.join(font_dir, font_filename)

                with open(font_path, 'wb') as f:
                    f.write(font_data)

                print(f"[FONT_INFO] 已创建嵌入字体: {font_filename}")

                # 由于这只是示例数据，直接跳转到安装指南
                self.show_font_install_guide(font_dir)
                return False

            except Exception as e:
                print(f"[FONT_WARNING] 嵌入字体数据处理失败: {e}")
                return self.install_orbitron_simple()

        except Exception as e:
            print(f"[FONT_ERROR] 嵌入字体安装失败: {e}")
            return self.install_orbitron_simple()

    def install_orbitron_simple(self):
        """简化的Orbitron字体安装方案 - 提供一键安装功能"""
        try:
            print("[FONT_INFO] 启动字体安装助手...")

            # 创建一个更友好的安装界面
            if hasattr(self, 'root'):
                # 创建字体安装窗口
                font_window = tk.Toplevel(self.root)
                font_window.title("Orbitron 字体安装助手")
                font_window.geometry("480x360")
                font_window.configure(bg=self.colors["bg_primary"])
                font_window.resizable(False, False)
                font_window.wm_attributes("-topmost", True)

                # 居中显示
                font_window.update_idletasks()
                x = (font_window.winfo_screenwidth() - 480) // 2
                y = (font_window.winfo_screenheight() - 360) // 2
                font_window.geometry(f"480x360+{x}+{y}")

                # 创建主框架
                main_frame = tk.Frame(
                    font_window, bg=self.colors["bg_primary"])
                main_frame.pack(fill="both", expand=True, padx=20, pady=20)

                # 标题
                title_label = tk.Label(
                    main_frame,
                    text="🚀 Orbitron 字体安装助手",
                    font=self.get_font(16, "bold"),
                    fg=self.colors["neon_cyan"],
                    bg=self.colors["bg_primary"]
                )
                title_label.pack(pady=(0, 20))

                # 说明文字
                info_text = """
Orbitron 是一款未来主义科幻字体，
完美匹配 Cyberpunk 2077 风格界面！

自动下载失败，请选择以下安装方式：
"""
                info_label = tk.Label(
                    main_frame,
                    text=info_text,
                    font=self.get_font(10),
                    fg=self.colors["text_primary"],
                    bg=self.colors["bg_primary"],
                    justify="center"
                )
                info_label.pack(pady=(0, 30))

                # 按钮框架
                button_frame = tk.Frame(
                    main_frame, bg=self.colors["bg_primary"])
                button_frame.pack(fill="x", pady=10)

                # 在线下载按钮
                def open_font_page():
                    try:
                        webbrowser.open(
                            "https://fonts.google.com/specimen/Orbitron")
                        font_window.destroy()
                    except:
                        pass

                online_btn = self.create_enhanced_button(
                    button_frame,
                    "🌐 在线下载安装",
                    open_font_page,
                    self.colors["neon_cyan"],
                    width=20, height=2
                )
                online_btn.pack(fill="x", pady=5)

                # 本地安装按钮
                def open_local_guide():
                    try:
                        # 创建fonts文件夹
                        font_dir = self.get_resource_path("fonts")
                        os.makedirs(font_dir, exist_ok=True)

                        # 打开文件夹
                        import subprocess
                        subprocess.Popen(f'explorer "{font_dir}"')

                        # 显示本地安装指南
                        guide_window = tk.Toplevel(font_window)
                        guide_window.title("本地安装指南")
                        guide_window.geometry("400x300")
                        guide_window.configure(bg=self.colors["bg_primary"])

                        guide_text = """
本地安装步骤：

1. 将下载的 Orbitron 字体文件
   (.ttf 格式) 复制到已打开的文件夹

2. 双击字体文件进行安装

3. 重启程序即可使用新字体

支持的字体文件格式：
• Orbitron-Regular.ttf
• Orbitron-Bold.ttf  
• Orbitron-Black.ttf
"""

                        guide_label = tk.Label(
                            guide_window,
                            text=guide_text,
                            font=self.get_font(9),
                            fg=self.colors["text_primary"],
                            bg=self.colors["bg_primary"],
                            justify="left"
                        )
                        guide_label.pack(padx=20, pady=20)

                        font_window.destroy()

                    except Exception as e:
                        print(f"[FONT_ERROR] 打开本地指南失败: {e}")

                local_btn = self.create_enhanced_button(
                    button_frame,
                    "📁 本地安装指南",
                    open_local_guide,
                    self.colors["neon_yellow"],
                    width=20, height=2
                )
                local_btn.pack(fill="x", pady=5)

                # 跳过按钮
                def skip_font():
                    font_window.destroy()

                skip_btn = self.create_enhanced_button(
                    button_frame,
                    "⏭️ 跳过，使用默认字体",
                    skip_font,
                    self.colors["text_secondary"],
                    width=20, height=2
                )
                skip_btn.pack(fill="x", pady=(15, 5))

                # 重新下载按钮（高级选项）
                def reset_and_download():
                    try:
                        self.reset_font_download()
                        font_window.destroy()
                        # 重新触发下载
                        self.load_embedded_font()
                    except Exception as e:
                        print(f"[FONT_ERROR] 重新下载失败: {e}")

                reset_btn = self.create_enhanced_button(
                    button_frame,
                    "🔄 重新下载字体",
                    reset_and_download,
                    self.colors["text_secondary"],
                    width=20, height=1
                )
                reset_btn.pack(fill="x", pady=2)

                # 底部提示
                tip_label = tk.Label(
                    main_frame,
                    text="💡 安装字体后重启程序即可生效",
                    font=self.get_font(8),
                    fg=self.colors["text_secondary"],
                    bg=self.colors["bg_primary"]
                )
                tip_label.pack(side="bottom", pady=(20, 0))

            else:
                # 控制台模式的简化指南
                guide_text = """
╔══════════════════════════════════════════════════════════════════╗
║                    Orbitron 字体安装助手                          ║
╠══════════════════════════════════════════════════════════════════╣
║ 🌐 在线安装：                                                    ║
║    https://fonts.google.com/specimen/Orbitron                   ║
║                                                                  ║
║ 📁 本地安装：                                                    ║
║    1. 下载 Orbitron-*.ttf 字体文件                              ║
║    2. 双击安装到系统                                             ║
║    3. 重启程序                                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""
                print(guide_text)

            return False  # 返回False表示需要手动完成

        except Exception as e:
            print(f"[FONT_ERROR] 字体安装助手启动失败: {e}")
            return False

    def install_font_files(self, font_files):
        """尝试安装字体文件到系统"""
        try:
            if sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                success_count = 0
                for font_path in font_files:
                    try:
                        # Windows API安装字体
                        result = ctypes.windll.gdi32.AddFontResourceW(
                            font_path)
                        if result > 0:
                            success_count += 1
                            print(
                                f"[FONT_INFO] 已安装: {os.path.basename(font_path)}")
                    except Exception as e:
                        print(f"[FONT_WARNING] 安装字体失败 {font_path}: {e}")
                        continue

                if success_count > 0:
                    # 通知系统字体已改变
                    HWND_BROADCAST = 0xFFFF
                    WM_FONTCHANGE = 0x001D
                    ctypes.windll.user32.SendMessageW(
                        HWND_BROADCAST, WM_FONTCHANGE, 0, 0)
                    return True

            elif sys.platform.startswith("linux"):
                # Linux字体安装
                font_dir = os.path.expanduser("~/.local/share/fonts")
                os.makedirs(font_dir, exist_ok=True)

                success_count = 0
                for font_path in font_files:
                    try:
                        dest_path = os.path.join(
                            font_dir, os.path.basename(font_path))
                        with open(font_path, 'rb') as src, open(dest_path, 'wb') as dst:
                            dst.write(src.read())
                        success_count += 1
                        print(f"[FONT_INFO] 已复制到: {dest_path}")
                    except Exception as e:
                        print(f"[FONT_WARNING] 复制字体失败: {e}")

                if success_count > 0:
                    # 刷新字体缓存
                    os.system("fc-cache -f -v")
                    return True

            elif sys.platform == "darwin":
                # macOS字体安装
                font_dir = os.path.expanduser("~/Library/Fonts")
                os.makedirs(font_dir, exist_ok=True)

                success_count = 0
                for font_path in font_files:
                    try:
                        dest_path = os.path.join(
                            font_dir, os.path.basename(font_path))
                        with open(font_path, 'rb') as src, open(dest_path, 'wb') as dst:
                            dst.write(src.read())
                        success_count += 1
                        print(f"[FONT_INFO] 已安装到: {dest_path}")
                    except Exception as e:
                        print(f"[FONT_WARNING] 安装字体失败: {e}")

                return success_count > 0

        except Exception as e:
            print(f"[FONT_ERROR] 字体安装失败: {e}")

        return False

    def show_font_install_guide(self, font_dir=None):
        """显示字体安装指南"""
        guide_message = """
═══════════════════════════════════════
        Orbitron 字体安装指南
═══════════════════════════════════════

自动安装失败，请手动安装：

方法一：在线下载
1. 访问：https://fonts.google.com/specimen/Orbitron
2. 点击 "Download family" 下载字体包
3. 解压后双击 .ttf 文件安装

方法二：使用本地文件（如果已下载）"""

        if font_dir and os.path.exists(font_dir):
            guide_message += f"""
4. 打开文件夹：{font_dir}
5. 双击字体文件进行安装"""

        guide_message += """

安装完成后重启程序即可使用 Orbitron 字体！
═══════════════════════════════════════
"""

        print(guide_message)

        # 在GUI中也显示提示
        if hasattr(self, 'root'):
            self.show_messagebox(
                "字体自动安装失败\n请查看控制台获取安装指南",
                "字体安装",
                self.colors.get("neon_yellow", "#FFD700")
            )

    def __init__(self):
        try:
            # 初始化字体配置
            self.setup_fonts()
        except Exception as e:
            print(f"[ERROR] 字体初始化失败: {e}")
            # 使用默认字体继续运行

        # Cyberpunk配色方案 - 现代化优化
        self.colors = {
            "bg_primary": "#0B0E1A",     # 更深的主背景，减少眼疲劳
            "bg_secondary": "#1A1D2E",   # 次要背景
            "bg_accent": "#262B40",      # 强调背景，更柔和
            "neon_cyan": "#00E5FF",      # 更亮的霓虹青色
            "neon_green": "#39FF14",     # 更鲜艳的霓虹绿色
            "neon_pink": "#FF006E",      # 调整的霓虹粉色
            "neon_purple": "#9D4EDD",    # 更饱和的霓虹紫色
            "neon_yellow": "#FFD23F",    # 温暖的霓虹黄色
            "neon_orange": "#FF6B35",    # 活力橙色
            "neon_red": "#FF073A",       # 霓虹红色
            "neon_blue": "#3D5AFE",      # 现代蓝色
            "text_primary": "#EAEAEA",   # 高对比度主文本
            "text_secondary": "#B8B8B8",  # 次要文本
            "text_accent": "#9E9E9E",    # 强调文本
            "text_dim": "#757575",       # 暗色文本
            "border_light": "#4A5568",   # 浅色边框
            "border_dark": "#2D3748",    # 深色边框
            "error_red": "#FF5252",      # 现代化错误红色
            "success_green": "#4CAF50",  # 成功绿色
            "warning_yellow": "#FFC107",  # 警告黄色
        }

        # JASON阶段机制系统 - 修改为动态配置模式
        self.jason_config = {}  # 保留作为兼容性备份，主要使用 current_act_config
        self.current_act_config = None  # 当前选择的ACT配置文件，包含JASON阶段信息
        self.current_jason_phase = 1
        self.jason_phase_start_time = None
        self.jason_rage_start_time = None
        self.jason_phases_completed = []
        self.jason_combat_start_time = None
        self.jason_phase_damage_start = 0
        self.jason_auto_advance_enabled = True

        # RGB动画相关
        self.rgb_animation_running = False
        self.rgb_color_index = 0
        self.rgb_gradient_step = 0
        self.rgb_interval = 200  # 大幅提高间隔，彻底解决卡顿
        self._last_rgb_color = None  # 缓存上次颜色，避免重复渲染
        self._animation_frame_skip = 0  # 帧跳过计数器，进一步优化
        self.rgb_colors = [
            "#ff0000",
            "#ff4000",
            "#ff8000",
            "#ffff00",
            "#80ff00",
            "#00ff00",
            "#00ff80",
            "#00ffff",
            "#0080ff",
            "#0000ff",
            "#8000ff",
            "#ff00ff",
            "#ff0080",
        ]
        # 边框RGB动画
        self.border_frame = None
        self.border_colors = []
        self.generate_gradient_colors()

        # 圆角样式配置
        self.rounded_styles = {
            "button_relief": "flat",
            "frame_relief": "flat",
            "panel_relief": "flat",
            "border_width": 0,
            "inner_border": 1,
            "corner_radius": 8,
            "shadow_offset": 2,
        }

        self.root = tk.Tk()

        # 初始化拖拽数据
        self.drag_data = {"x": 0, "y": 0}

        self.setup_window()
        self.setup_ui()

        # 数据相关
        self.api_url = "http://localhost:8989/api/data"
        self.clear_url = "http://localhost:8989/api/clear"
        self.logs_url = "http://localhost:8989/api/logs"  # 新增日志API
        self.running = False
        self.update_thread = None
        self.test_mode = False
        self.test_counter = 0

        # 存储当前数据
        self.current_data = {}

        # 直接数据传递模式
        self.direct_mode = False
        self.data_source = None  # 数据源对象引用
        self.data_lock = threading.Lock()  # 数据同步锁

        # UID用户名映射
        self.uid_name_mapping = {}  # UID -> 用户名映射
        try:
            self.load_uid_mapping()  # 加载保存的映射
        except Exception as e:
            print(f"[ERROR] 加载UID映射失败: {e}")
            self.uid_name_mapping = {}

        # 个人UID设置
        self.personal_uid = None  # 个人UID
        try:
            self.load_personal_uid()  # 加载个人UID设置
        except Exception as e:
            print(f"[ERROR] 加载个人UID失败: {e}")
            self.personal_uid = None

        # 自动UID映射检测
        self.auto_uid_mapping = True  # 是否启用自动UID映射
        self.uid_mapping_thread = None  # UID映射检测线程
        self.server_log_monitor_running = False  # 服务器日志监控运行状态
        self.processed_lines = set()  # 已处理的日志行，避免重复处理

        # 延迟启动这些功能，避免初始化时卡顿
        # 这些将在UI完全加载后启动
        self._delayed_start_scheduled = False

        # 初始化TTS功能
        self.tts_engine = None
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            # 设置语音参数
            voices = self.tts_engine.getProperty('voices')
            if voices:
                # 优先选择中文语音
                for voice in voices:
                    if 'chinese' in voice.name.lower() or 'mandarin' in voice.name.lower():
                        self.tts_engine.setProperty('voice', voice.id)
                        break
            # 设置语速和音量
            self.tts_engine.setProperty('rate', 150)  # 语速
            self.tts_engine.setProperty('volume', 0.8)  # 音量
            print("[INFO] TTS引擎初始化成功")
        except Exception as e:
            print(f"[WARNING] TTS引擎初始化失败: {e}")
            self.tts_engine = None

        # 初始化TTS队列系统
        self.tts_queue = queue.PriorityQueue()  # 优先级队列
        self.tts_worker_thread = None
        self.tts_worker_running = False
        self.start_tts_worker()

        # 伤害统计相关
        self.total_damage = 0  # 全团总伤害

        # 初始化全局键盘监听
        self.hidden_by_home = False  # 是否被HOME键隐藏
        self.keyboard_listener = None
        self.init_global_hotkey()

        # 启动RGB动画（这个比较轻量）
        self.start_rgb_animation()

        # 添加主窗口淡入效果
        self.root.after(100, lambda: self.fade_window_in(
            self.root, self.current_alpha, 0.2))

    def set_data_source(self, data_source):
        """设置直接数据源"""
        with self.data_lock:
            self.data_source = data_source
        self.update_status("[DIRECT_MODE] 已连接数据源，点击DIRECT按钮启动直接模式")
        self.show_messagebox(
            "已连接数据源，点击DIRECT按钮启动直接模式",
            title="DIRECT MODE",
            color=self.colors["neon_cyan"],
        )

    def get_direct_data(self):
        """从数据源获取数据"""
        if not self.data_source:
            return None

        try:
            with self.data_lock:
                # 从UserDataManager获取数据
                all_users_data = self.data_source.getAllUsersData()
                if not all_users_data:
                    return {"code": 0, "user": {}}

                # 转换数据格式以匹配ACT UI的期望格式
                user_data = {}
                for uid, user_summary in all_users_data.items():
                    user_data[uid] = {
                        "realtime_dps": user_summary.get("realtime_dps", 0),
                        "realtime_dps_max": user_summary.get("realtime_dps_max", 0),
                        "total_dps": user_summary.get("total_dps", 0),
                        "total_damage": user_summary.get("total_damage", {
                            "normal": 0,
                            "critical": 0,
                            "lucky": 0,
                            "crit_lucky": 0,
                            "hpLessen": 0,
                            "total": 0,
                        }),
                        "total_count": user_summary.get("total_count", {
                            "normal": 0,
                            "critical": 0,
                            "lucky": 0,
                            "total": 0,
                        }),
                        "profession": user_summary.get("profession", "未知"),
                        "taken_damage": user_summary.get("taken_damage", 0),
                        "total_healing": user_summary.get("total_healing", {
                            "normal": 0,
                            "critical": 0,
                            "lucky": 0,
                            "crit_lucky": 0,
                            "hpLessen": 0,
                            "total": 0,
                        }),
                        "total_hps": user_summary.get("total_hps", 0),
                        "realtime_hps": user_summary.get("realtime_hps", 0),
                        "realtime_hps_max": user_summary.get("realtime_hps_max", 0),
                    }

                return {"code": 0, "user": user_data}

        except Exception as e:
            self.update_status(f"[DIRECT_ERROR] 获取数据失败: {e}")
            return None

    def clear_direct_data(self):
        """清除直接模式的数据"""
        if not self.data_source:
            return False

        try:
            with self.data_lock:
                # 使用UserDataManager的clearAll方法清除数据
                self.data_source.clearAll()
                return True
        except Exception as e:
            self.update_status(f"[DIRECT_ERROR] 清除数据失败: {e}")
            return False

    def load_uid_mapping(self):
        """加载保存的UID用户名映射"""
        try:
            # 处理不同的路径情况
            possible_paths = [
                "uid_mapping.json",  # 当前目录
                self.get_resource_path("uid_mapping.json"),  # 资源目录
                os.path.join(os.getcwd(), "uid_mapping.json"),  # 工作目录
            ]

            mapping_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    mapping_file = path
                    break

            if mapping_file:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    self.uid_name_mapping = json.load(f)
                self.update_status(
                    f"[CONFIG] 已加载 {len(self.uid_name_mapping)} 个UID映射 (从 {mapping_file})")
            else:
                self.uid_name_mapping = {}
                self.update_status("[CONFIG] 未找到uid_mapping.json文件，使用空映射")
        except Exception as e:
            self.uid_name_mapping = {}
            self.update_status(f"[CONFIG] 加载UID映射失败: {e}")

    def save_uid_mapping(self):
        """保存UID用户名映射"""
        try:
            # 优先保存到当前工作目录（避免打包后路径问题）
            mapping_file = os.path.join(os.getcwd(), "uid_mapping.json")

            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.uid_name_mapping, f,
                          ensure_ascii=False, indent=2)
            self.update_status(
                f"[CONFIG] 已保存 {len(self.uid_name_mapping)} 个UID映射到 {mapping_file}")
        except Exception as e:
            self.update_status(f"[CONFIG] 保存UID映射失败: {e}")

    def load_personal_uid(self):
        """加载个人UID设置"""
        try:
            # 处理不同的路径情况
            possible_paths = [
                "personal_uid.txt",  # 当前目录
                os.path.join(os.getcwd(), "personal_uid.txt"),  # 工作目录
                self.get_resource_path("personal_uid.txt"),  # 资源目录
            ]

            uid_file = None
            for path in possible_paths:
                if os.path.exists(path):
                    uid_file = path
                    break

            if uid_file:
                with open(uid_file, 'r', encoding='utf-8') as f:
                    self.personal_uid = f.read().strip()
                self.update_status(f"[CONFIG] 已加载个人UID: {self.personal_uid}")
            else:
                self.personal_uid = None
                self.update_status("[CONFIG] 未找到个人UID设置")
        except Exception as e:
            self.personal_uid = None
            self.update_status(f"[CONFIG] 加载个人UID失败: {e}")

    def save_personal_uid(self, uid):
        """保存个人UID设置"""
        try:
            # 优先保存到当前工作目录
            uid_file = os.path.join(os.getcwd(), "personal_uid.txt")

            with open(uid_file, 'w', encoding='utf-8') as f:
                f.write(uid)
            self.personal_uid = uid
            self.update_status(f"[CONFIG] 已保存个人UID: {uid}")
            return True
        except Exception as e:
            self.update_status(f"[CONFIG] 保存个人UID失败: {e}")
            return False

    def start_uid_mapping_monitor(self):
        """启动UID映射监控"""
        if not self.auto_uid_mapping:
            return

        if self.uid_mapping_thread and self.uid_mapping_thread.is_alive():
            return

        self.server_log_monitor_running = True
        self.uid_mapping_thread = threading.Thread(
            target=self._uid_mapping_monitor_loop, daemon=True)
        self.uid_mapping_thread.start()
        self._safe_update_status("[AUTO_UID] 已启动API自动UID映射检测")

    def stop_uid_mapping_monitor(self):
        """停止UID映射监控"""
        self.server_log_monitor_running = False
        if self.uid_mapping_thread and self.uid_mapping_thread.is_alive():
            try:
                self.uid_mapping_thread.join(timeout=2)
            except:
                pass
        self._safe_update_status("[AUTO_UID] 已停止自动UID映射检测")

    def _uid_mapping_monitor_loop(self):
        """UID映射监控循环 - 通过API获取"""
        import time

        # 初始延迟，让主程序先完全启动
        time.sleep(1)

        self._safe_update_status("[AUTO_UID] 开始通过API监控UID映射...")

        consecutive_errors = 0
        max_consecutive_errors = 10

        while self.server_log_monitor_running:
            try:
                # 通过API获取UID映射（不再需要正则表达式）
                success = self._read_server_logs(None)

                if success:
                    # 重置错误计数
                    consecutive_errors = 0
                    # API调用成功，使用较短间隔
                    sleep_time = 3.0
                else:
                    consecutive_errors += 1
                    # API调用失败，逐渐增加间隔
                    sleep_time = min(10.0, 3.0 + consecutive_errors * 0.5)

                # 如果连续错误太多，报告状态
                if consecutive_errors == 5:
                    self._safe_update_status("[AUTO_UID] 服务器连接困难，继续尝试...")
                elif consecutive_errors >= max_consecutive_errors:
                    self._safe_update_status("[AUTO_UID] 服务器长时间无响应，降低检查频率...")
                    sleep_time = 15.0  # 长时间失败时降低频率

                time.sleep(sleep_time)

            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:  # 只在前几次错误时报告
                    self._safe_update_status(
                        f"[AUTO_UID] 监控异常 ({consecutive_errors}): {e}")

                # 错误时等待更长时间
                sleep_time = min(10, 3 + consecutive_errors)
                time.sleep(sleep_time)

        self._safe_update_status("[AUTO_UID] UID映射监控已停止")

    def _safe_update_status(self, message):
        """线程安全的状态更新"""
        try:
            if hasattr(self, 'root') and self.root:
                self.root.after(0, lambda: self.update_status(message))
            else:
                # 如果没有UI，就打印到控制台
                print(f"[UID_MONITOR] {message}")
        except:
            print(f"[UID_MONITOR] {message}")

    def _read_server_logs(self, pattern):
        """从服务器API获取UID映射"""
        try:
            # 使用新的UID映射API（基于现有的API URL构建）
            import requests
            base_url = "http://localhost:8989"  # 和其他API保持一致
            response = requests.get(
                f"{base_url}/api/uid-mappings", timeout=1.0)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 0:
                    mappings = data.get('mappings', {})

                    # 检查是否有新的映射
                    new_mappings_found = False
                    for uid, name in mappings.items():
                        if uid not in self.uid_name_mapping:
                            # 新的UID映射
                            self.uid_name_mapping[uid] = name
                            new_mappings_found = True
                            self._safe_update_status(
                                f"[AUTO_UID] 发现新映射: {uid} -> {name}")
                        elif self.uid_name_mapping[uid] != name:
                            # 更新已有映射（用户名变化）
                            old_name = self.uid_name_mapping[uid]
                            self.uid_name_mapping[uid] = name
                            new_mappings_found = True
                            self._safe_update_status(
                                f"[AUTO_UID] 更新映射: {uid} {old_name} -> {name}")

                    # 如果有新映射，自动保存
                    if new_mappings_found:
                        try:
                            self.save_uid_mapping()
                        except Exception as e:
                            self._safe_update_status(f"[AUTO_UID] 保存映射失败: {e}")

                    return True
        except requests.exceptions.Timeout:
            # 超时是正常的，不需要报错
            pass
        except requests.exceptions.ConnectionError:
            # 连接错误也是正常的（服务器可能没启动）
            pass
        except Exception:
            # 其他错误也静默处理
            pass
        return False

    def _process_log_line(self, log_line, pattern):
        """处理单行日志"""
        if not log_line or log_line in self.processed_lines:
            return

        # 添加到已处理集合（限制大小避免内存泄漏）
        self.processed_lines.add(log_line)
        if len(self.processed_lines) > 1000:
            # 保留最近的500行
            recent_lines = list(self.processed_lines)[-500:]
            self.processed_lines = set(recent_lines)

        # 匹配玩家信息
        match = pattern.search(log_line)
        if match:
            player_name = match.group(1).strip()
            uuid = match.group(2).strip()

            # 检查是否需要更新映射（新UID或同UID不同用户名）
            if uuid not in self.uid_name_mapping:
                # 新的UID映射
                self.uid_name_mapping[uuid] = player_name
                self._safe_update_status(
                    f"[AUTO_UID] 发现新映射: {uuid} -> {player_name}")

                # 自动保存映射
                try:
                    self.save_uid_mapping()
                except Exception as e:
                    self._safe_update_status(f"[AUTO_UID] 保存映射失败: {e}")
            elif self.uid_name_mapping[uuid] != player_name:
                # 同UID但用户名不同，覆盖原有映射
                old_name = self.uid_name_mapping[uuid]
                self.uid_name_mapping[uuid] = player_name
                self._safe_update_status(
                    f"[AUTO_UID] 更新映射: {uuid} -> {player_name} (原: {old_name})")

                # 自动保存映射
                try:
                    self.save_uid_mapping()
                except Exception as e:
                    self._safe_update_status(f"[AUTO_UID] 保存映射失败: {e}")

    def toggle_auto_uid_mapping(self, enabled):
        """切换自动UID映射功能"""
        self.auto_uid_mapping = enabled
        if enabled:
            if not self.server_log_monitor_running:
                self.start_uid_mapping_monitor()
        else:
            if self.server_log_monitor_running:
                self.stop_uid_mapping_monitor()

        status = "启用" if enabled else "禁用"
        self._safe_update_status(f"[AUTO_UID] 已{status}自动UID映射检测")

    def get_display_name(self, uid):
        """获取显示名称，优先使用用户设置的名称"""
        return self.uid_name_mapping.get(uid, uid)

    def show_personal_uid_dialog(self, callback=None):
        """显示个人UID输入对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("◊ 个人UID设置 ◊")
        dialog.geometry("450x350")
        dialog.resizable(False, False)
        dialog.wm_attributes("-topmost", True)
        dialog.configure(bg="#000000")
        dialog.overrideredirect(True)

        # 创建拖拽数据
        dialog_drag_data = {"x": 0, "y": 0}

        # 拖拽功能
        def start_drag(event):
            dialog_drag_data["x"] = event.x
            dialog_drag_data["y"] = event.y

        def on_drag(event):
            if dialog_drag_data["x"] != 0 or dialog_drag_data["y"] != 0:
                x = dialog.winfo_x() + (event.x - dialog_drag_data["x"])
                y = dialog.winfo_y() + (event.y - dialog_drag_data["y"])
                dialog.geometry(f"+{x}+{y}")

        def stop_drag(event):
            dialog_drag_data["x"] = 0
            dialog_drag_data["y"] = 0

        # 创建RGB边框（更厚的边框）
        border_frame = tk.Frame(dialog, bg="#ff0000", bd=0, relief="flat")
        border_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # 创建主框架
        main_frame = tk.Frame(
            border_frame, bg=self.colors["bg_primary"], bd=0, relief="flat")
        main_frame.pack(fill="both", expand=True, padx=3, pady=3)

        # 为主框架添加拖拽功能
        main_frame.bind("<Button-1>", start_drag)
        main_frame.bind("<B1-Motion>", on_drag)
        main_frame.bind("<ButtonRelease-1>", stop_drag)

        # 标题 - 更大更华丽
        title_canvas = self.create_shadow_text_canvas(
            main_frame,
            text="▓▓▓ [PERSONAL_UID_CONFIG] ▓▓▓",
            font_tuple=self.get_font(16, "bold"),
            fg_color=self.colors["neon_cyan"],
            bg_color=self.colors["bg_primary"],
            height=50
        )
        title_canvas.pack(fill="x", pady=(20, 15))

        # 副标题
        subtitle_canvas = self.create_shadow_text_canvas(
            main_frame,
            text="◊ SYSTEM_INITIALIZATION ◊",
            font_tuple=self.get_font(12, "normal"),
            fg_color=self.colors["neon_yellow"],
            bg_color=self.colors["bg_primary"],
            height=30
        )
        subtitle_canvas.pack(fill="x", pady=(0, 20))

        # 说明文字 - 使用Cyberpunk风格
        info_lines = [
            "[INFO]: 配置个人UID以启用MINI窗口个人数据显示",
            "[NOTICE]: 此设置将自动保存，无需重复输入"
        ]

        for line in info_lines:
            info_canvas = self.create_shadow_text_canvas(
                main_frame,
                text=line,
                font_tuple=self.get_font(9),
                fg_color=self.colors["text_primary"],
                bg_color=self.colors["bg_primary"],
                height=25
            )
            info_canvas.pack(fill="x", pady=2)

        # 输入区域 - 增强的Cyberpunk框架
        input_outer, input_frame = self.create_rounded_frame(
            main_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_green"],
            padding=3
        )
        input_outer.pack(fill="x", padx=25, pady=(20, 25))

        # UID输入标签 - 使用阴影效果
        label_canvas = self.create_shadow_text_canvas(
            input_frame,
            text="[UID_INPUT]:",
            font_tuple=self.get_font(12, "bold"),
            fg_color=self.colors["neon_yellow"],
            bg_color=self.colors["bg_secondary"],
            height=35
        )
        label_canvas.pack(fill="x", pady=(10, 5))

        # UID输入框 - 更大更明显
        uid_entry = tk.Entry(
            input_frame,
            font=self.get_font(12),
            bg=self.colors["bg_primary"],
            fg=self.colors["neon_cyan"],
            insertbackground=self.colors["neon_cyan"],
            bd=0,
            relief="flat",
            width=30,
            justify="center"
        )
        uid_entry.pack(pady=(5, 15), ipady=8)

        # 如果已有个人UID，预填充
        if self.personal_uid:
            uid_entry.insert(0, self.personal_uid)

        # 按钮区域
        button_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        button_frame.pack(fill="x", padx=25, pady=(0, 25))

        def save_and_close():
            uid = uid_entry.get().strip()
            if uid:
                if self.save_personal_uid(uid):
                    self.show_messagebox(
                        f"个人UID已保存: {uid}",
                        title="保存成功",
                        color=self.colors["success_green"]
                    )
                    dialog.destroy()
                    if callback:
                        callback()
                else:
                    self.show_messagebox(
                        "保存失败，请重试",
                        title="错误",
                        color=self.colors["error_red"]
                    )
            else:
                self.show_messagebox(
                    "请输入有效的UID",
                    title="输入错误",
                    color=self.colors["warning_yellow"]
                )

        def cancel_close():
            dialog.destroy()

        # 保存按钮
        save_btn = self.create_enhanced_button(
            button_frame, "◊ 保存", save_and_close,
            self.colors["neon_green"], width=12, height=2
        )
        save_btn.pack(side="left", padx=(0, 10))

        # 取消按钮
        cancel_btn = self.create_enhanced_button(
            button_frame, "✕ 取消", cancel_close,
            self.colors["neon_pink"], width=12, height=2
        )
        cancel_btn.pack(side="left")

        # 如果没有个人UID，显示跳过按钮
        if not self.personal_uid:
            skip_btn = self.create_enhanced_button(
                button_frame, "⏭ 跳过", lambda: (
                    dialog.destroy(), callback() if callback else None),
                self.colors["text_secondary"], width=12, height=2
            )
            skip_btn.pack(side="right")

        # RGB边框动画
        dialog_gradient_step = 0

        def animate_dialog_border():
            nonlocal dialog_gradient_step
            if dialog.winfo_exists():
                try:
                    if hasattr(self, 'border_colors') and self.border_colors:
                        current_color = self.border_colors[dialog_gradient_step]
                        border_frame.configure(bg=current_color)
                        dialog_gradient_step = (
                            dialog_gradient_step + 1) % len(self.border_colors)
                    dialog.after(150, animate_dialog_border)
                except:
                    pass

        # 启动边框动画
        animate_dialog_border()

        # 窗口居中
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # 聚焦到输入框
        uid_entry.focus_set()

        # 绑定回车键
        uid_entry.bind("<Return>", lambda e: save_and_close())

    def show_uid_mapping_dialog(self):
        """显示UID用户名映射配置对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("◊ UID用户名映射配置 ◊")
        dialog.geometry("600x500")
        dialog.resizable(True, True)
        dialog.wm_attributes("-topmost", True)
        dialog.configure(bg="#000000")

        # 设置无边框 (在所有Tkinter操作之后)
        dialog.overrideredirect(True)

        # 创建拖拽数据
        dialog_drag_data = {"x": 0, "y": 0}

        # 拖拽功能
        def start_drag(event):
            dialog_drag_data["x"] = event.x
            dialog_drag_data["y"] = event.y

        def on_drag(event):
            if dialog_drag_data["x"] != 0 or dialog_drag_data["y"] != 0:
                x = dialog.winfo_x() + (event.x - dialog_drag_data["x"])
                y = dialog.winfo_y() + (event.y - dialog_drag_data["y"])
                dialog.geometry(f"+{x}+{y}")

        def stop_drag(event):
            dialog_drag_data["x"] = 0
            dialog_drag_data["y"] = 0

        # 创建RGB边框
        border_frame = tk.Frame(dialog, bg="#ff0000", bd=0, relief="flat")
        border_frame.pack(fill="both", expand=True, padx=3, pady=3)

        # 创建主框架
        main_frame = tk.Frame(
            border_frame, bg=self.colors["bg_primary"], bd=0, relief="flat")
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # 为标题区域添加拖拽功能
        main_frame.bind("<Button-1>", start_drag)
        main_frame.bind("<B1-Motion>", on_drag)
        main_frame.bind("<ButtonRelease-1>", stop_drag)

        # 标题
        title_canvas = self.create_shadow_text_canvas(
            main_frame,
            text="▓▓▓ UID用户名映射管理 ▓▓▓",
            font_tuple=self.get_font(12, "bold"),
            fg_color=self.colors["neon_cyan"],
            bg_color=self.colors["bg_primary"],
            height=30
        )
        title_canvas.pack(fill="x", pady=(10, 10))

        # 在标题区域添加顶部关闭按钮
        top_close_btn = self.create_enhanced_button(
            main_frame, "✕", dialog.destroy,
            self.colors["neon_pink"], width=3, height=1
        )
        top_close_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # 为标题区域也添加拖拽功能
        title_canvas.bind("<Button-1>", start_drag)
        title_canvas.bind("<B1-Motion>", on_drag)
        title_canvas.bind("<ButtonRelease-1>", stop_drag)

        # RGB边框动画
        dialog_gradient_step = 0

        def animate_dialog_border():
            nonlocal dialog_gradient_step
            if dialog.winfo_exists():
                try:
                    # 使用和主UI相同的渐变颜色
                    if hasattr(self, 'border_colors') and self.border_colors:
                        current_color = self.border_colors[dialog_gradient_step]
                        border_frame.configure(bg=current_color)
                        dialog_gradient_step = (
                            dialog_gradient_step + 1) % len(self.border_colors)

                    # 使用和主UI相同的速度 - 100ms间隔
                    dialog.after(100, animate_dialog_border)
                except:
                    pass

        # 启动边框动画
        animate_dialog_border()

        # 输入区域
        input_frame = tk.Frame(
            main_frame, bg=self.colors["bg_secondary"], relief="raised", bd=2)
        input_frame.pack(fill="x", pady=(0, 10))

        # UID输入
        uid_frame = tk.Frame(input_frame, bg=self.colors["bg_secondary"])
        uid_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(uid_frame, text="UID:", font=self.get_font(9),
                 bg=self.colors["bg_secondary"], fg=self.colors["text_primary"]).pack(side="left")
        uid_entry_container = self.create_rounded_entry(uid_frame, width=20)
        uid_entry_container.pack(side="left", padx=(10, 0))
        uid_entry = uid_entry_container.entry if hasattr(
            uid_entry_container, 'entry') else uid_entry_container

        # 用户名输入
        name_frame = tk.Frame(input_frame, bg=self.colors["bg_secondary"])
        name_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(name_frame, text="用户名:", font=self.get_font(9),
                 bg=self.colors["bg_secondary"], fg=self.colors["text_primary"]).pack(side="left")
        name_entry_container = self.create_rounded_entry(name_frame, width=20)
        name_entry_container.pack(side="left", padx=(10, 0))
        name_entry = name_entry_container.entry if hasattr(
            name_entry_container, 'entry') else name_entry_container

        # 自动映射开关
        auto_frame = tk.Frame(input_frame, bg=self.colors["bg_secondary"])
        auto_frame.pack(fill="x", padx=10, pady=5)

        auto_var = tk.BooleanVar(value=self.auto_uid_mapping)
        auto_check = tk.Checkbutton(
            auto_frame,
            text="自动从服务器API检测UID映射 (每2-5秒，覆盖重名)",
            variable=auto_var,
            font=self.get_font(9),
            bg=self.colors["bg_secondary"],
            fg=self.colors["neon_green"],
            selectcolor=self.colors["bg_accent"],
            activebackground=self.colors["bg_secondary"],
            activeforeground=self.colors["neon_green"],
            command=lambda: self.toggle_auto_uid_mapping(auto_var.get())
        )
        auto_check.pack(side="left")

        # 状态指示
        status_label = tk.Label(
            auto_frame,
            text=f"[监控状态: {'运行中' if self.server_log_monitor_running else '已停止'}]",
            font=self.get_font(8),
            bg=self.colors["bg_secondary"],
            fg=self.colors["neon_cyan"] if self.server_log_monitor_running else self.colors["text_accent"]
        )
        status_label.pack(side="right")

        # 按钮区域
        button_frame = tk.Frame(input_frame, bg=self.colors["bg_secondary"])
        button_frame.pack(fill="x", padx=10, pady=5)

        def add_mapping():
            uid = uid_entry.get().strip()
            name = name_entry.get().strip()
            if uid and name:
                self.uid_name_mapping[uid] = name
                self.save_uid_mapping()
                uid_entry.delete(0, tk.END)
                name_entry.delete(0, tk.END)
                refresh_list()
                self.update_status(f"[CONFIG] 已添加映射: {uid} -> {name}")

        def delete_mapping():
            selection = mapping_list.curselection()
            if selection:
                index = selection[0]
                uid = list(self.uid_name_mapping.keys())[index]
                del self.uid_name_mapping[uid]
                self.save_uid_mapping()
                refresh_list()
                self.update_status(f"[CONFIG] 已删除映射: {uid}")

        # 添加按钮
        add_btn = self.create_enhanced_button(button_frame, "◊ 添加", add_mapping,
                                              self.colors["neon_green"], width=8)
        add_btn.pack(side="left", padx=(0, 5))

        # 删除按钮
        del_btn = self.create_enhanced_button(button_frame, "✕ 删除", delete_mapping,
                                              self.colors["neon_pink"], width=8)
        del_btn.pack(side="left")

        # 映射列表区域
        list_frame = tk.Frame(
            main_frame, bg=self.colors["bg_secondary"], relief="raised", bd=2)
        list_frame.pack(fill="both", expand=True)

        # 列表标题
        list_title = self.create_shadow_text_canvas(
            list_frame,
            text="[当前映射列表]:",
            font_tuple=self.get_font(10, "bold"),
            fg_color=self.colors["neon_orange"],
            bg_color=self.colors["bg_secondary"],
            height=25
        )
        list_title.pack(fill="x", pady=5)

        # 滚动列表（圆角版本）
        list_container = self.create_rounded_listbox(list_frame, height=12)
        list_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 获取实际的listbox控件
        mapping_list = list_container.listbox
        scrollbar = list_container.scrollbar

        def refresh_list():
            """刷新UID映射列表，包括从API获取最新数据"""
            # 首先尝试从API获取最新映射
            try:
                import requests
                response = requests.get(
                    "http://localhost:8989/api/uid-mappings", timeout=2.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('code') == 0:
                        api_mappings = data.get('mappings', {})

                        # 合并API映射到本地映射
                        updated_count = 0
                        for uid, name in api_mappings.items():
                            if uid not in self.uid_name_mapping:
                                self.uid_name_mapping[uid] = name
                                updated_count += 1
                            elif self.uid_name_mapping[uid] != name:
                                self.uid_name_mapping[uid] = name
                                updated_count += 1

                        if updated_count > 0:
                            self.update_status(
                                f"[刷新] 从服务器获取到 {updated_count} 个新的或更新的映射")
                            # 保存更新的映射
                            try:
                                self.save_uid_mapping()
                            except Exception as e:
                                self.update_status(f"[刷新] 保存映射失败: {e}")
                        else:
                            self.update_status("[刷新] 映射已是最新")
                    else:
                        self.update_status(f"[刷新] API响应错误: {data.get('code')}")
                else:
                    self.update_status(f"[刷新] API请求失败: {response.status_code}")
            except requests.exceptions.ConnectionError:
                self.update_status("[刷新] 无法连接到服务器，使用本地映射")
            except Exception as e:
                self.update_status(f"[刷新] API获取失败: {e}")

            # 更新列表显示
            mapping_list.delete(0, tk.END)
            for uid, name in self.uid_name_mapping.items():
                mapping_list.insert(tk.END, f"{uid} → {name}")

        def on_list_select(event):
            selection = mapping_list.curselection()
            if selection:
                index = selection[0]
                uid = list(self.uid_name_mapping.keys())[index]
                name = self.uid_name_mapping[uid]
                uid_entry.delete(0, tk.END)
                uid_entry.insert(0, uid)
                name_entry.delete(0, tk.END)
                name_entry.insert(0, name)

        mapping_list.bind("<<ListboxSelect>>", on_list_select)

        # 按钮区域
        button_container = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        button_container.pack(fill="x", pady=(10, 10))

        # 关闭按钮
        close_btn = self.create_enhanced_button(button_container, "✕ 关闭", dialog.destroy,
                                                self.colors["neon_pink"], width=12)
        close_btn.pack(side="right", padx=(5, 0))

        # 刷新按钮
        refresh_btn = self.create_enhanced_button(button_container, "↻ 刷新", refresh_list,
                                                  self.colors["neon_orange"], width=12)
        refresh_btn.pack(side="right", padx=(5, 0))

        # 初始化列表
        refresh_list()

        # 窗口居中 (在overrideredirect之后进行)
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # 聚焦到UID输入框
        uid_entry.focus_set()

    def generate_gradient_colors(self):
        """生成现代化渐变颜色序列"""
        # 生成更平滑的现代化渐变色序列
        gradient_colors = []
        steps = 72  # 增加步数获得更平滑的渐变

        for i in range(steps):
            # 使用更饱和的色彩和更好的色相分布
            hue = i / steps
            saturation = 0.95  # 高饱和度
            brightness = 0.9   # 略微降低亮度，减少眼疲劳

            rgb = colorsys.hsv_to_rgb(hue, saturation, brightness)
            hex_color = "#{:02x}{:02x}{:02x}".format(int(rgb[0] * 255),
                                                     int(rgb[1] * 255),
                                                     int(rgb[2] * 255))
            gradient_colors.append(hex_color)

        self.border_colors = gradient_colors

    def setup_window(self):
        """设置窗口 - Cyberpunk风格（无边框圆角背景适配）"""
        self.root.title("◊ STAR_RESONANCE_ACT_CONSOLE ◊")
        self.root.geometry("920x980")  # 适中尺寸
        # 设置透明背景，让RGB边框成为真正的窗口边界
        self.root.configure(bg='black')  # 临时背景色，稍后会被遮罩

        # 无边框设计
        self.root.overrideredirect(True)

        # 启动时自动置顶
        self.root.wm_attributes("-topmost", True)

        # 设置半透明效果 - 默认值
        self.current_alpha = 0.95
        self.root.wm_attributes("-alpha", 0.0)  # 初始透明度为0，准备淡入

        # 在Windows系统上尝试设置圆角窗口
        try:
            import ctypes
            from ctypes import wintypes

            # 等待窗口完全创建
            self.root.update()

            # 获取窗口句柄
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd == 0:
                hwnd = self.root.winfo_id()

            # 创建圆角区域
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            corner_radius = 12  # 与边框圆角一致

            # 创建圆角矩形区域
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, width, height, corner_radius * 2, corner_radius * 2
            )

            if hrgn:
                # 应用圆角区域到窗口
                ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
                self._window_region_set = True
            else:
                self._window_region_set = False

        except Exception as e:
            print(f"[WINDOW] 圆角窗口设置失败，使用标准边框: {e}")
            self._window_region_set = False

        # 全局透明度变量，用于主界面和MINI界面同步
        self.global_alpha_var = tk.DoubleVar(value=self.current_alpha * 100)
        self.mini_windows = []  # 存储所有打开的MINI窗口引用
        self.timer_windows = []  # 存储所有打开的ACT timer窗口引用

        # 创建RGB边框容器
        self.create_rgb_border()

        # 设置窗口图标
        self._set_window_icon()

        # 窗口居中
        self._center_window()

        # 添加拖拽功能
        self._add_drag_functionality()

        # 关闭窗口时的处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 延迟字体验证（在窗口创建完成后）
        self.root.after(100, self.delayed_font_verification)

        # 绑定JASON阶段机制快捷键
        self.setup_jason_hotkeys()

    def setup_jason_hotkeys(self):
        """设置JASON阶段机制快捷键"""
        try:
            hotkeys = self.current_act_config.get(
                "hotkeys", {}) if self.current_act_config else {}

            # 绑定全局快捷键
            advance_key = hotkeys.get("advance_phase", "Prior")
            reset_key = hotkeys.get("reset_rage_time", "Next")

            self.root.bind(f"<KeyPress-{advance_key}>",
                           lambda e: self.advance_jason_phase())
            self.root.bind(f"<KeyPress-{reset_key}>",
                           lambda e: self.reset_jason_rage_time())

            # 绑定直接阶段选择快捷键
            for i in range(1, 4):
                phase_key = hotkeys.get(f"phase_{i}", f"F{i}")
                self.root.bind(
                    f"<KeyPress-{phase_key}>", lambda e, p=i: self.set_jason_phase(p))

            # 确保窗口可以接收键盘事件
            self.root.focus_set()

            print(
                f"[DEBUG] JASON快捷键已绑定: {advance_key}=推进阶段, {reset_key}=重置暴走时间")
        except Exception as e:
            print(f"[DEBUG] JASON快捷键绑定失败: {e}")

    def create_rgb_border(self):
        """创建RGB动画边框（完全填充窗口，圆角背景适配）"""
        # 边框设置，完全贴合窗口边缘
        self._border_padding = 0   # 完全贴边
        self._border_width = 3     # 边框粗细
        self._corner_radius = 12   # 与窗口圆角一致

        if Image is not None:
            # 使用Canvas作为窗口的完整背景
            self.border_canvas = tk.Canvas(
                self.root, bg=self.colors["bg_primary"], highlightthickness=0, bd=0)
            self.border_canvas.pack(fill="both", expand=True, padx=0, pady=0)

            # 主内容容器，留出边框空间
            if not hasattr(self, "main_content_frame"):
                self.main_content_frame = tk.Frame(
                    self.border_canvas, bg=self.colors["bg_primary"], bd=0, relief="flat")

            # 在Canvas中创建窗口来放置主内容
            # 留出边框宽度的空间
            border_space = self._border_width + 3
            self.content_window = self.border_canvas.create_window(
                border_space, border_space,
                anchor="nw",
                window=self.main_content_frame
            )

            # 用于存储当前边框图像
            self._border_imgtk = None
            self._border_last_size = (0, 0)

            def on_resize(event):
                # 更新内容框架大小以匹配Canvas
                canvas_width = event.width
                canvas_height = event.height

                # 计算内容区域大小
                content_width = canvas_width - (border_space * 2)
                content_height = canvas_height - (border_space * 2)

                # 更新内容窗口大小
                self.border_canvas.itemconfig(
                    self.content_window,
                    width=content_width,
                    height=content_height
                )

                # 防抖处理，减少频繁重绘
                if hasattr(self, '_resize_timer'):
                    self.root.after_cancel(self._resize_timer)
                self._resize_timer = self.root.after(
                    50, self._render_border_image)

            self.border_canvas.bind("<Configure>", on_resize)
        else:
            # 回退：保持原来的矩形边框结构，去除黑边
            shadow_frame = tk.Frame(
                self.root, bg=self.colors["bg_primary"], bd=0, relief="flat")
            shadow_frame.pack(fill="both", expand=True, padx=0, pady=0)

            self.border_frame = tk.Frame(
                shadow_frame,
                bg="#ff0000",
                bd=0,
                relief="flat"
            )
            self.border_frame.pack(fill="both", expand=True, padx=3, pady=3)

            gradient_frame = tk.Frame(self.border_frame,
                                      bg=self.colors["bg_primary"],
                                      bd=0,
                                      relief="flat")
            gradient_frame.pack(fill="both", expand=True, padx=2, pady=2)

            self.main_content_frame = tk.Frame(gradient_frame,
                                               bg=self.colors["bg_primary"],
                                               bd=0,
                                               relief="flat")
            self.main_content_frame.pack(
                fill="both", expand=True, padx=6, pady=6)

    def _render_border_image(self):
        """渲染完整的圆角窗口背景与RGB边框"""
        if Image is None:
            return

        # 获取Canvas的实际尺寸
        canvas_w = self.border_canvas.winfo_width()
        canvas_h = self.border_canvas.winfo_height()
        if canvas_w <= 0 or canvas_h <= 0:
            return

        # 当前RGB颜色
        current_color = (self.border_colors[self.rgb_gradient_step]
                         if hasattr(self, "border_colors") and self.border_colors else "#ff0000")

        # 仅在尺寸或颜色变化时重绘
        key = (canvas_w, canvas_h, self._corner_radius,
               self._border_width, current_color)
        if getattr(self, "_border_cache_key", None) == key and self._border_imgtk is not None:
            return

        # 创建完整的窗口背景图像
        scale = 1.5  # 适度的抗锯齿
        W, H = int(canvas_w * scale), int(canvas_h * scale)
        r = max(0, int(self._corner_radius * scale))
        bw = max(1, int(self._border_width * scale))

        # 创建背景图像
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 绘制完整的圆角背景
        bg_color = self.colors["bg_primary"]
        draw.rounded_rectangle([0, 0, W-1, H-1], radius=r, fill=bg_color)

        # 添加RGB边框发光效果
        try:
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            # 在边缘绘制发光边框
            gdraw.rounded_rectangle([bw//2, bw//2, W-1-bw//2, H-1-bw//2],
                                    radius=r, outline=current_color, width=bw)
            # 轻微的发光效果
            glow = glow.filter(ImageFilter.GaussianBlur(1.5 * scale / 10))
            img = Image.alpha_composite(img, glow)
        except Exception:
            pass

        # 绘制清晰的RGB边框
        draw.rounded_rectangle([bw//2, bw//2, W-1-bw//2, H-1-bw//2],
                               radius=r, outline=current_color, width=bw)

        # 缩放到目标尺寸
        img = img.resize((canvas_w, canvas_h), resample=Image.LANCZOS)

        # 转换为Tkinter图像并显示
        imgtk = ImageTk.PhotoImage(img)
        self.border_canvas.delete("bg_image")
        self.border_canvas.create_image(
            0, 0, anchor="nw", image=imgtk, tags="bg_image")

        # 缓存
        self._border_imgtk = imgtk
        self._border_cache_key = key

    def _set_window_icon(self):
        """设置窗口图标"""
        try:
            icon_paths = [
                "icon.ico",
                os.path.join(os.path.dirname(__file__), "icon.ico"),
                (os.path.join(sys._MEIPASS, "icon.ico") if hasattr(
                    sys, "_MEIPASS") else None),
            ]

            for icon_path in icon_paths:
                if icon_path and os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
                    break
        except (tk.TclError, AttributeError):
            pass

    def _center_window(self):
        """窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")

    def _add_drag_functionality(self):
        """添加窗口拖拽功能 - 避免与控件冲突"""
        self.drag_data = {"x": 0, "y": 0}

        def start_drag(event):
            # 检查事件来源，避免在滑块、按钮等控件上触发拖拽
            widget_class = event.widget.__class__.__name__
            if widget_class in ['Scale', 'Button', 'Entry', 'Text', 'Listbox', 'Scrollbar']:
                return

            # 检查是否点击在滑块容器内
            if hasattr(event, 'stopPropagation'):
                return

            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

        def drag_window(event):
            # 同样检查事件来源
            widget_class = event.widget.__class__.__name__
            if widget_class in ['Scale', 'Button', 'Entry', 'Text', 'Listbox', 'Scrollbar']:
                return

            # 检查是否在滑块容器内
            if hasattr(event, 'stopPropagation'):
                return

            if self.drag_data["x"] != 0 or self.drag_data["y"] != 0:
                x = self.root.winfo_x() + (event.x - self.drag_data["x"])
                y = self.root.winfo_y() + (event.y - self.drag_data["y"])
                self.root.geometry(f"+{x}+{y}")

        def stop_drag(event):
            self.drag_data["x"] = 0
            self.drag_data["y"] = 0

        # 只为特定的容器组件添加拖拽绑定，避免子控件
        drag_widgets = [self.main_content_frame]

        for widget in drag_widgets:
            widget.bind("<Button-1>", start_drag)
            widget.bind("<B1-Motion>", drag_window)
            widget.bind("<ButtonRelease-1>", stop_drag)

    def create_rounded_frame(self,
                             parent,
                             bg_color=None,
                             border_color=None,
                             padding=5):
        """创建增强圆角风格的框架，更现代的内部UI效果"""
        if bg_color is None:
            bg_color = self.colors["bg_accent"]
        if border_color is None:
            border_color = self.colors["neon_cyan"]

        # 如果有Pillow，创建真正的圆角图像背景
        if Image is not None:
            return self._create_image_rounded_frame(parent, bg_color, border_color, padding)

        # 回退到传统的立体框架
        return self._create_traditional_rounded_frame(parent, bg_color, border_color, padding)

    def _create_image_rounded_frame(self, parent, bg_color, border_color, padding):
        """使用图像创建真正的圆角框架"""
        # 最外层容器
        outer_container = tk.Frame(
            parent, bg=parent.cget("bg"), relief="flat", bd=0)

        # 使用Canvas作为圆角背景
        canvas = tk.Canvas(
            outer_container,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0,
            height=100  # 初始高度，会自动调整
        )
        canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # 内容框架
        inner_frame = tk.Frame(canvas, bg=bg_color, bd=0, relief="flat")

        # 在Canvas中创建窗口
        content_window = canvas.create_window(
            padding + 2, padding + 2,
            anchor="nw",
            window=inner_frame
        )

        # 存储圆角相关信息
        canvas._rounded_bg = None
        canvas._last_size = (0, 0)
        canvas._bg_color = bg_color
        canvas._border_color = border_color
        canvas._padding = padding

        def render_rounded_bg():
            """渲染圆角背景"""
            canvas_w = canvas.winfo_width()
            canvas_h = canvas.winfo_height()

            if canvas_w <= 1 or canvas_h <= 1:
                canvas.after(50, render_rounded_bg)
                return

            # 更新内容窗口大小
            content_w = canvas_w - (padding + 2) * 2
            content_h = canvas_h - (padding + 2) * 2
            canvas.itemconfig(
                content_window, width=content_w, height=content_h)

            # 检查是否需要重新渲染
            current_size = (canvas_w, canvas_h)
            if canvas._last_size == current_size and canvas._rounded_bg is not None:
                return

            # 创建圆角背景图像
            radius = 8  # 内部UI使用较小的圆角
            border_width = 2

            scale = 1.5
            W, H = int(canvas_w * scale), int(canvas_h * scale)
            r = int(radius * scale)
            bw = int(border_width * scale)

            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 绘制圆角背景
            draw.rounded_rectangle([0, 0, W-1, H-1], radius=r, fill=bg_color)

            # 添加微妙的渐变效果
            try:
                # 创建轻微的内阴影
                shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow)
                shadow_draw.rounded_rectangle(
                    [3, 3, W-4, H-4], radius=r-2, fill=(0, 0, 0, 20)
                )
                shadow = shadow.filter(ImageFilter.GaussianBlur(2))
                img = Image.alpha_composite(img, shadow)
            except Exception:
                pass

            # 绘制圆角边框
            draw.rounded_rectangle(
                [bw//2, bw//2, W-1-bw//2, H-1-bw//2],
                radius=r, outline=border_color, width=bw
            )

            # 缩放并显示
            img = img.resize((canvas_w, canvas_h), Image.LANCZOS)
            bg_img = ImageTk.PhotoImage(img)

            canvas.delete("rounded_bg")
            canvas.create_image(0, 0, anchor="nw",
                                image=bg_img, tags="rounded_bg")
            canvas.tag_lower("rounded_bg")  # 确保背景在最底层

            # 保存引用防止被垃圾回收
            canvas._rounded_bg = bg_img
            canvas._last_size = current_size

        def on_canvas_configure(event):
            """Canvas大小改变时重新渲染"""
            if hasattr(canvas, '_render_timer'):
                canvas.after_cancel(canvas._render_timer)
            canvas._render_timer = canvas.after(50, render_rounded_bg)

        canvas.bind("<Configure>", on_canvas_configure)

        # 初始渲染
        canvas.after(100, render_rounded_bg)

        return outer_container, inner_frame

    def _create_traditional_rounded_frame(self, parent, bg_color, border_color, padding):
        """传统的立体圆角框架（回退方案）"""
        # 最外层容器
        outer_container = tk.Frame(
            parent,
            bg=parent.cget("bg"),
            relief="flat",
            bd=0,
        )

        # 外层框架 - 提供立体效果
        outer_frame = tk.Frame(
            outer_container,
            bg=border_color,
            relief="raised",  # 立体凸起效果
            bd=2,
        )
        outer_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # 内层框架
        inner_frame = tk.Frame(
            outer_frame,
            bg=bg_color,
            relief="sunken",  # 内凹效果增强立体感
            bd=1,
            highlightthickness=1,
            highlightcolor=border_color,
            highlightbackground=border_color,
        )
        inner_frame.pack(fill="both", expand=True, padx=padding, pady=padding)

        return outer_container, inner_frame

    def create_enhanced_button(self, parent, text, command, color, width=10, height=1, font_weight="bold"):
        """创建圆角按钮（仅四角圆角，抗锯齿；无Pillow则回退为方形按钮）"""
        if Image is None:
            # 回退：使用原本的方形按钮，避免锯齿圆角
            btn = tk.Button(
                parent, text=text, command=command,
                font=self.get_font(9, font_weight),
                bg=self.colors["bg_primary"], fg=color,
                activebackground=color, activeforeground=self.colors["bg_primary"],
                bd=3, relief="raised", cursor="hand2",
                width=width, height=height,
                highlightthickness=2, highlightcolor=color,
                highlightbackground=self.colors["bg_secondary"],
            )
            return btn

        # 以字符宽高估算像素尺寸
        px_w = max(80, width * 10 + 28)
        px_h = max(28, height * 20 + 10)
        radius = 12  # 增加圆角半径，更现代
        border_w = 2

        def make_btn_image(fill_bg, fg_border):
            scale = 3
            W, H = px_w * scale, px_h * scale
            r = radius * scale
            bw = border_w * scale
            img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 背景填充
            draw.rounded_rectangle([0, 0, W - 1, H - 1], r, fill=fill_bg)

            # 添加微妙的内阴影效果
            try:
                shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                s_draw = ImageDraw.Draw(shadow)
                s_draw.rounded_rectangle(
                    [2, 2, W-3, H-3], r-2, fill=(0, 0, 0, 30))
                shadow = shadow.filter(ImageFilter.GaussianBlur(1))
                img = Image.alpha_composite(img, shadow)
            except Exception:
                pass

            # 边框
            draw.rounded_rectangle([bw//2, bw//2, W - 1 - bw//2, H - 1 - bw//2],
                                   r, outline=fg_border, width=bw)
            img = img.resize((px_w, px_h), Image.LANCZOS)
            return ImageTk.PhotoImage(img)

        normal_img = make_btn_image(self.colors["bg_primary"], color)
        hover_img = make_btn_image(color, self.colors["bg_primary"])  # 反转
        active_img = make_btn_image(self.colors["bg_secondary"], color)

        btn = tk.Label(parent, text=text, font=self.get_font(9, font_weight),
                       fg=color, bg=parent.cget("bg"), cursor="hand2")
        btn._img_normal = normal_img
        btn._img_hover = hover_img
        btn._img_active = active_img
        btn.configure(image=normal_img, compound="center")

        def on_enter(_):
            btn.configure(image=btn._img_hover, fg=self.colors["bg_primary"])

        def on_leave(_):
            btn.configure(image=btn._img_normal, fg=color)

        def on_press(_):
            btn.configure(image=btn._img_active)

        def on_release(_):
            btn.configure(image=btn._img_hover)
            try:
                command()
            except Exception as e:
                self.update_status(f"[UI] 按钮执行失败: {e}")

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.bind("<Button-1>", on_press)
        btn.bind("<ButtonRelease-1>", on_release)

        return btn

    def create_rounded_entry(self, parent, textvariable=None, width=20, **kwargs):
        """创建圆角输入框"""
        if Image is None:
            # 回退到普通输入框
            entry = tk.Entry(
                parent,
                textvariable=textvariable,
                width=width,
                font=self.get_font(9),
                bg=self.colors["bg_secondary"],
                fg=self.colors["text_primary"],
                insertbackground=self.colors["neon_cyan"],
                relief="sunken",
                bd=2,
                **kwargs
            )
            return entry

        # 创建Canvas容器
        canvas = tk.Canvas(
            parent,
            height=26,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0
        )

        # 创建输入框
        entry = tk.Entry(
            canvas,
            textvariable=textvariable,
            width=width,
            font=self.get_font(9),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_primary"],
            insertbackground=self.colors["neon_cyan"],
            relief="flat",
            bd=0,
            **kwargs
        )

        # 在Canvas中放置输入框
        canvas.create_window(13, 13, window=entry)

        # 渲染圆角背景
        def render_entry_bg():
            canvas_w = canvas.winfo_width()
            if canvas_w <= 1:
                canvas.after(50, render_entry_bg)
                return

            radius = 6
            border_width = 1

            img = Image.new("RGBA", (canvas_w, 26), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 背景
            draw.rounded_rectangle(
                [0, 0, canvas_w-1, 25],
                radius=radius,
                fill=self.colors["bg_secondary"]
            )

            # 边框
            draw.rounded_rectangle(
                [border_width//2, border_width//2, canvas_w -
                    1-border_width//2, 25-border_width//2],
                radius=radius,
                outline=self.colors["neon_cyan"],
                width=border_width
            )

            bg_img = ImageTk.PhotoImage(img)
            canvas.delete("entry_bg")
            canvas.create_image(0, 0, anchor="nw",
                                image=bg_img, tags="entry_bg")
            canvas.tag_lower("entry_bg")
            canvas._entry_bg = bg_img

        def on_entry_configure(event):
            all_items = canvas.find_all()
            if len(all_items) > 1:  # 确保有足够的子项
                canvas.itemconfig(all_items[1], width=event.width-26)
            if hasattr(canvas, '_entry_timer'):
                canvas.after_cancel(canvas._entry_timer)
            canvas._entry_timer = canvas.after(50, render_entry_bg)

        canvas.bind("<Configure>", on_entry_configure)
        canvas.after(100, render_entry_bg)

        # 返回Canvas，但附带entry属性
        canvas.entry = entry
        return canvas

    def create_rounded_listbox(self, parent, height=10, **kwargs):
        """创建圆角列表框"""
        if Image is None:
            # 回退到普通列表框
            listbox_frame = tk.Frame(parent, bg=parent.cget("bg"))

            listbox = tk.Listbox(
                listbox_frame,
                height=height,
                font=self.get_font(9),
                bg=self.colors["bg_secondary"],
                fg=self.colors["text_primary"],
                selectbackground=self.colors["neon_cyan"],
                selectforeground=self.colors["bg_primary"],
                relief="sunken",
                bd=2,
                **kwargs
            )

            scrollbar = tk.Scrollbar(listbox_frame)
            listbox.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=listbox.yview)

            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            listbox_frame.listbox = listbox
            listbox_frame.scrollbar = scrollbar
            return listbox_frame

        # 使用圆角Canvas容器
        container = tk.Frame(parent, bg=parent.cget("bg"))

        canvas = tk.Canvas(
            container,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0
        )
        canvas.pack(fill="both", expand=True, padx=2, pady=2)

        # 内容框架
        content_frame = tk.Frame(canvas, bg=self.colors["bg_secondary"])

        # 从kwargs中移除可能冲突的参数
        listbox_kwargs = kwargs.copy()
        # 移除所有可能冲突的Listbox参数
        conflicting_params = ['bg', 'fg', 'selectbackground',
                              'selectforeground', 'relief', 'bd', 'height', 'font']
        for param in conflicting_params:
            listbox_kwargs.pop(param, None)

        listbox = tk.Listbox(
            content_frame,
            height=height,
            font=self.get_font(9),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_primary"],
            selectbackground=self.colors["neon_cyan"],
            selectforeground=self.colors["bg_primary"],
            relief="flat",
            bd=0,
            **listbox_kwargs
        )

        scrollbar = tk.Scrollbar(content_frame)
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)

        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 在Canvas中创建内容窗口
        content_window = canvas.create_window(
            8, 8, anchor="nw", window=content_frame)

        def render_listbox_bg():
            canvas_w = canvas.winfo_width()
            canvas_h = canvas.winfo_height()

            if canvas_w <= 1 or canvas_h <= 1:
                canvas.after(50, render_listbox_bg)
                return

            # 更新内容大小
            content_w = canvas_w - 16
            content_h = canvas_h - 16
            canvas.itemconfig(
                content_window, width=content_w, height=content_h)

            # 渲染圆角背景
            radius = 8
            border_width = 2

            img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 背景
            draw.rounded_rectangle(
                [0, 0, canvas_w-1, canvas_h-1],
                radius=radius,
                fill=self.colors["bg_secondary"]
            )

            # 边框
            draw.rounded_rectangle(
                [border_width//2, border_width//2, canvas_w-1 -
                    border_width//2, canvas_h-1-border_width//2],
                radius=radius,
                outline=self.colors["neon_cyan"],
                width=border_width
            )

            bg_img = ImageTk.PhotoImage(img)
            canvas.delete("listbox_bg")
            canvas.create_image(0, 0, anchor="nw",
                                image=bg_img, tags="listbox_bg")
            canvas.tag_lower("listbox_bg")
            canvas._listbox_bg = bg_img

        def on_listbox_configure(event):
            if hasattr(canvas, '_listbox_timer'):
                canvas.after_cancel(canvas._listbox_timer)
            canvas._listbox_timer = canvas.after(50, render_listbox_bg)

        canvas.bind("<Configure>", on_listbox_configure)
        canvas.after(100, render_listbox_bg)

        # 返回容器，但附带listbox和scrollbar属性
        container.listbox = listbox
        container.scrollbar = scrollbar
        container.canvas = canvas
        return container

    def create_rounded_scale(self, parent, from_=0, to=100, orient=tk.HORIZONTAL, variable=None, command=None, **kwargs):
        """创建圆角滑块"""
        if Image is None:
            # 回退到普通滑块
            scale = tk.Scale(
                parent,
                from_=from_,
                to=to,
                orient=orient,
                variable=variable,
                command=command,
                font=self.get_font(7),
                bg=self.colors["bg_primary"],
                fg=self.colors["neon_cyan"],
                activebackground=self.colors["neon_cyan"],
                highlightcolor=self.colors["neon_cyan"],
                troughcolor=self.colors["bg_secondary"],
                bd=0,
                relief="flat",
                **kwargs
            )
            return scale

        # 创建Canvas容器用于圆角背景
        canvas = tk.Canvas(
            parent,
            height=35,
            bg=parent.cget("bg"),
            highlightthickness=0,
            bd=0
        )

        # 创建滑块
        scale = tk.Scale(
            canvas,
            from_=from_,
            to=to,
            orient=orient,
            variable=variable,
            command=command,
            font=self.get_font(7),
            bg=self.colors["bg_primary"],
            fg=self.colors["neon_cyan"],
            activebackground=self.colors["neon_cyan"],
            highlightcolor=self.colors["neon_cyan"],
            troughcolor=self.colors["bg_secondary"],
            bd=0,
            relief="flat",
            **kwargs
        )

        # 在Canvas中放置滑块
        canvas.create_window(8, 17, window=scale)

        def render_scale_bg():
            canvas_w = canvas.winfo_width()
            if canvas_w <= 1:
                canvas.after(50, render_scale_bg)
                return

            radius = 8
            border_width = 1

            img = Image.new("RGBA", (canvas_w, 35), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 背景
            draw.rounded_rectangle(
                [0, 0, canvas_w-1, 34],
                radius=radius,
                fill=self.colors["bg_primary"]
            )

            # 边框
            draw.rounded_rectangle(
                [border_width//2, border_width//2, canvas_w -
                    1-border_width//2, 34-border_width//2],
                radius=radius,
                outline=self.colors["neon_cyan"],
                width=border_width
            )

            bg_img = ImageTk.PhotoImage(img)
            canvas.delete("scale_bg")
            canvas.create_image(0, 0, anchor="nw",
                                image=bg_img, tags="scale_bg")
            canvas.tag_lower("scale_bg")
            canvas._scale_bg = bg_img

        def on_scale_configure(event):
            all_items = canvas.find_all()
            if len(all_items) > 1:  # 确保有足够的子项
                canvas.itemconfig(all_items[1], width=event.width-16)
            if hasattr(canvas, '_scale_timer'):
                canvas.after_cancel(canvas._scale_timer)
            canvas._scale_timer = canvas.after(50, render_scale_bg)

        canvas.bind("<Configure>", on_scale_configure)
        canvas.after(100, render_scale_bg)

        # 返回Canvas，但附带scale属性
        canvas.scale = scale
        return canvas

    def start_rgb_animation(self):
        """启动RGB动画效果"""
        if not self.rgb_animation_running:
            self.rgb_animation_running = True
            self._animate_rgb()

    def _animate_rgb(self):
        """RGB动画循环 - 边框渐变效果（最大性能优化版）"""
        if not self.rgb_animation_running:
            return

        # 帧跳过机制：每3帧才渲染一次，大幅提升性能
        self._animation_frame_skip += 1
        if self._animation_frame_skip < 3:
            self.root.after(self.rgb_interval // 3, self._animate_rgb)
            return
        self._animation_frame_skip = 0

        # 更新渐变索引
        self.rgb_gradient_step = (self.rgb_gradient_step + 1) % len(
            self.border_colors)
        current_color = self.border_colors[self.rgb_gradient_step]

        # 性能优化：限制渲染频率，减少不必要的重绘
        if Image is not None and hasattr(self, "border_canvas") and self.border_canvas:
            # 只在颜色实际变化时才重新渲染
            if not hasattr(self, '_last_rgb_color') or self._last_rgb_color != current_color:
                self._render_border_image()
                self._last_rgb_color = current_color
        elif hasattr(self, "border_frame") and self.border_frame:
            self.border_frame.config(bg=current_color)

        # 继续动画（速度可调）
        self.root.after(self.rgb_interval, self._animate_rgb)

    def set_rgb_speed(self, speed_label):
        """设置RGB动画速度: Slow/Normal/Fast（最大化性能优化）"""
        mapping = {
            "Slow": 400,    # 更慢的速度，确保流畅性
            "Normal": 200,  # 默认值，专注性能
            "Fast": 150,    # 最快速度，仍然保证流畅
        }
        self.rgb_interval = mapping.get(speed_label, 200)

    def toggle_rgb_animation(self):
        """切换RGB边框动画开/关"""
        self.rgb_animation_running = not self.rgb_animation_running
        if self.rgb_animation_running:
            self._animate_rgb()

    def setup_ui(self):
        """设置UI界面 - Cyberpunk风格"""
        # 主容器使用新的内容容器
        main_container = tk.Frame(self.main_content_frame,
                                  bg=self.colors["bg_primary"])
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # 标题栏
        self.create_title_header(main_container)

        # 控制面板
        self.create_control_panel(main_container)

        # 数据显示面板
        self.create_data_panel(main_container)

        # 详细信息面板
        self.create_detail_panel(main_container)

        # 状态栏
        self.create_status_bar(main_container)

    def create_title_header(self, parent):
        """创建标题栏"""
        outer_frame, header_frame = self.create_rounded_frame(
            parent,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_cyan"],
            padding=3,
        )
        outer_frame.pack(fill="x", pady=(0, 10))

        # 主标题 - 使用阴影效果的Canvas
        self.title_canvas = self.create_shadow_text_canvas(
            header_frame,
            text="▓▓▓ STAR_RESONANCE_ACT_DAMAGE_CONSOLE ▓▓▓",
            font_tuple=self.get_font(14, "bold"),
            fg_color=self.colors["neon_cyan"],
            bg_color=self.colors["bg_secondary"],
            height=40
        )
        self.title_canvas.pack(pady=8, fill="x")

        # 为标题Canvas添加拖拽功能
        def title_start_drag(event):
            self.drag_data["x"] = event.x
            self.drag_data["y"] = event.y

        def title_drag_window(event):
            if self.drag_data["x"] != 0 or self.drag_data["y"] != 0:
                x = self.root.winfo_x() + (event.x - self.drag_data["x"])
                y = self.root.winfo_y() + (event.y - self.drag_data["y"])
                self.root.geometry(f"+{x}+{y}")

        def title_stop_drag(event):
            self.drag_data["x"] = 0
            self.drag_data["y"] = 0

        self.title_canvas.bind("<Button-1>", title_start_drag)
        self.title_canvas.bind("<B1-Motion>", title_drag_window)
        self.title_canvas.bind("<ButtonRelease-1>", title_stop_drag)

        # 副标题 - 使用阴影效果
        self.subtitle_canvas = self.create_shadow_text_canvas(
            header_frame,
            text="[REAL_TIME_DAMAGE_STATISTICS_MONITORING]",
            font_tuple=self.get_font(10),
            fg_color=self.colors["neon_green"],
            bg_color=self.colors["bg_secondary"],
            height=25
        )
        self.subtitle_canvas.pack(fill="x")

        # 为副标题也添加拖拽功能
        self.subtitle_canvas.bind("<Button-1>", title_start_drag)
        self.subtitle_canvas.bind("<B1-Motion>", title_drag_window)
        self.subtitle_canvas.bind("<ButtonRelease-1>", title_stop_drag)

        # 关闭按钮 - 圆角版本
        close_btn = self.create_enhanced_button(
            header_frame, "✕", self.on_closing, self.colors["neon_pink"], width=4, height=1
        )
        close_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

    def create_control_panel(self, parent):
        """创建控制面板"""
        outer_frame, control_frame = self.create_rounded_frame(
            parent,
            bg_color=self.colors["bg_accent"],
            border_color=self.colors["neon_orange"],
            padding=3,
        )
        # 设置控制面板的固定高度
        outer_frame.configure(height=160)  # 设置外框高度
        outer_frame.pack(fill="x", pady=(0, 10))
        outer_frame.pack_propagate(False)  # 防止子控件改变大小

        # 标题 - 使用阴影效果
        control_title_canvas = self.create_shadow_text_canvas(
            control_frame,
            text="[CONTROL_MATRIX]:",
            font_tuple=self.get_font(12, "bold"),
            fg_color=self.colors["neon_orange"],
            bg_color=self.colors["bg_accent"],
            height=30
        )
        control_title_canvas.pack(pady=5, fill="x")

        # 控制容器
        controls_container = tk.Frame(control_frame,
                                      bg=self.colors["bg_accent"],
                                      height=220)  # 调整为适应外框的高度
        controls_container.pack(pady=5, fill="x")
        controls_container.pack_propagate(False)  # 防止子控件影响容器大小

        # 左侧：状态和刷新设置（优化布局）
        left_frame = tk.Frame(controls_container, bg=self.colors["bg_accent"])
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # 连接状态（调整间距）
        status_frame = tk.Frame(left_frame, bg=self.colors["bg_accent"])
        status_frame.pack(anchor="w", pady=(2, 5))

        tk.Label(
            status_frame,
            text="STATUS:",
            font=self.get_font(9, "bold"),
            bg=self.colors["bg_accent"],
            fg=self.colors["text_primary"],
        ).pack(side="left")

        self.status_label = tk.Label(
            status_frame,
            text="● DISCONNECTED",
            font=self.get_font(9),
            bg=self.colors["bg_accent"],
            fg=self.colors["error_red"],
        )
        self.status_label.pack(side="left", padx=(8, 0))

        # 刷新间隔设置（调整间距）
        refresh_frame = tk.Frame(left_frame, bg=self.colors["bg_accent"])
        refresh_frame.pack(anchor="w", pady=(2, 5))

        tk.Label(
            refresh_frame,
            text="REFRESH:",
            font=self.get_font(9, "bold"),
            bg=self.colors["bg_accent"],
            fg=self.colors["text_primary"],
        ).pack(side="left")

        self.refresh_var = tk.StringVar(value="100")
        refresh_values = ["100", "200", "500", "1000"]
        self.refresh_combo = ttk.Combobox(
            refresh_frame,
            textvariable=self.refresh_var,
            values=refresh_values,
            width=6,
            state="readonly",
        )
        self.refresh_combo.pack(side="left", padx=(8, 0))
        self.refresh_combo.bind("<<ComboboxSelected>>",
                                self.on_refresh_changed)

        # 右侧：控制按钮区域
        right_container = tk.Frame(
            controls_container, bg=self.colors["bg_accent"])
        right_container.pack(side="right", padx=(10, 0))

        # 控制按钮框架
        button_frame = tk.Frame(right_container,
                                bg=self.colors["bg_accent"])
        button_frame.pack(side="left", padx=(0, 15))

        # 配置网格权重（调整按钮排列）
        for i in range(4):  # 4列
            button_frame.grid_columnconfigure(
                i, weight=1, minsize=90)  # 增大按钮宽度
        for i in range(2):  # 2行
            button_frame.grid_rowconfigure(i, weight=1, minsize=40)  # 增大按钮高度

        # 创建立体控制按钮（优化按钮文本和颜色）
        buttons = [
            ("◊ START", self.start_monitoring,
             self.colors["neon_green"], 0, 0),
            ("◊ DIRECT", self.start_direct_mode,
             self.colors["neon_orange"], 0, 1),
            ("■ STOP", self.stop_monitoring, self.colors["neon_pink"], 0, 2),
            ("▣ MINI", self.show_minimal_mode, self.colors["neon_cyan"], 0, 3),
            ("⟲ CLEAR", self.clear_data, self.colors["neon_yellow"], 1, 0),
            ("◆ TEST", self.start_test_mode, self.colors["neon_purple"], 1, 1),
            ("⚙ UID", self.show_uid_mapping_dialog,
             self.colors["warning_yellow"], 1, 2),
        ]

        for text, command, color, row, col in buttons:
            # 使用新的立体按钮（增大尺寸）
            btn_container = self.create_enhanced_button(
                button_frame, text, command, color, width=9, height=2  # 增大按钮尺寸
            )
            btn_container.grid(row=row, column=col,
                               padx=3, pady=4, sticky="ew")  # 增大间距

        # 添加背景透明度控制滑块（在按钮右侧）
        alpha_frame = tk.Frame(right_container, bg=self.colors["bg_accent"])
        alpha_frame.pack(side="right", padx=(20, 10))  # 增加左右边距，让它更靠右

        # 透明度标签
        tk.Label(
            alpha_frame,
            text="BG OPACITY:",
            font=self.get_font(9),
            bg=self.colors["bg_accent"],
            fg=self.colors["text_primary"],
        ).pack(anchor="w", pady=(0, 2))

        # 透明度按钮控制
        self.alpha_var = self.global_alpha_var  # 使用全局变量

        # 透明度按钮容器
        alpha_buttons_frame = tk.Frame(
            alpha_frame, bg=self.colors["bg_accent"])
        alpha_buttons_frame.pack(pady=(2, 3))  # 减少顶部边距，让按钮更靠上

        # 定义透明度设置函数
        def set_alpha_melon():
            """设置Melon透明度 80%"""
            self.alpha_var.set(80)
            self.on_alpha_changed(80)

        def set_alpha_full():
            """设置Full透明度 95%"""
            self.alpha_var.set(95)
            self.on_alpha_changed(95)

        # Melon按钮（80%）
        melon_btn = self.create_enhanced_button(
            alpha_buttons_frame, "Melon", set_alpha_melon,
            self.colors["neon_orange"], width=4, height=1, font_weight="normal"
        )
        melon_btn.pack(pady=(0, 1))  # 上边距0，下边距1

        # Full按钮（95%）
        full_btn = self.create_enhanced_button(
            alpha_buttons_frame, "Full", set_alpha_full,
            self.colors["neon_green"], width=4, height=1, font_weight="normal"
        )
        full_btn.pack(pady=(0, 1))  # 上边距0，下边距1

        # 透明度数值显示
        self.alpha_label = tk.Label(
            alpha_frame,
            text=f"{int(self.current_alpha * 100)}%",
            font=self.get_font(7),
            bg=self.colors["bg_accent"],
            fg=self.colors["neon_cyan"],
        )
        self.alpha_label.pack(pady=(0, 2))

        # RGB速度与开关控制
        rgb_ctrl = tk.Frame(alpha_frame, bg=self.colors["bg_accent"])
        rgb_ctrl.pack(pady=(8, 0))

        tk.Label(
            rgb_ctrl,
            text="RGB SPEED:",
            font=self.get_font(8),
            bg=self.colors["bg_accent"],
            fg=self.colors["text_primary"],
        ).grid(row=0, column=0, sticky="w", padx=(0, 4))

        self.rgb_speed_var = tk.StringVar(value="Normal")
        speed_combo = ttk.Combobox(
            rgb_ctrl,
            textvariable=self.rgb_speed_var,
            values=["Slow", "Normal", "Fast"],
            width=7,
            state="readonly",
        )
        speed_combo.grid(row=0, column=1, sticky="w")
        speed_combo.bind("<<ComboboxSelected>>",
                         lambda e: self.set_rgb_speed(self.rgb_speed_var.get()))

        # RGB开关按钮
        self.rgb_toggle_btn = self.create_enhanced_button(
            rgb_ctrl, "RGB ●", self.toggle_rgb_animation, self.colors["neon_cyan"], width=6, height=1
        )
        self.rgb_toggle_btn.grid(row=1, column=0, columnspan=2, pady=(4, 0))

    def calculate_foreground_alpha(self, background_alpha):
        """计算前景元素的有效透明度，确保字体和按钮至少70%可见"""
        # 前景元素始终保持完全不透明，通过颜色增强来确保可见性
        return 1.0

    def calculate_effective_visibility(self, background_alpha):
        """计算有效可见性 - 当背景透明度低时需要颜色增强"""
        min_visibility = 0.7
        if background_alpha < min_visibility:
            # 需要颜色增强来补偿背景透明度的不足
            enhancement_needed = min_visibility / background_alpha
            return min(2.0, enhancement_needed)  # 最大2倍增强
        else:
            return 1.0  # 不需要增强

    def enhance_color_for_low_alpha(self, color, background_alpha):
        """在低背景透明度时增强颜色亮度，确保可见性"""
        enhancement_factor = self.calculate_effective_visibility(
            background_alpha)

        if enhancement_factor <= 1.0:
            return color  # 不需要增强

        # 解析十六进制颜色
        if color.startswith('#'):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)

            # 增强亮度，但保持色调
            r = min(255, int(r * enhancement_factor))
            g = min(255, int(g * enhancement_factor))
            b = min(255, int(b * enhancement_factor))

            return f"#{r:02x}{g:02x}{b:02x}"

        return color

    def update_foreground_visibility(self, background_alpha):
        """更新前景元素的可见性，在低背景透明度时增强颜色"""
        # 这个方法可以在将来扩展，用于动态更新所有文本和按钮的颜色
        # 目前主要是为了保持接口的完整性
        pass

    def update_global_alpha(self, value, source="main"):
        """全局透明度更新 - 同步主界面和所有MINI窗口，字体和按钮保持最低70%透明度"""
        try:
            background_alpha = float(value) / 100.0
            background_alpha = max(
                0.8, min(1.0, background_alpha))  # 背景可以80%-100%
            self.current_alpha = background_alpha

            # 计算有效可见性增强因子
            visibility_enhancement = self.calculate_effective_visibility(
                background_alpha)

            # 更新前景元素的可见性
            self.update_foreground_visibility(background_alpha)

            # 更新主窗口背景透明度
            self.root.wm_attributes("-alpha", background_alpha)

            # 更新所有MINI窗口背景透明度
            for mini_info in self.mini_windows:
                if mini_info and mini_info.get("window") and mini_info["window"].winfo_exists():
                    mini_info["window"].wm_attributes(
                        "-alpha", background_alpha)
                    mini_info["window"].current_alpha = background_alpha

                    # 更新MINI窗口的透明度标签
                    if mini_info.get("alpha_label"):
                        mini_info["alpha_label"].config(
                            text=f"{int(background_alpha * 100)}%")

                    # 更新MINI窗口的滑块（如果不是从MINI窗口触发的）
                    if source != "mini" and mini_info.get("alpha_var"):
                        mini_info["alpha_var"].set(background_alpha * 100)

            # 更新所有ACT timer窗口背景透明度
            for timer_window in self.timer_windows:
                if timer_window and timer_window.winfo_exists():
                    timer_window.wm_attributes("-alpha", background_alpha)

            # 更新主窗口的透明度标签
            if hasattr(self, 'alpha_label'):
                self.alpha_label.config(text=f"{int(background_alpha * 100)}%")

            # 更新主窗口滑块（如果不是从主窗口触发的）
            if source != "main" and hasattr(self, 'alpha_var'):
                self.alpha_var.set(background_alpha * 100)

            # 更新全局变量
            self.global_alpha_var.set(background_alpha * 100)

            # 更新状态信息，说明字体和按钮的可见性保护
            if background_alpha < 0.7:
                enhancement = self.calculate_effective_visibility(
                    background_alpha)
                self.update_status(
                    f"[CONFIG] 背景透明度: {int(background_alpha * 100)}% (前景增强: {enhancement:.1f}x)")
            else:
                self.update_status(
                    f"[CONFIG] 背景透明度: {int(background_alpha * 100)}%")
        except Exception as e:
            self.update_status(f"[ERROR] 透明度设置错误: {e}")

    def on_alpha_changed(self, value):
        """主界面透明度滑块变化回调"""
        self.update_global_alpha(value, source="main")

    def on_mini_alpha_changed(self, value, mini_info):
        """MINI界面透明度滑块变化回调"""
        self.update_global_alpha(value, source="mini")

    def show_minimal_mode(self):
        """显示所有玩家总伤害横向条形图，按总伤害排名，使用主UI的Cyberpunk风格"""
        # 检查是否已设置个人UID，如果没有则先要求输入
        if not self.personal_uid:
            self.show_personal_uid_dialog(callback=self._create_minimal_mode)
            return
        else:
            self._create_minimal_mode()

    def _create_minimal_mode(self):
        """创建MINI模式窗口的实际实现"""
        self.root.withdraw()
        mini = tk.Toplevel()
        mini.title("◊ STAR_RESONANCE_MINI_CONSOLE ◊")
        mini.geometry("440x700")  # 缩减高度
        mini.resizable(False, False)
        mini.wm_attributes("-topmost", True)
        mini.overrideredirect(True)
        # 为MINI窗口设置与主界面相同的透明度
        mini.current_alpha = self.current_alpha
        mini.wm_attributes("-alpha", 0.0)  # 初始透明度为0，准备淡入
        # 去除黑边，使用主背景色
        mini.configure(bg=self.colors["bg_primary"])
        drag_data = {"x": 0, "y": 0, "dragging": False}

        # 创建MINI窗口信息字典
        mini_info = {
            "window": mini,
            "alpha_var": None,
            "alpha_label": None
        }

        # 创建RGB边框容器（与主UI完全一致的圆角背景）
        if Image is not None:
            # 尝试为MINI窗口设置圆角区域
            try:
                import ctypes
                mini.update()
                hwnd = ctypes.windll.user32.GetParent(mini.winfo_id())
                if hwnd == 0:
                    hwnd = mini.winfo_id()

                width = 440
                height = 700  # 更新圆角区域高度
                corner_radius = 12

                hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                    0, 0, width, height, corner_radius * 2, corner_radius * 2
                )

                if hrgn:
                    ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
            except Exception:
                pass

            # 使用与主UI相同的Canvas背景方案
            border_canvas = tk.Canvas(
                mini, bg=self.colors["bg_primary"], highlightthickness=0, bd=0)
            border_canvas.pack(fill="both", expand=True, padx=0, pady=0)

            # 主内容容器，使用与主UI相同的方式
            main_content_frame = tk.Frame(
                border_canvas, bg=self.colors["bg_primary"], bd=0, relief="flat")

            # 在Canvas中创建窗口
            border_space = 6  # 边框空间
            content_window = border_canvas.create_window(
                border_space, border_space,
                anchor="nw",
                window=main_content_frame
            )

            mini._border_imgtk = None
            mini._border_cache_key = None
            mini.rgb_index = 0

            def render_mini_border():
                """渲染MINI窗口的完整圆角背景（与主UI一致），优化缓存减少闪烁"""
                canvas_w = border_canvas.winfo_width()
                canvas_h = border_canvas.winfo_height()
                if canvas_w <= 0 or canvas_h <= 0:
                    return

                # 更新内容区域大小
                content_width = canvas_w - (border_space * 2)
                content_height = canvas_h - (border_space * 2)
                border_canvas.itemconfig(
                    content_window,
                    width=content_width,
                    height=content_height
                )

                current_color = self.border_colors[mini.rgb_index % len(
                    self.border_colors)]
                key = (canvas_w, canvas_h, current_color)

                # 更严格的缓存检查，减少不必要的重绘
                if (getattr(mini, "_border_cache_key", None) == key and
                    mini._border_imgtk is not None and
                    hasattr(border_canvas, 'find_withtag') and
                        border_canvas.find_withtag("bg_image")):
                    return

                # 创建完整的圆角背景（与主UI一致）
                scale = 1.5
                W, H = int(canvas_w * scale), int(canvas_h * scale)
                r = max(0, int(12 * scale))  # 与主UI相同的圆角
                bw = max(1, int(3 * scale))  # 与主UI相同的边框宽度

                # 安全检查，确保边框不会导致无效的坐标
                if W <= bw * 2 or H <= bw * 2:
                    return  # 尺寸太小，跳过渲染

                img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)

                # 绘制完整的圆角背景
                bg_color = self.colors["bg_primary"]
                draw.rounded_rectangle(
                    [0, 0, W-1, H-1], radius=r, fill=bg_color)

                # 添加RGB边框发光效果
                try:
                    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    gdraw = ImageDraw.Draw(glow)
                    gdraw.rounded_rectangle([bw//2, bw//2, W-1-bw//2, H-1-bw//2],
                                            radius=r, outline=current_color, width=bw)
                    glow = glow.filter(
                        ImageFilter.GaussianBlur(1.5 * scale / 10))
                    img = Image.alpha_composite(img, glow)
                except Exception:
                    pass

                # 绘制清晰的RGB边框
                draw.rounded_rectangle([bw//2, bw//2, W-1-bw//2, H-1-bw//2],
                                       radius=r, outline=current_color, width=bw)

                img = img.resize((canvas_w, canvas_h), resample=Image.LANCZOS)
                imgtk = ImageTk.PhotoImage(img)
                border_canvas.delete("bg_image")
                border_canvas.create_image(
                    0, 0, anchor="nw", image=imgtk, tags="bg_image")
                mini._border_imgtk = imgtk
                mini._border_cache_key = key

            def mini_rgb_animate():
                """MINI窗口RGB动画（与主UI同步），优化减少闪烁"""
                if not mini.winfo_exists():
                    return

                # 检查是否真的需要更新
                old_index = getattr(mini, 'rgb_index', 0)
                mini.rgb_index = (mini.rgb_index + 1) % len(self.border_colors)

                # 只有当颜色真的改变时才重新渲染
                if mini.rgb_index != old_index:
                    # 使用更温和的渲染方式，避免闪烁
                    if hasattr(mini, '_mini_rgb_timer'):
                        mini.after_cancel(mini._mini_rgb_timer)
                    mini._mini_rgb_timer = mini.after(10, render_mini_border)

                mini.after(self.rgb_interval, mini_rgb_animate)

            def on_mini_resize(event):
                """MINI窗口大小变化处理，减少闪烁"""
                if hasattr(mini, '_mini_resize_timer'):
                    mini.after_cancel(mini._mini_resize_timer)
                # 增加延迟，减少频繁重绘
                mini._mini_resize_timer = mini.after(100, render_mini_border)

            # 绑定事件
            border_canvas.bind("<Configure>", on_mini_resize)

            # 初始渲染与动画
            mini.after(100, render_mini_border)
            mini.after(self.rgb_interval, mini_rgb_animate)
        else:
            # 回退为矩形边框，去除黑边
            shadow_frame = tk.Frame(
                mini, bg=self.colors["bg_primary"], bd=0, relief="flat")
            shadow_frame.pack(fill="both", expand=True, padx=0, pady=0)
            border_frame = tk.Frame(
                shadow_frame, bg="#ff0000", bd=0, relief="flat")
            border_frame.pack(fill="both", expand=True, padx=3, pady=3)
            gradient_frame = tk.Frame(
                border_frame, bg=self.colors["bg_primary"], bd=0, relief="flat")
            gradient_frame.pack(fill="both", expand=True, padx=2, pady=2)
            main_content_frame = tk.Frame(
                gradient_frame, bg=self.colors["bg_primary"], bd=0, relief="flat")
            main_content_frame.pack(fill="both", expand=True, padx=6, pady=6)

            def mini_rgb_animate():
                if not mini.winfo_exists():
                    return
                color_index = getattr(mini, "rgb_index", 0)
                current_color = self.border_colors[color_index % len(
                    self.border_colors)]
                border_frame.config(bg=current_color)
                mini.rgb_index = (color_index + 1) % len(self.border_colors)
                mini.after(self.rgb_interval, mini_rgb_animate)

        # 创建标题栏（使用主UI风格）
        header_outer, header_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_cyan"],
            padding=2,  # 减小内边距
        )
        header_outer.configure(height=65)  # 设置外框固定高度为原来的一半
        header_outer.pack(fill="x", pady=(6, 4))  # 减小外边距
        header_outer.pack_propagate(False)  # 防止子控件改变外框大小

        # 标题内容容器
        title_container = tk.Frame(
            header_frame, bg=self.colors["bg_secondary"])
        title_container.pack(fill="x", pady=int(3 * 1.1))  # 扩大1.1倍

        # 主标题 - 缩小字体并添加阴影效果的Canvas
        title_canvas = tk.Canvas(
            title_container,
            height=int(25 * 1.1),  # 缩减为原来的一半
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        title_canvas.pack(fill="x", pady=int(2 * 1.1))

        def draw_title_with_shadow():
            title_canvas.delete("all")
            title_text = "▓▓▓ MINI_CONSOLE ▓▓▓"
            font_tuple = self.get_font(int(12 * 1.1), "normal")

            # 获取画布中心位置
            canvas_width = title_canvas.winfo_width()
            if canvas_width > 1:
                center_x = canvas_width // 2
                center_y = int(12 * 1.1)

                # 绘制多层阴影（渐变效果）
                shadow_layers = [
                    (3, 3, "#000000"),
                    (2, 2, "#111111"),
                    (1, 1, "#222222")
                ]

                for dx, dy, shadow_color in shadow_layers:
                    title_canvas.create_text(
                        center_x + dx,
                        center_y + dy,
                        text=title_text,
                        font=font_tuple,
                        fill=shadow_color,
                        anchor="center"
                    )

                # 绘制边框效果（使用深灰色）
                border_color = "#333333"
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    title_canvas.create_text(
                        center_x + dx,
                        center_y + dy,
                        text=title_text,
                        font=font_tuple,
                        fill=border_color,
                        anchor="center"
                    )

                # 绘制主文字
                title_canvas.create_text(
                    center_x,
                    center_y,
                    text=title_text,
                    font=font_tuple,
                    fill=self.colors["neon_cyan"],
                    anchor="center"
                )

        # 绑定配置事件以重绘标题
        title_canvas.bind("<Configure>", lambda e: draw_title_with_shadow())
        title_canvas.after(10, draw_title_with_shadow)

        # 副标题 - 使用Canvas添加阴影
        subtitle_canvas = tk.Canvas(
            title_container,
            height=int(16 * 1.1),  # 缩减为原来的一半
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        subtitle_canvas.pack(fill="x")

        def draw_subtitle_with_shadow():
            # 检查canvas是否仍然存在
            try:
                if not subtitle_canvas.winfo_exists():
                    return
            except:
                return

            subtitle_canvas.delete("all")
            subtitle_text = "[REAL_TIME_RANKING]"
            font_tuple = self.get_font(int(8 * 1.1), "normal")

            # 获取画布中心位置
            try:
                canvas_width = subtitle_canvas.winfo_width()
                if canvas_width > 1:
                    center_x = canvas_width // 2
                    center_y = int(8 * 1.1)

                    # 绘制多层阴影
                    shadow_layers = [
                        (2, 2, "#000000"),
                        (1, 1, "#111111")
                    ]

                    for dx, dy, shadow_color in shadow_layers:
                        subtitle_canvas.create_text(
                            center_x + dx,
                            center_y + dy,
                            text=subtitle_text,
                            font=font_tuple,
                            fill=shadow_color,
                            anchor="center"
                        )

                    # 绘制边框效果
                    border_color = "#333333"
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        subtitle_canvas.create_text(
                            center_x + dx,
                            center_y + dy,
                            text=subtitle_text,
                            font=font_tuple,
                            fill=border_color,
                            anchor="center"
                        )

                    # 绘制主文字
                    subtitle_canvas.create_text(
                        center_x,
                        center_y,
                        text=subtitle_text,
                        font=font_tuple,
                        fill=self.colors["neon_green"],
                        anchor="center"
                    )
            except:
                # 如果canvas已被销毁，静默忽略错误
                pass

        # 保存after任务ID到mini窗口，以便后续取消
        if not hasattr(mini, '_after_tasks'):
            mini._after_tasks = []

        def safe_bind_configure():
            try:
                subtitle_canvas.bind(
                    "<Configure>", lambda e: draw_subtitle_with_shadow())
            except:
                pass

        def safe_after_draw():
            try:
                task_id = subtitle_canvas.after(10, draw_subtitle_with_shadow)
                mini._after_tasks.append(task_id)
            except:
                pass

        safe_bind_configure()
        safe_after_draw()

        # 关闭按钮 - 圆角版本（缩小尺寸）
        close_btn = self.create_enhanced_button(
            title_container, "✕", lambda: self._close_minimal_mode(mini),
            self.colors["neon_pink"], width=2, height=1  # 缩小宽度从3到2
        )
        close_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-3, y=2)  # 调整位置

        # 创建本人DPS显示区域
        self_dps_outer, self_dps_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_yellow"],
            padding=int(2 * 1.1),
        )
        self_dps_outer.configure(height=75)  # 设置外框固定高度为原来的一半
        self_dps_outer.pack(fill="x", pady=(0, int(2 * 1.1)))
        self_dps_outer.pack_propagate(False)  # 防止子控件改变外框大小

        # 本人DPS标题
        self_dps_title_canvas = tk.Canvas(
            self_dps_frame,
            height=int(0),
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        self_dps_title_canvas.pack(fill="x", pady=int(2 * 1.1))

        def draw_self_dps_title():
            self_dps_title_canvas.delete("all")
            title_text = "[MY_PERFORMANCE]:"
            font_tuple = self.get_font(int(8 * 1.1), "normal")

            canvas_width = self_dps_title_canvas.winfo_width()
            if canvas_width > 1:
                center_x = canvas_width // 2
                center_y = int(8 * 1.1)

                # 绘制阴影
                for dx, dy in [(1, 1), (2, 2)]:
                    self_dps_title_canvas.create_text(
                        center_x + dx, center_y + dy,
                        text=title_text, font=font_tuple,
                        fill="#000000", anchor="center"
                    )

                # 绘制主文字
                self_dps_title_canvas.create_text(
                    center_x, center_y,
                    text=title_text, font=font_tuple,
                    fill=self.colors["neon_yellow"], anchor="center"
                )

        self_dps_title_canvas.bind(
            "<Configure>", lambda e: draw_self_dps_title())
        self_dps_title_canvas.after(10, draw_self_dps_title)

        # 本人DPS条容器
        self_dps_container = tk.Frame(
            self_dps_frame, bg=self.colors["bg_secondary"])
        self_dps_container.pack(fill="x", padx=int(6 * 1.1), pady=int(2 * 1.1))

        # 存储本人DPS显示组件的引用
        mini._self_dps_container = self_dps_container

        # 创建数据显示面板（使用主UI风格）
        data_outer, data_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_accent"],
            border_color=self.colors["neon_green"],
            padding=int(2 * 1.1),  # 扩大1.1倍内边距
        )
        data_outer.pack(fill="both", expand=True,
                        pady=(0, int(4 * 1.1)))  # 扩大1.1倍外边距

        # 数据面板标题 - 使用Canvas添加阴影
        data_title_canvas = tk.Canvas(
            data_frame,
            height=int(18 * 1.1),  # 扩大1.1倍高度
            bg=self.colors["bg_accent"],
            highlightthickness=0,
            bd=0
        )
        data_title_canvas.pack(fill="x", pady=int(3 * 1.1))

        def draw_data_title_with_shadow():
            data_title_canvas.delete("all")
            title_text = "[DAMAGE_RANKING]:"
            font_tuple = self.get_font(int(9 * 1.1), "normal")

            canvas_width = data_title_canvas.winfo_width()
            if canvas_width > 1:
                center_x = canvas_width // 2
                center_y = int(9 * 1.1)

                # 绘制多层阴影
                shadow_layers = [
                    (2, 2, "#000000"),
                    (1, 1, "#111111")
                ]

                for dx, dy, shadow_color in shadow_layers:
                    data_title_canvas.create_text(
                        center_x + dx,
                        center_y + dy,
                        text=title_text,
                        font=font_tuple,
                        fill=shadow_color,
                        anchor="center"
                    )

                # 绘制边框效果
                border_color = "#333333"
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    data_title_canvas.create_text(
                        center_x + dx,
                        center_y + dy,
                        text=title_text,
                        font=font_tuple,
                        fill=border_color,
                        anchor="center"
                    )

                # 绘制主文字
                data_title_canvas.create_text(
                    center_x,
                    center_y,
                    text=title_text,
                    font=font_tuple,
                    fill=self.colors["neon_green"],
                    anchor="center"
                )

        data_title_canvas.bind(
            "<Configure>", lambda e: draw_data_title_with_shadow())
        data_title_canvas.after(10, draw_data_title_with_shadow)

        # 内容容器
        content_container = tk.Frame(data_frame, bg=self.colors["bg_accent"])
        content_container.pack(fill="both", expand=True,
                               padx=int(6 * 1.1), pady=int(3 * 1.1))  # 扩大1.1倍边距

        def start_drag(event):
            # 检查事件来源，避免在滑块、按钮等控件上触发拖拽
            widget_class = event.widget.__class__.__name__
            if widget_class in ['Scale', 'Button', 'Entry', 'Text', 'Listbox', 'Scrollbar']:
                return

            # 检查是否点击在滑块容器内
            if hasattr(event, 'stopPropagation'):
                return

            drag_data["x"] = event.x_root - mini.winfo_x()
            drag_data["y"] = event.y_root - mini.winfo_y()
            drag_data["dragging"] = True

        def drag_window(event):
            # 同样检查事件来源
            widget_class = event.widget.__class__.__name__
            if widget_class in ['Scale', 'Button', 'Entry', 'Text', 'Listbox', 'Scrollbar']:
                return

            # 检查是否在滑块容器内
            if hasattr(event, 'stopPropagation'):
                return

            if drag_data["dragging"]:
                x = event.x_root - drag_data["x"]
                y = event.y_root - drag_data["y"]
                mini.geometry(f"+{x}+{y}")

                # 同时更新所有关联的timer窗口位置
                # 方法1：检查mini对象的关联timer
                if hasattr(mini, 'associated_timers'):
                    for timer_window in mini.associated_timers:
                        if timer_window.winfo_exists():
                            # 使用固定的MINI窗口宽度（440px）+ 10像素间距
                            timer_x = x + 440 + 10
                            timer_y = y
                            timer_window.geometry(f"+{timer_x}+{timer_y}")

                else:

                    # 方法2：通过全局timer列表搜索引用此mini窗口的timer
                    for i, timer_window in enumerate(self.timer_windows):
                        print(
                            f"检查timer窗口 {i}: 存在={timer_window.winfo_exists()}, 有reference_window={hasattr(timer_window, 'reference_window')}")
                        if hasattr(timer_window, 'reference_window'):
                            print(
                                f"Timer窗口 {i} 的reference_window: {timer_window.reference_window}, mini: {mini}")
                        if (timer_window.winfo_exists() and
                            hasattr(timer_window, 'reference_window') and
                                timer_window.reference_window == mini):
                            timer_x = x + 440 + 10
                            timer_y = y
                            timer_window.geometry(f"+{timer_x}+{timer_y}")

                            print(f"通过全局搜索更新timer窗口位置: {timer_x}, {timer_y}")

        def stop_drag(event):
            drag_data["dragging"] = False

        # 只为特定容器绑定拖拽事件，避免与控件冲突
        drag_widgets = [main_content_frame, header_frame]
        for widget in drag_widgets:
            widget.bind("<Button-1>", start_drag)
            widget.bind("<B1-Motion>", drag_window)
            widget.bind("<ButtonRelease-1>", stop_drag)

        def render_content():
            # 优先从API获取数据，如果失败则使用current_data
            data = None
            if not self.direct_mode:
                try:
                    import requests
                    response = requests.get(self.api_url, timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                except:
                    pass

            # 如果API获取失败，使用其他数据源
            if not data:
                data = (self.current_data
                        if self.current_data else self.get_direct_data() or {
                            "user": {}
                        })

            user_data = data.get("user", {})
            sorted_users = sorted(
                user_data.items(),
                key=lambda x: x[1].get("total_damage", {}).get(
                    "total", 0) if x[1] else 0,
                reverse=True,
            )

            # 更新本人DPS条
            self.update_self_dps_bar(mini, user_data, sorted_users)

            # 检查是否需要重新创建UI（数据变化才重创建，减少闪烁）
            current_user_count = len(sorted_users)
            last_user_count = getattr(
                content_container, '_last_user_count', -1)
            need_recreate = (last_user_count != current_user_count or
                             not hasattr(content_container, '_main_canvas'))

            if need_recreate:
                # 只在必要时清除现有内容
                for widget in content_container.winfo_children():
                    widget.destroy()
                content_container._last_user_count = current_user_count

            # 如果没有数据，显示等待信息
            if not sorted_users:
                no_data_canvas = tk.Canvas(
                    content_container,
                    height=int(60 * 1.1),  # 扩大1.1倍高度
                    bg=self.colors["bg_accent"],
                    highlightthickness=0,
                    bd=0
                )
                no_data_canvas.pack(fill="x", pady=int(10 * 1.1))

                def draw_no_data_with_shadow():
                    no_data_canvas.delete("all")
                    text_lines = [
                        "▓▓▓ WAITING_FOR_DATA ▓▓▓",
                        "[SYSTEM]: 未检测到战斗数据",
                        "[STATUS]: 等待玩家开始战斗..."
                    ]

                    canvas_width = no_data_canvas.winfo_width()
                    if canvas_width > 1:
                        center_x = canvas_width // 2
                        font_tuple = self.get_font(int(8 * 1.1), "normal")

                        for i, line in enumerate(text_lines):
                            y_pos = int(10 * 1.1) + i * int(16 * 1.1)

                            # 绘制多层阴影
                            shadow_layers = [
                                (2, 2, "#000000"),
                                (1, 1, "#111111")
                            ]

                            for dx, dy, shadow_color in shadow_layers:
                                no_data_canvas.create_text(
                                    center_x + dx,
                                    y_pos + dy,
                                    text=line,
                                    font=font_tuple,
                                    fill=shadow_color,
                                    anchor="center"
                                )

                            # 绘制边框效果
                            border_color = "#333333"
                            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                no_data_canvas.create_text(
                                    center_x + dx,
                                    y_pos + dy,
                                    text=line,
                                    font=font_tuple,
                                    fill=border_color,
                                    anchor="center"
                                )

                            # 绘制主文字
                            color = self.colors["neon_cyan"] if i == 0 else self.colors["text_accent"]
                            no_data_canvas.create_text(
                                center_x,
                                y_pos,
                                text=line,
                                font=font_tuple,
                                fill=color,
                                anchor="center"
                            )

                no_data_canvas.bind(
                    "<Configure>", lambda e: draw_no_data_with_shadow())
                no_data_canvas.after(10, draw_no_data_with_shadow)
                return

            # 计算显示参数 - 扩大1.1倍尺寸
            bar_area_w = int(320 * 1.1)  # 扩大1.1倍宽度
            bar_h = int(24 * 1.1)  # 扩大1.1倍高度
            gap = int(6 * 1.1)  # 扩大1.1倍间距
            max_bars = 10  # 增加到最多显示10个人
            show_users = sorted_users[:max_bars]
            max_val = max([u[1].get("total_damage", {}).get("total", 0)
                           for u in show_users] + [1])
            canvas_h = bar_h * len(show_users) + gap * \
                (len(show_users) - 1) + int(30 * 1.1)

            # 创建或重用滚动区域
            if need_recreate or not hasattr(content_container, '_canvas_container'):
                canvas_container = tk.Frame(
                    content_container, bg=self.colors["bg_accent"])
                canvas_container.pack(
                    fill="both", expand=True, pady=int(3 * 1.1))
                content_container._canvas_container = canvas_container

                canvas = tk.Canvas(
                    canvas_container,
                    width=int((bar_area_w + 40) * 1.1),  # 扩大1.1倍宽度
                    height=min(canvas_h, int(480 * 1.1)),  # 扩大1.1倍最大高度
                    bg=self.colors["bg_primary"],
                    highlightthickness=1,
                    highlightcolor=self.colors["border_light"],
                    relief="solid",
                    bd=0,
                )
                canvas.pack(pady=int(3 * 1.1))
                content_container._main_canvas = canvas
            else:
                # 重用现有Canvas，只清除内容不重新创建
                canvas = content_container._main_canvas
                canvas.delete("all")  # 只删除Canvas内容，不重创建Widget

            # 绘制数据条（使用现有Canvas，减少闪烁）
            for idx, (uid, info) in enumerate(show_users):
                total = info.get("total_damage", {}).get(
                    "total", 0) if info else 0
                dps = info.get("total_dps", 0) if info else 0
                profession = info.get("profession", "未知")

                # 排名颜色
                if idx == 0:
                    bar_color = self.colors["neon_green"]
                    text_color = self.colors["neon_green"]
                elif idx == 1:
                    bar_color = self.colors["neon_cyan"]
                    text_color = self.colors["neon_cyan"]
                elif idx == 2:
                    bar_color = self.colors["neon_yellow"]
                    text_color = self.colors["neon_yellow"]
                else:
                    bar_color = self.colors["neon_purple"]
                    text_color = self.colors["text_primary"]

                y0 = int(15 * 1.1) + idx * (bar_h + gap)  # 扩大1.1倍起始位置
                bar_len = int((total / max_val) *
                              (bar_area_w - int(115 * 1.1)))  # 扩大1.1倍计算，调整进度条宽度

                # 排名标识 - 带阴影
                rank_text = f"#{idx + 1}"
                rank_font = self.get_font(
                    int(10 * 1.1), "normal")  # 扩大1.1倍字体，改为细体
                # 阴影
                canvas.create_text(
                    int(8 * 1.1) + 1, y0 + bar_h // 2 + 1,
                    text=rank_text, font=rank_font, fill="#000000", anchor="w"
                )
                # 主文字
                canvas.create_text(
                    int(8 * 1.1), y0 + bar_h // 2,
                    text=rank_text, font=rank_font, fill=text_color, anchor="w"
                )

                # 玩家信息 - 带阴影，向右移动
                display_name = self.get_display_name(uid)  # 使用映射的用户名
                player_info = f"{display_name}"
                if len(player_info) > 8:  # 截断过长的用户名
                    player_info = player_info[:8] + "..."
                player_font = self.get_font(
                    int(8 * 1.1), "normal")  # 扩大1.1倍字体，改为细体
                # 阴影
                canvas.create_text(
                    int(42 * 1.1) + 1, y0 + bar_h // 2 -
                    int(4 * 1.1) + 1,  # 从35移动到42
                    text=player_info, font=player_font, fill="#000000", anchor="w"
                )
                # 主文字
                canvas.create_text(
                    int(42 * 1.1), y0 + bar_h // 2 - int(4 * 1.1),  # 从35移动到42
                    text=player_info, font=player_font, fill=self.colors["text_primary"], anchor="w"
                )

                # 职业信息 - 带阴影，向右移动
                prof_info = f"[{profession}]"
                prof_font = self.get_font(int(7 * 1.1), "normal")  # 扩大1.1倍字体
                # 阴影
                canvas.create_text(
                    int(42 * 1.1) + 1, y0 + bar_h // 2 +
                    int(4 * 1.1) + 1,  # 从35移动到42
                    text=prof_info, font=prof_font, fill="#000000", anchor="w"
                )
                # 主文字
                canvas.create_text(
                    int(42 * 1.1), y0 + bar_h // 2 + int(4 * 1.1),  # 从35移动到42
                    text=prof_info, font=prof_font, fill=self.colors["neon_orange"], anchor="w"
                )

                # 进度条背景（深色）- 左移5像素
                canvas.create_rectangle(
                    int(105 * 1.1), y0 + int(4 * 1.1),
                    int(105 * 1.1) + (bar_area_w - int(115 * 1.1)), y0 +
                    bar_h - int(4 * 1.1),
                    fill=self.colors["bg_secondary"],
                    outline=self.colors["border_dark"],
                    width=1,
                )

                # 进度条（带阴影效果）
                if bar_len > 0:
                    # 阴影
                    canvas.create_rectangle(
                        int(107 * 1.1), y0 + int(6 * 1.1),
                        int(105 * 1.1) + bar_len +
                        2, y0 + bar_h - int(2 * 1.1),
                        fill="#000000", outline="", width=0,
                    )
                    # 主条
                    canvas.create_rectangle(
                        int(105 * 1.1), y0 + int(4 * 1.1),
                        int(105 * 1.1) + bar_len, y0 + bar_h - int(4 * 1.1),
                        fill=bar_color,
                        outline=self.colors["bg_primary"],
                        width=1,  # 保持边框大小
                    )

                # 在进度条上显示DPS - 带边框和阴影
                avg_dps_text = f"DPS:{dps:,.0f}"
                if dps >= 1000000:
                    avg_dps_text = f"DPS:{dps/1000000:.1f}M"
                elif dps >= 1000:
                    avg_dps_text = f"DPS:{dps/1000:.1f}K"

                dps_font = self.get_font(
                    int(6 * 1.1 * 1.2), "normal")  # 放大1.2倍

                # 计算DPS文字位置（在进度条中间偏左）
                dps_x = int(105 * 1.1) + max(int(40 * 1.1), bar_len // 3)
                dps_y = y0 + bar_h // 2

                # DPS数字边框效果
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                    canvas.create_text(
                        dps_x + dx, dps_y + dy,
                        text=avg_dps_text, font=dps_font, fill="#000000", anchor="w"
                    )

                # DPS阴影
                canvas.create_text(
                    dps_x + 1, dps_y + 1,
                    text=avg_dps_text, font=dps_font, fill="#111111", anchor="w"
                )

                # DPS主文字（使用黄色高亮）
                canvas.create_text(
                    dps_x, dps_y,
                    text=avg_dps_text, font=dps_font, fill=self.colors["neon_yellow"], anchor="w"
                )

                # 伤害数值 - 带边框和阴影（移动到右上角）
                damage_text = self.format_damage_number(total)

                damage_font = self.get_font(
                    int(9 * 1.1), "normal")  # 扩大1.1倍字体，改为细体

                # 伤害数字边框效果（四方向）
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                    canvas.create_text(
                        bar_area_w + int(30 * 1.1) + dx, y0 + bar_h // 2 + dy,
                        text=damage_text, font=damage_font, fill="#000000", anchor="e"
                    )

                # 阴影
                canvas.create_text(
                    bar_area_w + int(30 * 1.1) + 2, y0 + bar_h // 2 + 2,
                    text=damage_text, font=damage_font, fill="#111111", anchor="e"
                )

                # 主文字
                canvas.create_text(
                    bar_area_w + int(30 * 1.1), y0 + bar_h // 2,
                    text=damage_text, font=damage_font, fill=text_color, anchor="e"
                )

        # 创建状态栏和控制栏（使用主UI风格）- 高度匹配文本
        status_outer, status_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["border_light"],
            padding=int(1 * 1.1),  # 扩大1.1倍内边距
        )
        # 设置固定高度，只够容纳文本
        status_outer.configure(height=int(35 * 1.1))  # 设置为文本高度的合适尺寸
        status_outer.pack(fill="x", pady=(0, int(4 * 1.1)))  # 扩大1.1倍外边距
        status_outer.pack_propagate(False)  # 防止子控件改变外框大小

        # 状态栏和控制栏容器
        status_control_container = tk.Frame(
            status_frame, bg=self.colors["bg_secondary"])
        status_control_container.pack(
            fill="x", padx=int(3 * 1.1), pady=int(1 * 1.1))

        # 左侧：状态信息
        status_left = tk.Frame(status_control_container,
                               bg=self.colors["bg_secondary"])
        status_left.pack(side="left", fill="x", expand=True)

        # 状态栏Canvas - 添加阴影效果
        status_canvas = tk.Canvas(
            status_left,
            height=int(16 * 1.1),  # 扩大1.1倍高度
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        status_canvas.pack(fill="x", pady=int(1 * 1.1))

        def update_status_with_shadow(text):
            status_canvas.delete("all")
            font_tuple = self.get_font(int(7 * 1.1), "normal")

            canvas_width = status_canvas.winfo_width()
            if canvas_width > 1:
                # 绘制多层阴影
                shadow_layers = [
                    (2, 2, "#000000"),
                    (1, 1, "#111111")
                ]

                for dx, dy, shadow_color in shadow_layers:
                    status_canvas.create_text(
                        int(6 * 1.1) + dx, int(8 * 1.1) + dy,
                        text=text, font=font_tuple, fill=shadow_color, anchor="w"
                    )

                # 绘制边框效果
                border_color = "#333333"
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    status_canvas.create_text(
                        int(6 * 1.1) + dx, int(8 * 1.1) + dy,
                        text=text, font=font_tuple, fill=border_color, anchor="w"
                    )

                # 主文字
                status_canvas.create_text(
                    int(6 * 1.1), int(8 * 1.1),
                    text=text, font=font_tuple, fill=self.colors["text_accent"], anchor="w"
                )

        # 右侧：透明度控制
        alpha_control = tk.Frame(
            status_control_container, bg=self.colors["bg_secondary"])
        alpha_control.pack(side="right", padx=(int(10 * 1.1), 0))

        # 透明度标签
        tk.Label(
            alpha_control,
            text="ALPHA:",
            font=self.get_font(int(6 * 1.1), "normal"),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_primary"],
        ).pack(side="left", padx=(0, int(2 * 1.1)))

        # 透明度滑块
        mini_alpha_var = tk.DoubleVar(value=self.current_alpha * 100)
        mini_info["alpha_var"] = mini_alpha_var  # 保存到mini_info

        mini_alpha_scale = tk.Scale(
            alpha_control,
            from_=80,  # 背景最小30%透明度
            to=100,    # 最大100%不透明
            orient=tk.HORIZONTAL,
            variable=mini_alpha_var,
            command=lambda v: self.on_mini_alpha_changed(v, mini_info),
            font=self.get_font(int(6 * 1.1)),
            bg=self.colors["bg_secondary"],
            fg=self.colors["neon_cyan"],
            activebackground=self.colors["neon_cyan"],
            highlightcolor=self.colors["neon_cyan"],
            troughcolor=self.colors["bg_primary"],
            length=int(60 * 1.1),  # 扩大1.1倍长度
            width=int(8 * 1.1),    # 扩大1.1倍宽度
            sliderlength=int(12 * 1.1),
            bd=0,
            relief="flat",
            showvalue=0,  # 不显示数值（用单独标签显示）
        )
        mini_alpha_scale.pack(side="left", padx=int(1 * 1.1))

        # 防止滑块区域触发窗口拖拽（但允许滑块本身的交互）
        def prevent_mini_window_drag(event):
            # 只阻止事件向上传播，不阻止滑块本身的功能
            event.stopPropagation = True

        alpha_control.bind("<Button-1>", prevent_mini_window_drag)
        alpha_control.bind("<B1-Motion>", prevent_mini_window_drag)

        # 透明度数值显示
        mini_alpha_label = tk.Label(
            alpha_control,
            text=f"{int(self.current_alpha * 100)}%",
            font=self.get_font(int(6 * 1.1), "normal"),
            bg=self.colors["bg_secondary"],
            fg=self.colors["neon_cyan"],
            width=4,
        )
        mini_alpha_label.pack(side="left", padx=(int(2 * 1.1), 0))
        mini_info["alpha_label"] = mini_alpha_label  # 保存到mini_info

        # 将mini_info添加到全局列表
        self.mini_windows.append(mini_info)

        # ACT启动按钮区域（底部信息框中央）- 高度刚好容纳按钮
        act_button_outer, act_button_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_green"],
            padding=int(2 * 1.1),  # 减小内边距
        )
        # 设置固定高度，刚好容纳按钮
        act_button_outer.configure(height=int(45 * 1.1))  # 按钮高度 + 最小边距
        act_button_outer.pack(fill="x", pady=(int(8 * 1.1), int(4 * 1.1)))
        act_button_outer.pack_propagate(False)  # 防止子控件改变外框大小

        # ACT按钮容器 - 居中
        act_button_container = tk.Frame(
            act_button_frame, bg=self.colors["bg_secondary"])
        act_button_container.pack(expand=True)

        # 使用主菜单风格的按钮
        # ACT配置选择和控制区域
        act_control_frame = tk.Frame(
            act_button_container, bg=self.colors["bg_secondary"])
        act_control_frame.pack(fill="x", pady=(int(2 * 1.1), int(1 * 1.1)))

        # 左侧：配置文件选择
        config_frame = tk.Frame(
            act_control_frame, bg=self.colors["bg_secondary"])
        config_frame.pack(side="left", fill="x", expand=True)

        config_label = tk.Label(
            config_frame,
            text="ACT配置:",
            font=self.get_font(int(8 * 1.1), "normal"),
            fg=self.colors["text_primary"],
            bg=self.colors["bg_secondary"]
        )
        config_label.pack(side="left", padx=(0, 5))

        # 配置文件下拉选择框
        self.act_config_var = tk.StringVar()
        self.config_combobox = tk.ttk.Combobox(
            config_frame,
            textvariable=self.act_config_var,
            font=self.get_font(int(8 * 1.1), "normal"),
            width=15,
            state="readonly"
        )
        self.config_combobox.pack(side="left", padx=(0, 10))

        # 绑定配置文件选择改变事件
        self.config_combobox.bind(
            "<<ComboboxSelected>>", self.on_act_config_changed)

        # 刷新配置文件列表
        self.refresh_act_configs()

        # 右侧：倒计时设置和启动按钮
        timer_control_frame = tk.Frame(
            act_control_frame, bg=self.colors["bg_secondary"])
        timer_control_frame.pack(side="right")

        def create_act_timer():
            # 获取选中的配置文件
            config_name = self.act_config_var.get()

            # 从JSON配置文件获取持续时间
            total_seconds = 300  # 默认5分钟

            # 重置当前配置
            self.current_act_config = None

            if config_name and config_name != "无配置文件":
                try:
                    config = self.load_act_config(config_name)
                    if config:
                        # 设置当前配置，供JASON阶段控制使用
                        self.current_act_config = config

                        if 'total_duration' in config:
                            total_seconds = config['total_duration']
                            print(
                                f"从配置文件 {config_name} 获取时长: {total_seconds}秒")
                        else:
                            print(
                                f"配置文件 {config_name} 中未找到 total_duration，使用默认5分钟")

                        # 调试信息：检查JASON阶段配置
                        if 'jason_phases' in config:
                            print(
                                f"[DEBUG] 已加载JASON阶段配置，包含 {len(config.get('jason_phases', {}))} 个阶段")
                        else:
                            print(f"[DEBUG] 配置文件中没有JASON阶段定义")
                except Exception as e:
                    print(f"解析配置文件时出错: {e}，使用默认5分钟")
            else:
                print("未选择配置文件，使用默认5分钟")

            self.launch_act_timer_window(mini, total_seconds, config_name)

        # ACT Start按钮（放在右侧的timer_control_frame中）
        act_start_button = self.create_enhanced_button(
            timer_control_frame,
            text="ACT Start",
            command=create_act_timer,
            color=self.colors["neon_green"],
            width=12,
            height=1,
            font_weight="bold"
        )
        act_start_button.pack(side="right")

        # 初始状态文本
        update_status_with_shadow("[MINI_CONSOLE_ACTIVE] 实时数据监控中...")

        def refresh_mini():
            if not mini.winfo_exists():
                return
            try:
                render_content()
                # 更新状态栏时间
                from datetime import datetime
                current_time = datetime.now().strftime("%H:%M:%S")
                update_status_with_shadow(
                    f"[{current_time}] MINI_CONSOLE_ACTIVE | 数据更新中..."
                )
            except Exception as e:
                update_status_with_shadow(
                    f"[ERROR] 数据更新失败: {str(e)[:20]}..."  # 缩短错误信息
                )
            mini.after(1000, refresh_mini)

        # 启动更新和动画
        render_content()
        mini.after(1000, refresh_mini)
        mini.after(100, mini_rgb_animate)

        # 添加小窗口淡入效果
        mini.after(150, lambda: self.fade_window_in(
            mini, mini.current_alpha, 0.2))

    def update_self_dps_bar(self, mini, user_data, sorted_users):
        """更新本人DPS条显示"""
        if not hasattr(mini, '_self_dps_container'):
            return

        container = mini._self_dps_container

        # 尝试检测本人数据
        self_uid = None
        self_data = None
        self_rank = 0

        # 优先使用保存的个人UID
        if self.personal_uid and self.personal_uid in user_data:
            self_uid = self.personal_uid
            self_data = user_data[self.personal_uid]
        else:
            # 检测方法1：通过UID映射查找本人
            if hasattr(self, 'uid_mapping'):
                for uid, info in user_data.items():
                    mapped_name = self.get_display_name(uid)
                    # 如果映射的名字包含特定标识（比如"本人"、"我"等）
                    if any(keyword in mapped_name.lower() for keyword in ['本人', '我', 'me', 'self']):
                        self_uid = uid
                        self_data = info
                        break

            # 检测方法2：如果没有找到，使用第一个玩家作为示例
            if not self_data and sorted_users:
                self_uid, self_data = sorted_users[0]

        # 计算排名
        if self_data:
            for rank, (uid, info) in enumerate(sorted_users, 1):
                if uid == self_uid:
                    self_rank = rank
                    break

        # 检查是否需要重建UI（数据变化才重建，减少闪烁）
        current_key = f"{self_uid}_{self_rank}_{len(sorted_users)}"
        if self_data:
            current_key += f"_{self_data.get('total_dps', 0):.0f}"

        last_key = getattr(mini, '_last_self_dps_key', '')

        if current_key == last_key:
            return  # 数据没有变化，不重建UI

        mini._last_self_dps_key = current_key

        # 清除现有显示（只有在数据变化时才清除）
        for widget in container.winfo_children():
            widget.destroy()

        if self_data:
            # 获取第一名的DPS数据用于比例计算
            first_place_dps = sorted_users[0][1].get(
                "total_dps", 0) if sorted_users else 0

            # 创建本人DPS条
            self.create_self_dps_display(
                container, self_uid, self_data, self_rank, len(sorted_users), first_place_dps)
        else:
            # 显示未检测到本人
            no_self_label = tk.Label(
                container,
                text="[SYSTEM]: 未检测到个人数据",
                font=self.get_font(int(8 * 1.1), "normal"),
                bg=self.colors["bg_secondary"],
                fg=self.colors["text_accent"]
            )
            no_self_label.pack(pady=int(5 * 1.1))

            # 如果有设置个人UID但数据中没有，显示提示
            if self.personal_uid:
                hint_label = tk.Label(
                    container,
                    text=f"个人UID ({self.personal_uid}) 暂无战斗数据",
                    font=self.get_font(int(7 * 1.1), "normal"),
                    bg=self.colors["bg_secondary"],
                    fg=self.colors["text_dim"]
                )
                hint_label.pack(pady=int(2 * 1.1))

    def create_self_dps_display(self, container, uid, data, rank, total_players, first_place_dps=0):
        """创建本人DPS显示条"""
        # 获取数据
        display_name = self.get_display_name(uid)
        profession = data.get("profession", "未知")
        total_damage = data.get("total_damage", {}).get("total", 0)
        dps = data.get("total_dps", 0)

        # 创建玩家信息显示区域（向上移动更多）
        player_info_frame = tk.Frame(container, bg=self.colors["bg_secondary"])
        player_info_frame.pack(fill="x", pady=(0, int(1 * 1.1)))

        # 玩家信息Canvas - 添加阴影效果
        player_info_canvas = tk.Canvas(
            player_info_frame,
            height=int(16 * 1.1),  # 增加高度防止底部被截断
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        player_info_canvas.pack(fill="x")

        # 在canvas上设置绘制状态缓存属性
        player_info_canvas._last_draw_data = {
            "info_text": "", "canvas_width": 0, "last_update": 0}

        def draw_player_info_with_shadow():
            canvas_width = player_info_canvas.winfo_width()
            if canvas_width <= 1:
                # 如果canvas尚未正确显示，延迟重试
                player_info_canvas.after(100, draw_player_info_with_shadow)
                return

            # 玩家信息文本
            info_text = f"#{rank} {display_name} [{profession}]"

            import time
            current_time = time.time()

            # 检查是否需要重绘（数据没有变化且时间间隔小于0.5秒则不重绘）
            time_since_last = current_time - \
                player_info_canvas._last_draw_data.get("last_update", 0)
            if (player_info_canvas._last_draw_data["info_text"] == info_text and
                    abs(player_info_canvas._last_draw_data["canvas_width"] - canvas_width) < 5 and
                    time_since_last < 0.5):
                return

            # 更新缓存
            player_info_canvas._last_draw_data["info_text"] = info_text
            player_info_canvas._last_draw_data["canvas_width"] = canvas_width
            player_info_canvas._last_draw_data["last_update"] = current_time

            player_info_canvas.delete("all")
            font_tuple = self.get_font(int(10 * 1.1), "bold")

            # 位置计算（左对齐，向上移动更多）
            x_pos = int(8 * 1.1)
            y_pos = int(8 * 1.1)  # 进一步向上移动

            # 绘制多层阴影
            shadow_layers = [
                (3, 3, "#000000"),
                (2, 2, "#111111"),
                (1, 1, "#222222")
            ]

            for dx, dy, shadow_color in shadow_layers:
                player_info_canvas.create_text(
                    x_pos + dx, y_pos + dy,
                    text=info_text, font=font_tuple,
                    fill=shadow_color, anchor="w"
                )

            # 绘制边框效果
            border_color = "#333333"
            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                player_info_canvas.create_text(
                    x_pos + dx, y_pos + dy,
                    text=info_text, font=font_tuple,
                    fill=border_color, anchor="w"
                )

            # 绘制主文字（使用高亮颜色）
            player_info_canvas.create_text(
                x_pos, y_pos,
                text=info_text, font=font_tuple,
                fill=self.colors["neon_yellow"], anchor="w"
            )

        # 绑定事件和初始绘制 - 使用更稳定的更新机制
        def on_configure(event):
            if event.widget == player_info_canvas:
                # 强制重绘，忽略缓存
                player_info_canvas._last_draw_data["last_update"] = 0
                player_info_canvas.after_idle(draw_player_info_with_shadow)

        player_info_canvas.bind("<Configure>", on_configure)
        # 初始绘制
        player_info_canvas.after(10, draw_player_info_with_shadow)

        # 创建Canvas用于绘制DPS条（添加阴影效果）
        canvas = tk.Canvas(
            container,
            height=int(25 * 1.1),  # 增加高度防止底部被截断
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        canvas.pack(fill="x", pady=(int(6 * 1.1), int(1 * 1.1)))

        # 在canvas上设置DPS条绘制状态缓存属性
        canvas._last_dps_data = {"dps": -1,
                                 "canvas_width": 0, "last_update": 0}

        def draw_self_dps_bar():
            canvas_width = canvas.winfo_width()
            if canvas_width <= 1:
                # 如果canvas尚未正确显示，延迟重试
                canvas.after(100, draw_self_dps_bar)
                return

            import time
            current_time = time.time()

            # 检查是否需要重绘（DPS数据没有显著变化且时间间隔小于0.5秒则不重绘）
            time_since_last = current_time - \
                canvas._last_dps_data.get("last_update", 0)
            if (abs(canvas._last_dps_data["dps"] - dps) < max(dps * 0.01, 1) and  # DPS变化小于1%或1点
                    abs(canvas._last_dps_data["canvas_width"] - canvas_width) < 5 and
                    time_since_last < 0.5):
                return

            # 更新缓存
            canvas._last_dps_data["dps"] = dps
            canvas._last_dps_data["canvas_width"] = canvas_width
            canvas._last_dps_data["last_update"] = current_time

            canvas.delete("all")

            # DPS条参数
            bar_width = canvas_width - int(40 * 1.1)
            bar_height = int(16 * 1.1)  # 减小高度
            bar_x = int(20 * 1.1)
            bar_y = int(5 * 1.1)

            # 绘制DPS条阴影背景
            shadow_offset = 2
            canvas.create_rectangle(
                bar_x + shadow_offset, bar_y + shadow_offset,
                bar_x + bar_width + shadow_offset, bar_y + bar_height + shadow_offset,
                fill="#000000",
                outline=""
            )

            # 绘制DPS条背景
            canvas.create_rectangle(
                bar_x, bar_y, bar_x + bar_width, bar_y + bar_height,
                fill=self.colors["bg_primary"],
                outline=self.colors["border_light"],
                width=1
            )

            # 绘制DPS条（根据与第一名的DPS比例计算长度）
            if first_place_dps > 0 and dps > 0:
                # 根据与第一名的DPS比例计算条长度
                dps_ratio = min(dps / first_place_dps, 1.0)  # 最大不超过100%
                bar_fill_width = int(bar_width * dps_ratio)
            else:
                # 如果没有第一名数据或DPS为0，使用固定长度
                bar_fill_width = int(bar_width * 0.1)  # 最小10%长度

            # DPS条阴影
            canvas.create_rectangle(
                bar_x + 1 + shadow_offset, bar_y + 1 + shadow_offset,
                bar_x + bar_fill_width + shadow_offset, bar_y + bar_height - 1 + shadow_offset,
                fill="#111111",
                outline=""
            )

            # DPS条主体
            canvas.create_rectangle(
                bar_x + 1, bar_y + 1, bar_x + bar_fill_width, bar_y + bar_height - 1,
                fill=self.colors["neon_yellow"],
                outline=""
            )

            # 绘制DPS数值 - 添加阴影效果
            dps_text = f"DPS: {dps:,.0f}"
            if dps >= 1000000:
                dps_text = f"DPS: {dps/1000000:.1f}M"
            elif dps >= 1000:
                dps_text = f"DPS: {dps/1000:.1f}K"

            dps_font = self.get_font(int(8 * 1.1), "bold")
            dps_x = bar_x + int(15 * 1.1)
            dps_y = bar_y + bar_height // 2

            # DPS数值阴影
            for dx, dy in [(1, 1), (2, 2)]:
                canvas.create_text(
                    dps_x + dx, dps_y + dy,
                    text=dps_text, font=dps_font,
                    fill="#000000", anchor="w"
                )

            # DPS主文字
            canvas.create_text(
                dps_x, dps_y,
                text=dps_text, font=dps_font,
                fill=self.colors["neon_green"], anchor="w"  # 修改为绿色
            )

            # 绘制总排名信息 - 添加阴影效果
            rank_info = f"Rank: {rank}/{total_players}"
            rank_font = self.get_font(int(7 * 1.1), "normal")
            rank_x = bar_x + bar_width - int(5 * 1.1)
            rank_y = bar_y + bar_height // 2

            # 排名信息阴影
            for dx, dy in [(1, 1), (2, 2)]:
                canvas.create_text(
                    rank_x + dx, rank_y + dy,
                    text=rank_info, font=rank_font,
                    fill="#000000", anchor="e"
                )

            # 排名主文字
            canvas.create_text(
                rank_x, rank_y,
                text=rank_info, font=rank_font,
                fill=self.colors["neon_cyan"], anchor="e"
            )

        # 绑定事件和初始绘制 - 使用更稳定的更新机制
        def on_dps_configure(event):
            if event.widget == canvas:
                # 强制重绘，忽略缓存
                canvas._last_dps_data["last_update"] = 0
                canvas.after_idle(draw_self_dps_bar)

        canvas.bind("<Configure>", on_dps_configure)
        # 初始绘制
        canvas.after(10, draw_self_dps_bar)

    def _close_minimal_mode(self, mini):
        """关闭最小模式并恢复主界面"""
        if mini and mini.winfo_exists():
            # 取消所有保存的after任务，防止字幕回收问题
            try:
                if hasattr(mini, '_after_tasks'):
                    for task_id in mini._after_tasks:
                        try:
                            mini.after_cancel(task_id)
                        except:
                            pass
                    mini._after_tasks.clear()
            except Exception as e:
                print(f"取消after任务时出错: {e}")

            # 从mini_windows列表中移除该窗口的引用
            self.mini_windows = [info for info in self.mini_windows
                                 if not (info.get("window") and info["window"] == mini)]
            mini.destroy()
        self.root.deiconify()

    def launch_act_timer_window(self, reference_window=None, duration=300, config_name=None):
        """启动ACT计时器窗口 - 使用MINI UI相同风格，可以设置相对于参考窗口的位置"""
        print(f"启动ACT timer，参考窗口: {reference_window}")  # 调试信息
        if reference_window:
            print(f"参考窗口是否存在: {reference_window.winfo_exists()}")  # 调试信息

        # 创建新的ACTACT窗口
        print("开始创建timer窗口")  # 调试信息
        timer_window = tk.Toplevel()
        timer_window.title("◊ ACT_TIMER_CONSOLE ◊")
        timer_window.geometry("500x600")  # 稍微增大以适应新布局
        timer_window.resizable(False, False)
        timer_window.wm_attributes("-topmost", True)
        timer_window.wm_attributes("-alpha", self.current_alpha)
        timer_window.overrideredirect(True)  # 使用无边框模式
        timer_window.configure(bg=self.colors["bg_primary"])

        # 如果有参考窗口，将timer窗口放置在其右边
        if reference_window and reference_window.winfo_exists():
            try:

                reference_window.update_idletasks()  # 确保窗口已完全更新
                ref_x = reference_window.winfo_x()
                ref_y = reference_window.winfo_y()
                ref_width = reference_window.winfo_width()

                # 计算新位置：参考窗口右边 + 10像素间距
                new_x = ref_x + ref_width + 10
                new_y = ref_y  # 与参考窗口顶部对齐

                timer_window.geometry(f"500x600+{new_x}+{new_y}")

            except Exception as e:

                # 如果定位失败，使用默认位置
                pass
        else:
            print("没有参考窗口，使用默认位置")  # 调试信息

        # 设置圆角窗口和RGB边框（与MINI UI相同）
        print("开始设置圆角窗口和RGB边框")  # 调试信息
        if Image is not None:
            try:
                print("PIL可用，创建圆角窗口")  # 调试信息

                import ctypes
                timer_window.update()
                hwnd = ctypes.windll.user32.GetParent(timer_window.winfo_id())
                if hwnd == 0:
                    hwnd = timer_window.winfo_id()

                width = 500
                height = 600
                corner_radius = 12

                hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                    0, 0, width, height, corner_radius * 2, corner_radius * 2
                )

                if hrgn:
                    ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
                else:
                    ctypes.windll.user32.SetWindowRgn(hwnd, 0, True)
            except Exception as e:
                pass

            # 创建RGB边框容器（与MINI UI相同）

            border_canvas = tk.Canvas(
                timer_window, bg=self.colors["bg_primary"], highlightthickness=0, bd=0)
            border_canvas.pack(fill="both", expand=True, padx=0, pady=0)

            # 主内容容器

            main_content_frame = tk.Frame(
                border_canvas, bg=self.colors["bg_primary"], bd=0, relief="flat")

            # 在Canvas中创建窗口
            border_space = 6
            content_window = border_canvas.create_window(
                border_space, border_space,
                anchor="nw",
                window=main_content_frame
            )

            timer_window._border_imgtk = None
            timer_window._border_cache_key = None
            timer_window.rgb_index = 0

            def render_timer_border():
                """渲染ACT窗口的RGB边框"""
                canvas_w = border_canvas.winfo_width()
                canvas_h = border_canvas.winfo_height()
                if canvas_w <= 0 or canvas_h <= 0:
                    return

                # 更新内容区域大小
                content_width = canvas_w - (border_space * 2)
                content_height = canvas_h - (border_space * 2)
                border_canvas.itemconfig(
                    content_window,
                    width=content_width,
                    height=content_height
                )

                current_color = self.border_colors[timer_window.rgb_index % len(
                    self.border_colors)]
                key = (canvas_w, canvas_h, current_color)

                if (getattr(timer_window, "_border_cache_key", None) == key and
                        timer_window._border_imgtk is not None):
                    return

                # 创建圆角背景
                scale = 1.5
                W, H = int(canvas_w * scale), int(canvas_h * scale)
                r = max(0, int(12 * scale))
                bw = max(1, int(3 * scale))

                if W <= bw * 2 or H <= bw * 2:
                    return

                img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)

                # 绘制背景
                bg_color = self.colors["bg_primary"]
                draw.rounded_rectangle(
                    [0, 0, W-1, H-1], radius=r, fill=bg_color)

                # 添加RGB边框发光效果
                try:
                    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    gdraw = ImageDraw.Draw(glow)
                    gdraw.rounded_rectangle([bw//2, bw//2, W-1-bw//2, H-1-bw//2],
                                            radius=r, outline=current_color, width=bw)
                    glow = glow.filter(
                        ImageFilter.GaussianBlur(1.5 * scale / 10))
                    img = Image.alpha_composite(img, glow)
                except Exception:
                    pass

                # 绘制边框
                draw.rounded_rectangle([bw//2, bw//2, W-1-bw//2, H-1-bw//2],
                                       radius=r, outline=current_color, width=bw)

                img = img.resize((canvas_w, canvas_h), resample=Image.LANCZOS)
                imgtk = ImageTk.PhotoImage(img)
                border_canvas.delete("bg_image")
                border_canvas.create_image(
                    0, 0, anchor="nw", image=imgtk, tags="bg_image")
                timer_window._border_imgtk = imgtk
                timer_window._border_cache_key = key

            def timer_rgb_animate():
                """ACT窗口RGB动画"""
                if not timer_window.winfo_exists():
                    return

                old_index = getattr(timer_window, 'rgb_index', 0)
                timer_window.rgb_index = (
                    timer_window.rgb_index + 1) % len(self.border_colors)

                if timer_window.rgb_index != old_index:
                    if hasattr(timer_window, '_timer_rgb_timer'):
                        timer_window.after_cancel(
                            timer_window._timer_rgb_timer)
                    timer_window._timer_rgb_timer = timer_window.after(
                        10, render_timer_border)

                timer_window.after(self.rgb_interval, timer_rgb_animate)

            def on_timer_resize(event):
                if hasattr(timer_window, '_timer_resize_timer'):
                    timer_window.after_cancel(timer_window._timer_resize_timer)
                timer_window._timer_resize_timer = timer_window.after(
                    100, render_timer_border)

            border_canvas.bind("<Configure>", on_timer_resize)
            timer_window.after(100, render_timer_border)
            timer_window.after(self.rgb_interval, timer_rgb_animate)

        else:

            # 回退为矩形边框
            main_content_frame = tk.Frame(
                timer_window, bg=self.colors["bg_primary"], bd=0, relief="flat")
            main_content_frame.pack(fill="both", expand=True, padx=6, pady=6)

        # 创建标题栏（与MINI UI相同风格）

        header_outer, header_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_yellow"],
            padding=2,
        )
        header_outer.configure(height=65)
        header_outer.pack(fill="x", pady=(6, 4))
        header_outer.pack_propagate(False)

        # 标题内容容器

        title_container = tk.Frame(
            header_frame, bg=self.colors["bg_secondary"])
        title_container.pack(fill="x", pady=int(3 * 1.1))

        # 主标题 - 使用Canvas添加阴影效果

        title_canvas = tk.Canvas(
            title_container,
            height=int(25 * 1.1),
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        title_canvas.pack(fill="x", pady=int(2 * 1.1))

        def draw_timer_title_with_shadow():
            title_canvas.delete("all")
            title_text = "▓▓▓ ACT_TIMER ▓▓▓"
            font_tuple = self.get_font(int(12 * 1.1), "normal")

            canvas_width = title_canvas.winfo_width()
            if canvas_width > 1:
                center_x = canvas_width // 2
                center_y = int(12 * 1.1)

                # 绘制多层阴影
                shadow_layers = [
                    (3, 3, "#000000"),
                    (2, 2, "#111111"),
                    (1, 1, "#222222")
                ]

                for dx, dy, shadow_color in shadow_layers:
                    title_canvas.create_text(
                        center_x + dx, center_y + dy,
                        text=title_text, font=font_tuple,
                        fill=shadow_color, anchor="center"
                    )

                # 绘制边框效果
                border_color = "#333333"
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    title_canvas.create_text(
                        center_x + dx, center_y + dy,
                        text=title_text, font=font_tuple,
                        fill=border_color, anchor="center"
                    )

                # 绘制主文字
                title_canvas.create_text(
                    center_x, center_y,
                    text=title_text, font=font_tuple,
                    fill=self.colors["neon_yellow"], anchor="center"
                )

        title_canvas.bind(
            "<Configure>", lambda e: draw_timer_title_with_shadow())
        title_canvas.after(10, draw_timer_title_with_shadow)

        # 存储Canvas引用用于拖拽
        timer_window.title_canvas = title_canvas

        # 副标题

        subtitle_canvas = tk.Canvas(
            title_container,
            height=int(16 * 1.1),
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        subtitle_canvas.pack(fill="x")

        def draw_timer_subtitle_with_shadow():
            # 检查canvas是否仍然存在
            try:
                if not subtitle_canvas.winfo_exists():
                    return
            except:
                return

            subtitle_canvas.delete("all")
            subtitle_text = "[JASON_LIBRARY_TIMING]"
            font_tuple = self.get_font(int(8 * 1.1), "normal")

            try:
                canvas_width = subtitle_canvas.winfo_width()
                if canvas_width > 1:
                    center_x = canvas_width // 2
                    center_y = int(8 * 1.1)

                    # 绘制阴影
                    shadow_layers = [
                        (2, 2, "#000000"),
                        (1, 1, "#111111")
                    ]

                    for dx, dy, shadow_color in shadow_layers:
                        subtitle_canvas.create_text(
                            center_x + dx, center_y + dy,
                            text=subtitle_text, font=font_tuple,
                            fill=shadow_color, anchor="center"
                        )

                    # 绘制边框效果
                    border_color = "#333333"
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        subtitle_canvas.create_text(
                            center_x + dx, center_y + dy,
                            text=subtitle_text, font=font_tuple,
                            fill=border_color, anchor="center"
                        )

                    # 绘制主文字
                    subtitle_canvas.create_text(
                        center_x, center_y,
                        text=subtitle_text, font=font_tuple,
                        fill=self.colors["neon_cyan"], anchor="center"
                    )
            except:
                # 如果canvas已被销毁，静默忽略错误
                pass

        # 保存after任务ID到timer窗口
        if not hasattr(timer_window, '_after_tasks'):
            timer_window._after_tasks = []

        def safe_timer_bind():
            try:
                subtitle_canvas.bind(
                    "<Configure>", lambda e: draw_timer_subtitle_with_shadow())
            except:
                pass

        def safe_timer_after():
            try:
                task_id = subtitle_canvas.after(
                    10, draw_timer_subtitle_with_shadow)
                timer_window._after_tasks.append(task_id)
            except:
                pass

        safe_timer_bind()
        safe_timer_after()

        # 存储Canvas引用用于拖拽
        timer_window.subtitle_canvas = subtitle_canvas

        # 自定义关闭函数，清理关联关系

        def close_timer_window():
            # 从参考窗口的关联列表中移除
            if hasattr(timer_window, 'reference_window') and timer_window.reference_window:
                ref_window = timer_window.reference_window
                if hasattr(ref_window, 'associated_timers') and timer_window in ref_window.associated_timers:
                    ref_window.associated_timers.remove(timer_window)

            # 从全局列表中移除
            if timer_window in self.timer_windows:
                self.timer_windows.remove(timer_window)

            # 销毁窗口
            timer_window.destroy()

        # 关闭按钮

        close_btn = self.create_enhanced_button(
            title_container, "✕", close_timer_window,
            self.colors["neon_pink"], width=2, height=1
        )
        close_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-3, y=2)

        # ACT显示区域（使用圆角框架）

        timer_outer, timer_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_accent"],
            border_color=self.colors["neon_cyan"],
            padding=int(8 * 1.1),
        )
        timer_outer.configure(height=80)
        timer_outer.pack(fill="x", pady=(0, int(8 * 1.1)))
        timer_outer.pack_propagate(False)

        # 初始化ACT变量
        print("初始化ACT变量")  # 调试信息
        timer_window.timer_running = False
        timer_window.start_time = None
        timer_window.elapsed_time = 0
        timer_window.waiting_for_damage = False  # 是否在等待第一次伤害
        timer_window.total_duration = duration  # 使用传入的倒计时时长
        timer_window.damage_detected = False  # 是否检测到伤害
        timer_window.last_damage_count = 0  # 上次的伤害计数

        # 加载ACT配置
        timer_window.act_config = None
        if config_name:
            timer_window.act_config = self.load_act_config(config_name)
            if timer_window.act_config:
                # 如果配置文件指定了持续时间，则使用配置文件的
                if 'total_duration' in timer_window.act_config:
                    timer_window.total_duration = timer_window.act_config['total_duration']

        timer_window.alerts_triggered = set()  # 已触发的提醒
        # 跳过机制计数器 {alert_key: {'count': x, 'skip_count': y}}
        timer_window.skip_counters = {}
        print("ACT变量初始化完成")  # 调试信息

        # 时间显示Canvas - 添加阴影效果

        time_canvas = tk.Canvas(
            timer_frame,
            height=100,  # 增加高度以容纳阶段信息
            bg=self.colors["bg_accent"],
            highlightthickness=0,
            bd=0
        )
        time_canvas.pack(fill="x", pady=10)

        def draw_time_with_shadow(time_text="00:00:00", text_color=None, glow_effect=False, phase_info=None, team_damage=None):
            time_canvas.delete("all")
            font_tuple = self.get_font(24, "bold")

            # 如果没有指定颜色，使用默认的青色
            if text_color is None:
                text_color = self.colors["neon_cyan"]

            canvas_width = time_canvas.winfo_width()
            canvas_height = time_canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                center_x = canvas_width // 2
                time_y = 20  # 时间显示位置，调整得更靠上一些

                # 如果启用辉光效果，绘制荧光辉光
                if glow_effect:
                    # 多层辉光效果，从外到内逐渐增强
                    glow_layers = [
                        (12, 0.1),  # 最外层，非常淡
                        (8, 0.2),   # 中层
                        (6, 0.3),   # 内层
                        (4, 0.4),   # 最内层
                    ]

                    # 计算辉光颜色
                    def add_alpha_to_color(hex_color, alpha):
                        # 简化的颜色透明度处理
                        hex_color = hex_color.lstrip('#')
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        # 混合到背景色
                        bg_r, bg_g, bg_b = 30, 30, 40  # 背景色近似
                        final_r = int(r * alpha + bg_r * (1 - alpha))
                        final_g = int(g * alpha + bg_g * (1 - alpha))
                        final_b = int(b * alpha + bg_b * (1 - alpha))
                        return f"#{final_r:02x}{final_g:02x}{final_b:02x}"

                    # 绘制辉光层
                    for radius, alpha in glow_layers:
                        glow_color = add_alpha_to_color(text_color, alpha)
                        for angle in range(0, 360, 15):  # 每15度一个点
                            import math
                            dx = int(radius * math.cos(math.radians(angle)))
                            dy = int(radius * math.sin(math.radians(angle)))
                            time_canvas.create_text(
                                center_x + dx, time_y + dy,
                                text=time_text, font=font_tuple,
                                fill=glow_color, anchor="center"
                            )

                # 绘制时间的多层阴影
                shadow_layers = [
                    (4, 4, "#000000"),
                    (3, 3, "#111111"),
                    (2, 2, "#222222")
                ]

                for dx, dy, shadow_color in shadow_layers:
                    time_canvas.create_text(
                        center_x + dx, time_y + dy,
                        text=time_text, font=font_tuple,
                        fill=shadow_color, anchor="center"
                    )

                # 绘制时间的边框效果
                border_color = "#444444"
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    time_canvas.create_text(
                        center_x + dx, time_y + dy,
                        text=time_text, font=font_tuple,
                        fill=border_color, anchor="center"
                    )

                # 绘制主时间文字
                time_canvas.create_text(
                    center_x, time_y,
                    text=time_text, font=font_tuple,
                    fill=text_color, anchor="center"
                )

                # 绘制队伍总伤害（在时间右边）
                if team_damage is not None:
                    damage_text = self.format_damage_number(team_damage)
                    damage_font = self.get_font(14, "bold")
                    damage_color = self.colors["neon_orange"]
                    damage_x = canvas_width - 10  # 右侧位置
                    damage_y = 15  # 稍微靠上

                    # 绘制伤害数字的阴影
                    for dx, dy, shadow_color in [(2, 2, "#000000"), (1, 1, "#222222")]:
                        time_canvas.create_text(
                            damage_x + dx, damage_y + dy,
                            text=damage_text, font=damage_font,
                            fill=shadow_color, anchor="ne"
                        )

                    # 绘制边框效果
                    for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                        time_canvas.create_text(
                            damage_x + dx, damage_y + dy,
                            text=damage_text, font=damage_font,
                            fill="#444444", anchor="ne"
                        )

                    # 绘制主伤害文字
                    time_canvas.create_text(
                        damage_x, damage_y,
                        text=damage_text, font=damage_font,
                        fill=damage_color, anchor="ne"
                    )

                # 绘制阶段信息
                if phase_info:
                    phase_name = phase_info.get('name', '')
                    # 移除阶段描述显示，只保留阶段名称

                    # 阶段名称在左边 - 固定字体大小和样式
                    if phase_name:
                        # 修复：处理阶段名称中的换行符
                        phase_name = phase_name.replace(
                            '/n', '\n')  # 将 /n 转换为 \n

                        # 固定阶段名称字体 - 12号字体，粗体，使用渐变色
                        name_font = self.get_font(12, "bold")
                        name_color = self.colors["neon_purple"]  # 使用紫色作为阶段名称颜色

                        # 处理多行阶段名称
                        name_lines = phase_name.split('\n')
                        line_height = 15  # 行高
                        start_y = 8

                        for i, line in enumerate(name_lines):
                            current_y = start_y + i * line_height

                            # 绘制阶段名称的多层阴影效果
                            shadow_offsets = [
                                (2, 2, "#000000"), (1, 1, "#222222")]
                            for dx, dy, shadow_color in shadow_offsets:
                                time_canvas.create_text(
                                    10 + dx, current_y + dy, text=line, font=name_font,
                                    fill=shadow_color, anchor="nw"
                                )

                            # 绘制边框效果
                            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                time_canvas.create_text(
                                    10 + dx, current_y + dy, text=line, font=name_font,
                                    fill="#444444", anchor="nw"
                                )

                            # 绘制主文字
                            time_canvas.create_text(
                                10, current_y, text=line, font=name_font,
                                fill=name_color, anchor="nw"
                            )

        time_canvas.bind("<Configure>", lambda e: draw_time_with_shadow())
        timer_window.draw_time_with_shadow = draw_time_with_shadow
        # 显示初始倒计时时间（在配置加载后显示）

        def show_initial_time():
            initial_time = f"{timer_window.total_duration//3600:02d}:{(timer_window.total_duration%3600)//60:02d}:{timer_window.total_duration%60:02d}"
            current_phase = self.get_current_phase(timer_window, 0)  # 获取初始阶段
            team_damage = self.get_team_total_damage()  # 获取队伍总伤害
            draw_time_with_shadow(
                initial_time, self.colors["neon_cyan"], False, current_phase, team_damage)

        timer_window.after(10, show_initial_time)

        # 控制按钮区域（使用圆角框架）

        control_outer, control_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_green"],
            padding=int(4 * 1.1),
        )
        control_outer.configure(height=60)
        control_outer.pack(fill="x", pady=(0, int(8 * 1.1)))
        control_outer.pack_propagate(False)

        # 按钮容器

        button_container = tk.Frame(
            control_frame, bg=self.colors["bg_secondary"])
        button_container.pack(expand=True, pady=5)

        # 使用增强按钮风格

        start_button = self.create_enhanced_button(
            button_container, "Start",
            lambda: self.toggle_timer(timer_window, start_button),
            self.colors["neon_green"], width=8, height=1, font_weight="bold"
        )
        start_button.pack(side="left", padx=5)

        reset_button = self.create_enhanced_button(
            button_container, "Reset",
            lambda: self.reset_timer(timer_window, start_button),
            self.colors["neon_yellow"], width=8, height=1, font_weight="bold"
        )
        reset_button.pack(side="left", padx=5)

        # 事件记录区域（使用圆角框架）

        events_outer, events_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_purple"],
            padding=int(4 * 1.1),
        )
        events_outer.pack(fill="both", expand=True)

        # 事件标题Canvas - 添加阴影效果
        events_title_canvas = tk.Canvas(
            events_frame,
            height=int(20 * 1.1),
            bg=self.colors["bg_secondary"],
            highlightthickness=0,
            bd=0
        )
        events_title_canvas.pack(fill="x", pady=(5, 5))

        def draw_events_title_with_shadow():
            events_title_canvas.delete("all")
            title_text = "[JASON_LIBRARY_EVENTS]"
            font_tuple = self.get_font(int(10 * 1.1), "bold")

            canvas_width = events_title_canvas.winfo_width()
            if canvas_width > 1:
                center_x = canvas_width // 2
                center_y = int(10 * 1.1)

                # 绘制阴影
                for dx, dy in [(2, 2), (1, 1)]:
                    events_title_canvas.create_text(
                        center_x + dx, center_y + dy,
                        text=title_text, font=font_tuple,
                        fill="#000000", anchor="center"
                    )

                # 绘制主文字
                events_title_canvas.create_text(
                    center_x, center_y,
                    text=title_text, font=font_tuple,
                    fill=self.colors["neon_purple"], anchor="center"
                )

        events_title_canvas.bind(
            "<Configure>", lambda e: draw_events_title_with_shadow())
        events_title_canvas.after(10, draw_events_title_with_shadow)

        # 事件列表（使用圆角列表框）

        try:
            events_container = self.create_rounded_listbox(
                events_frame,
                height=12,
                bg=self.colors["bg_primary"],
                fg=self.colors["text_primary"],
                selectbackground=self.colors["neon_cyan"],
                selectforeground=self.colors["bg_primary"],
                font=self.get_font(9, "normal")
            )
            events_container.pack(
                fill="both", expand=True, padx=5, pady=(0, 5))
            # 获取真正的listbox
            events_listbox = events_container.listbox

        except Exception as e:

            import traceback
            traceback.print_exc()
            # 使用简单的Listbox作为回退
            events_listbox = tk.Listbox(
                events_frame,
                height=12,
                bg=self.colors["bg_primary"],
                fg=self.colors["text_primary"],
                selectbackground=self.colors["neon_cyan"],
                selectforeground=self.colors["bg_primary"],
                font=self.get_font(9, "normal")
            )
            events_listbox.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # 存储引用
        timer_window.events_listbox = events_listbox
        timer_window.start_button = start_button

        # 延迟0.1秒自动执行reset修复初始显示问题
        def auto_reset():
            """自动执行reset来修复初始显示问题"""
            try:
                self.reset_timer(timer_window, timer_window.start_button)
                print("自动执行了reset以修复初始显示")
            except Exception as e:
                print(f"自动reset时出错: {e}")

        timer_window.after(300, auto_reset)  # 延迟0.3秒自动执行reset

        # 添加TTS和明显提醒模式选项区域
        options_outer, options_frame = self.create_rounded_frame(
            main_content_frame,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["neon_orange"],
            padding=int(3 * 1.1),
        )
        options_outer.configure(height=80)
        options_outer.pack(fill="x", pady=(int(8 * 1.1), 0))
        options_outer.pack_propagate(False)

        # 选项容器
        options_container = tk.Frame(
            options_frame, bg=self.colors["bg_secondary"])
        options_container.pack(expand=True, pady=5)

        # TTS功能选项
        timer_window.tts_enabled = tk.BooleanVar(value=False)
        tts_checkbox = tk.Checkbutton(
            options_container,
            text="启用TTS语音播报",
            variable=timer_window.tts_enabled,
            font=self.get_font(int(9 * 1.1), "normal"),
            fg=self.colors["text_primary"],
            bg=self.colors["bg_secondary"],
            selectcolor=self.colors["bg_accent"],
            activebackground=self.colors["bg_secondary"],
            activeforeground=self.colors["neon_cyan"],
            bd=0,
            highlightthickness=0
        )
        tts_checkbox.pack(anchor="w", pady=2)

        # 明显提醒模式选项
        timer_window.prominent_alert_enabled = tk.BooleanVar(value=False)
        prominent_checkbox = tk.Checkbutton(
            options_container,
            text="明显提醒模式(屏幕顶部显示)",
            variable=timer_window.prominent_alert_enabled,
            font=self.get_font(int(9 * 1.1), "normal"),
            fg=self.colors["text_primary"],
            bg=self.colors["bg_secondary"],
            selectcolor=self.colors["bg_accent"],
            activebackground=self.colors["bg_secondary"],
            activeforeground=self.colors["neon_cyan"],
            bd=0,
            highlightthickness=0
        )
        prominent_checkbox.pack(anchor="w", pady=2)

        # 初始化明显提醒窗口为None
        timer_window.prominent_window = None
        timer_window.alert_fade_window = None

        # JASON阶段控制面板
        self.create_jason_control_panel(main_content_frame, timer_window)

        # 启动ACT更新循环

        try:

            self.update_timer_display(timer_window)

        except Exception as e:

            import traceback
            traceback.print_exc()

        # 将timer窗口添加到全局列表
        self.timer_windows.append(timer_window)

        print(f"Timer窗口已添加到全局列表，当前全局timer数量: {len(self.timer_windows)}")

        # 如果有参考窗口，建立关联关系
        if reference_window and reference_window.winfo_exists():

            # 为参考窗口添加关联的timer窗口列表（如果还没有的话）
            if not hasattr(reference_window, 'associated_timers'):
                reference_window.associated_timers = []

            reference_window.associated_timers.append(timer_window)

            print(
                f"Timer窗口已添加到参考窗口，列表长度: {len(reference_window.associated_timers)}")

            # 为timer窗口记录参考窗口
            timer_window.reference_window = reference_window

            print(
                f"Timer窗口的reference_window已设置为: {timer_window.reference_window}")

            print(
                f"Timer窗口已关联到参考窗口，当前关联数量: {len(reference_window.associated_timers)}")
        else:

            # 记录初始事件
            self.add_timer_event(timer_window, "ACT Timer Console 已启动")

        # 设置窗口关闭事件处理
        def on_timer_window_close():
            try:
                # 停止计时器运行
                timer_window.timer_running = False

                # 取消所有保存的after任务，防止字幕回收问题
                if hasattr(timer_window, '_after_tasks'):
                    for task_id in timer_window._after_tasks:
                        try:
                            timer_window.after_cancel(task_id)
                        except:
                            pass
                    timer_window._after_tasks.clear()
            except Exception as e:
                print(f"清理计时器窗口after任务时出错: {e}")

            try:
                # 清理明显提醒窗口及其所有任务
                if hasattr(timer_window, 'prominent_window') and timer_window.prominent_window:
                    try:
                        # 清理prominent_window的所有after任务
                        if hasattr(timer_window.prominent_window, '_after_tasks'):
                            for task_id in timer_window.prominent_window._after_tasks:
                                try:
                                    timer_window.prominent_window.after_cancel(
                                        task_id)
                                except:
                                    pass
                    except:
                        pass

                    try:
                        timer_window.prominent_window.destroy()
                    except:
                        pass

                    timer_window.prominent_window = None
            except Exception as e:
                print(f"清理明显提醒窗口时出错: {e}")

            try:
                # 清理警告队列
                if hasattr(timer_window, 'alert_queue'):
                    timer_window.alert_queue.clear()
                    timer_window.alert_queue_processing = False
            except Exception as e:
                print(f"清理警告队列时出错: {e}")

            try:
                # 从全局列表中移除
                if timer_window in self.timer_windows:
                    self.timer_windows.remove(timer_window)
            except Exception as e:
                print(f"从全局列表移除timer窗口时出错: {e}")

            try:
                timer_window.destroy()
            except Exception as e:
                print(f"销毁timer窗口时出错: {e}")

        timer_window.protocol("WM_DELETE_WINDOW", on_timer_window_close)

        # 添加窗口淡入效果
        self.fade_window_in(timer_window, self.current_alpha, 0.2)

        # 最终验证
        print(f"===== Timer创建完成 =====")
        print(f"timer_window对象存在: {timer_window.winfo_exists()}")
        print(f"全局timer_windows列表长度: {len(self.timer_windows)}")
        print(f"timer在列表中: {timer_window in self.timer_windows}")
        if reference_window:
            print(f"reference_window存在: {reference_window.winfo_exists()}")
            print(
                f"reference_window.associated_timers长度: {len(getattr(reference_window, 'associated_timers', []))}")
        print(f"==========================")

    def toggle_timer(self, timer_window, start_button):
        """切换ACT开始/暂停状态"""
        if not timer_window.timer_running:
            # 开始计时
            timer_window.timer_running = True
            timer_window.waiting_for_damage = True  # 等待伤害检测
            timer_window.damage_detected = False
            timer_window.start_time = None  # 先不设置开始时间

            # 由于使用增强按钮，需要通过重新配置来改变文字
            start_button.configure(text="Stop")
            self.add_timer_event(timer_window, "ACT已开始 - 等待开战")

            # 显示等待状态
            team_damage = self.get_team_total_damage()
            timer_window.draw_time_with_shadow(
                f"Waiting for Battle...", self.colors["neon_yellow"], False, None, team_damage)
        else:
            # 暂停计时
            timer_window.timer_running = False
            timer_window.waiting_for_damage = False
            start_button.configure(text="Resume")
            self.add_timer_event(timer_window, "ACT已暂停")

    def reset_timer(self, timer_window, start_button):
        """重置ACT"""
        timer_window.timer_running = False
        timer_window.waiting_for_damage = False
        timer_window.damage_detected = False
        timer_window.start_time = None
        timer_window.elapsed_time = 0
        timer_window.last_damage_count = 0
        # 重置初始伤害计数
        if hasattr(timer_window, 'initial_damage_count'):
            delattr(timer_window, 'initial_damage_count')
        # 重置已触发的提醒
        if hasattr(timer_window, 'alerts_triggered'):
            timer_window.alerts_triggered.clear()

        # 重置警告队列
        if hasattr(timer_window, 'alert_queue'):
            timer_window.alert_queue.clear()
            timer_window.alert_queue_processing = False

        # 重置伤害阈值触发记录
        if hasattr(timer_window, 'triggered_thresholds'):
            timer_window.triggered_thresholds.clear()

        # 重置字体颜色和过渡状态
        if hasattr(timer_window, 'color_transition'):
            timer_window.color_transition = {
                'active': False,
                'start_color': self.colors["neon_cyan"],
                'target_color': self.colors["neon_cyan"],
                'current_color': self.colors["neon_cyan"],
                'progress': 0.0,
                'duration': 0.5,
                'transition_start': time.time(),
                'glow_intensity': 0.0,
                'target_glow': 0.0
            }

        team_damage = self.get_team_total_damage()
        timer_window.draw_time_with_shadow(
            f"{timer_window.total_duration//60:02d}:{timer_window.total_duration%60:02d}:00",
            self.colors["neon_cyan"], False, None, team_damage)
        start_button.configure(text="Start")
        self.add_timer_event(timer_window, "ACT已重置")

    def update_timer_display(self, timer_window):
        """更新ACT显示"""
        try:
            # 检查timer_window是否仍然存在
            if not timer_window.winfo_exists():
                return
        except tk.TclError:
            # 窗口已被销毁
            return
        except AttributeError:
            # timer_window对象无效
            return

        if timer_window.timer_running:
            # 如果在等待伤害检测
            if timer_window.waiting_for_damage:
                # 检查是否有新的伤害
                current_damage_count = self.get_current_damage_count()

                # 调试信息：显示当前伤害计数
                debug_text = f"等待战斗开始... ({current_damage_count})"
                # 调试信息
                print(
                    f"[DEBUG] 伤害检测: 当前={current_damage_count}, 上次={timer_window.last_damage_count}")

                # 如果是第一次检查，记录初始伤害值
                if not hasattr(timer_window, 'initial_damage_count'):
                    timer_window.initial_damage_count = current_damage_count
                    timer_window.last_damage_count = current_damage_count

                # 检测伤害变化（任何增加都算作新伤害）
                if current_damage_count > timer_window.last_damage_count:
                    # 检测到伤害，开始倒计时
                    timer_window.waiting_for_damage = False
                    timer_window.damage_detected = True
                    timer_window.start_time = time.time()
                    timer_window.elapsed_time = 0
                    damage_increase = current_damage_count - timer_window.last_damage_count

                    # 设置JASON战斗开始时间（用于警告系统）
                    self.jason_combat_start_time = timer_window.start_time
                    self.jason_phase_start_time = timer_window.start_time  # 第一阶段开始时间与战斗开始时间相同
                    print(
                        f"[DEBUG] 战斗开始！设置JASON时间基准: {self.jason_combat_start_time}")

                    # 伤害阈值检测机制
                    self.check_damage_thresholds(
                        timer_window, current_damage_count, damage_increase)

                    # 如果有配置文件，使用配置文件的时长
                    if hasattr(timer_window, 'act_config') and timer_window.act_config:
                        if 'total_duration' in timer_window.act_config:
                            timer_window.total_duration = timer_window.act_config['total_duration']
                            self.add_timer_event(
                                timer_window, f"🔥Battle Start！使用配置时长: {timer_window.total_duration}秒")
                        else:
                            self.add_timer_event(
                                timer_window, f"🔥Battle Start！使用默认时长: {timer_window.total_duration}秒")
                    else:
                        self.add_timer_event(
                            timer_window, f"🔥Battle Start！无配置文件，使用默认时长: {timer_window.total_duration}秒")

                    # 如果启用了明显提醒模式，创建明显提醒窗口
                    if (hasattr(timer_window, 'prominent_alert_enabled') and
                            timer_window.prominent_alert_enabled.get()):
                        self.create_prominent_alert_window(timer_window)

                    # 立即显示倒计时开始
                    remaining_time = timer_window.total_duration
                    hours = int(remaining_time // 3600)
                    minutes = int((remaining_time % 3600) // 60)
                    seconds = int(remaining_time % 60)
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    team_damage = self.get_team_total_damage()
                    timer_window.draw_time_with_shadow(
                        time_str, self.colors["neon_green"], False, None, team_damage)

                    # 同时更新明显提醒窗口
                    if (hasattr(timer_window, 'prominent_alert_enabled') and
                        timer_window.prominent_alert_enabled.get() and
                        hasattr(timer_window, 'prominent_window') and
                            timer_window.prominent_window):
                        try:
                            if timer_window.prominent_window.winfo_exists():
                                timer_window.prominent_window.draw_prominent_time(
                                    time_str, self.colors["neon_green"], False, None)  # 战斗开始时不需要辉光，也没有阶段信息
                        except (tk.TclError, AttributeError):
                            # prominent_window已被销毁或无效
                            timer_window.prominent_window = None
                else:
                    # 更新last_damage_count以便下次比较
                    timer_window.last_damage_count = current_damage_count
                    # 继续显示等待状态
                    team_damage = self.get_team_total_damage()
                    timer_window.draw_time_with_shadow(
                        "Waiting for Battle...", self.colors["neon_yellow"], False, None, team_damage)

            # 如果已经检测到伤害，进行倒计时
            elif timer_window.damage_detected and timer_window.start_time is not None:
                timer_window.elapsed_time = time.time() - timer_window.start_time

                # 计算剩余时间（倒计时）
                remaining_time = max(
                    0, timer_window.total_duration - timer_window.elapsed_time)

                # 处理ACT配置中的提醒
                if hasattr(timer_window, 'act_config') and timer_window.act_config:
                    self.process_act_alerts(
                        timer_window, timer_window.elapsed_time, remaining_time)

                # 检查JASON阶段警告
                current_time = time.time()
                self.check_phase_warnings(current_time)

                if remaining_time <= 0:
                    # 倒计时结束
                    timer_window.timer_running = False

                    # TTS语音提示
                    if hasattr(timer_window, 'tts_enabled') and timer_window.tts_enabled.get():
                        try:
                            self.speak_text(
                                "Boss已经狂暴", source_type="boss_rage")
                        except Exception as e:
                            print(f"TTS播放失败: {e}")

                    # 显示特殊消息
                    special_message = "God bless you :D"
                    team_damage = self.get_team_total_damage()
                    timer_window.draw_time_with_shadow(
                        special_message, self.colors["neon_red"], True, None, team_damage)  # 启用辉光效果

                    # 同时更新明显提醒窗口
                    if (hasattr(timer_window, 'prominent_alert_enabled') and
                        timer_window.prominent_alert_enabled.get() and
                        hasattr(timer_window, 'prominent_window') and
                            timer_window.prominent_window):
                        try:
                            if timer_window.prominent_window.winfo_exists():
                                timer_window.prominent_window.draw_prominent_time(
                                    special_message, self.colors["neon_red"], True, None)  # 启用辉光效果
                        except (tk.TclError, AttributeError):
                            # prominent_window已被销毁或无效
                            timer_window.prominent_window = None

                    self.add_timer_event(timer_window, "BOSS已经狂暴！倒计时结束！")
                else:
                    # 格式化剩余时间显示
                    hours = int(remaining_time // 3600)
                    minutes = int((remaining_time % 3600) // 60)
                    seconds = int(remaining_time % 60)

                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                    # 多重颜色判断机制 - 同时考虑绝对时间、百分比和即将到达的警告/阶段
                    remaining_ratio = remaining_time / timer_window.total_duration
                    elapsed_time = timer_window.elapsed_time

                    # 获取下一个即将到达的警告或阶段切换时间
                    next_event_time = None

                    # 检查ACT配置中的警告
                    if hasattr(timer_window, 'act_config') and timer_window.act_config:
                        alerts = timer_window.act_config.get('alerts', [])
                        for alert in alerts:
                            if alert.get('type') == 'timed':
                                trigger_time = alert.get('trigger_time', 0)
                                # 如果警告时间在当前时间之后
                                if trigger_time > elapsed_time:
                                    if next_event_time is None or trigger_time < next_event_time:
                                        next_event_time = trigger_time

                        # 检查阶段切换时间
                        phases = timer_window.act_config.get('phases', [])
                        for phase in phases:
                            phase_start = phase.get('start_time', 0)
                            # 如果阶段开始时间在当前时间之后
                            if phase_start > elapsed_time:
                                if next_event_time is None or phase_start < next_event_time:
                                    next_event_time = phase_start

                    # 计算距离下一个事件的时间
                    time_to_next_event = None
                    if next_event_time is not None:
                        time_to_next_event = next_event_time - elapsed_time

                    # 初始化颜色过渡状态
                    if not hasattr(timer_window, '_color_transition'):
                        timer_window._color_transition = {
                            'current_color': self.colors["neon_cyan"],
                            'target_color': self.colors["neon_cyan"],
                            'transition_start': time.time(),
                            'glow_intensity': 0.0,
                            'target_glow': 0.0
                        }

                    # 绝对时间条件 - 只保留事件相关的警告
                    # 移除了固定时间警告(5秒/2秒)以避免叠加问题

                    # 百分比条件
                    ratio_critical = remaining_ratio < 0.25  # 小于25%
                    ratio_warning = remaining_ratio < 0.5   # 小于50%

                    # 颜色判断逻辑 - 按优先级确定最终颜色
                    # 红色条件（最高优先级）
                    red_conditions = []
                    if ratio_critical:
                        red_conditions.append("比例危险")

                    # 黄色条件（中等优先级）
                    yellow_conditions = []
                    if ratio_warning and not ratio_critical:
                        yellow_conditions.append("比例警告")

                    # 确定目标颜色和辉光强度
                    target_color = self.colors["neon_cyan"]
                    target_glow = 0.0

                    if red_conditions:
                        target_color = self.colors["neon_red"]
                        # 红色条件越多，辉光越强
                        if len(red_conditions) >= 3:
                            target_glow = 1.0  # 满足所有条件
                        elif len(red_conditions) >= 2:
                            target_glow = 0.8  # 满足两个条件
                        else:
                            target_glow = 0.6  # 满足一个条件
                    elif yellow_conditions:
                        target_color = self.colors["neon_yellow"]
                        # 黄色条件越多，辉光越强
                        if len(yellow_conditions) >= 3:
                            target_glow = 0.8
                        elif len(yellow_conditions) >= 2:
                            target_glow = 0.6
                        else:
                            target_glow = 0.4

                    # 颜色过渡逻辑
                    transition = timer_window._color_transition
                    current_time = time.time()

                    # 如果目标颜色变化，开始新的过渡
                    if target_color != transition['target_color']:
                        transition['current_color'] = self.interpolate_colors(
                            transition['current_color'], transition['target_color'], 1.0)
                        transition['target_color'] = target_color
                        transition['transition_start'] = current_time

                    # 计算颜色过渡进度（0.3秒内完成）
                    color_progress = min(
                        1.0, (current_time - transition['transition_start']) / 0.3)
                    color = self.interpolate_colors(
                        transition['current_color'], target_color, color_progress)

                    # 辉光过渡逻辑（0.2秒内完成）
                    if target_glow != transition['target_glow']:
                        transition['target_glow'] = target_glow
                        transition['glow_start'] = current_time

                    glow_progress = min(
                        1.0, (current_time - transition.get('glow_start', current_time)) / 0.2)
                    glow_intensity = transition['glow_intensity'] + (
                        target_glow - transition['glow_intensity']) * glow_progress
                    transition['glow_intensity'] = glow_intensity

                    # 辉光效果基于强度
                    glow_effect = glow_intensity > 0.1

                    # 检测当前阶段 - 使用JASON阶段信息而不是时间阶段信息
                    jason_phase_info = self.get_jason_phase_info()
                    current_phase = jason_phase_info if jason_phase_info else self.get_current_phase(
                        timer_window, timer_window.elapsed_time)

                    team_damage = self.get_team_total_damage()
                    timer_window.draw_time_with_shadow(
                        time_str, color, glow_effect, current_phase, team_damage)

                    # 如果启用了明显提醒模式，同时更新屏幕顶部的倒计时
                    if (hasattr(timer_window, 'prominent_alert_enabled') and
                        timer_window.prominent_alert_enabled.get() and
                        hasattr(timer_window, 'prominent_window') and
                            timer_window.prominent_window):
                        try:
                            if timer_window.prominent_window.winfo_exists():
                                timer_window.prominent_window.draw_prominent_time(
                                    time_str, color, glow_effect, current_phase)
                        except (tk.TclError, AttributeError):
                            # prominent_window已被销毁或无效
                            timer_window.prominent_window = None

        # 每秒更新一次
        timer_window.after(
            1000, lambda: self.update_timer_display(timer_window))

    def interpolate_colors(self, color1, color2, progress):
        """在两个颜色之间进行插值"""
        try:
            # 解析颜色
            def hex_to_rgb(hex_color):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

            def rgb_to_hex(rgb):
                return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

            rgb1 = hex_to_rgb(color1)
            rgb2 = hex_to_rgb(color2)

            # 插值计算
            r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * progress)
            g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * progress)
            b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * progress)

            return rgb_to_hex((r, g, b))
        except:
            return color2  # 如果出错，返回目标颜色

    def get_current_phase(self, timer_window, elapsed_time):
        """获取当前阶段信息"""
        try:
            if not hasattr(timer_window, 'act_config') or not timer_window.act_config:
                return None

            config = timer_window.act_config
            phases = config.get('phases', [])

            if not phases:
                return None

            # 查找当前时间对应的阶段
            for phase in phases:
                start_time = phase.get('start_time', 0)
                end_time = phase.get('end_time', 999999)

                if start_time <= elapsed_time < end_time:
                    return phase

            # 如果没有找到匹配的阶段，返回最后一个阶段
            return phases[-1] if phases else None

        except Exception as e:
            print(f"获取当前阶段时出错: {e}")
            return None

    def check_damage_thresholds(self, timer_window, current_damage, damage_increase):
        """检查伤害阈值并触发相应机制"""
        try:
            # 检查是否有配置文件和伤害阈值设置
            if not (hasattr(timer_window, 'act_config') and timer_window.act_config):
                return

            damage_thresholds = timer_window.act_config.get(
                'damage_thresholds', [])
            if not damage_thresholds:
                return

            # 初始化已触发的阈值列表
            if not hasattr(timer_window, 'triggered_thresholds'):
                timer_window.triggered_thresholds = set()

            # 检查每个伤害阈值
            for threshold in damage_thresholds:
                threshold_id = threshold.get(
                    'id', threshold.get('damage_threshold', 0))

                # 如果已经触发过这个阈值，跳过
                if threshold_id in timer_window.triggered_thresholds:
                    continue

                # 检查是否满足触发条件
                trigger_condition = threshold.get('trigger_condition', 'total')
                damage_threshold = threshold.get('damage_threshold', 0)

                should_trigger = False
                if trigger_condition == 'total' and current_damage >= damage_threshold:
                    should_trigger = True
                elif trigger_condition == 'increase' and damage_increase >= damage_threshold:
                    should_trigger = True

                if should_trigger:
                    # 标记为已触发
                    timer_window.triggered_thresholds.add(threshold_id)

                    # 创建警报对象
                    alert = {
                        'message': threshold.get('message', f'伤害达到{damage_threshold}'),
                        'color': threshold.get('color', 'yellow'),
                        'sound': threshold.get('sound', True),
                        'type': 'damage_threshold'
                    }

                    # 触发警报
                    self.trigger_alert(timer_window, alert, alert_index=0)

                    # 记录事件
                    self.add_timer_event(timer_window,
                                         f"💥 伤害阈值触发: {alert['message']} (当前伤害: {current_damage})")

        except Exception as e:
            print(f"检查伤害阈值时出错: {e}")

    def get_current_damage_count(self):
        """获取当前总伤害计数，用于检测伤害变化"""
        try:
            # 方法1：尝试从current_data获取
            if hasattr(self, 'current_data') and self.current_data:
                data = self.current_data
                if data.get("code") == 0 and data.get("user"):
                    total_damage = 0

                    for uid, user_info in data["user"].items():
                        # 检查正确的数据结构
                        if "total_damage" in user_info and isinstance(user_info["total_damage"], dict):
                            damage = user_info["total_damage"].get("total", 0)
                            total_damage += damage

                    return total_damage

            # 方法2：如果没有数据，尝试从UI表格获取
            if hasattr(self, 'tree') and self.tree:
                try:
                    total_damage = 0
                    for item in self.tree.get_children():
                        values = self.tree.item(item, 'values')
                        if values and len(values) > 4:  # 确保有足够的列
                            try:
                                # 第5列是总伤害
                                damage = float(
                                    values[4]) if values[4] and values[4] != '-' else 0
                                total_damage += damage
                            except (ValueError, IndexError):
                                continue
                    return total_damage
                except Exception as e:
                    print(f"从UI表格获取伤害时出错: {e}")

            return 0
        except Exception as e:
            print(f"获取伤害计数时出错: {e}")
            return 0

    def start_tts_worker(self):
        """启动TTS工作线程"""
        if self.tts_worker_thread is None or not self.tts_worker_thread.is_alive():
            self.tts_worker_running = True
            self.tts_worker_thread = threading.Thread(
                target=self.tts_worker, daemon=True)
            self.tts_worker_thread.start()

    def tts_worker(self):
        """TTS工作线程，按优先级和顺序播放"""
        while self.tts_worker_running:
            try:
                # 从队列中获取下一个TTS任务，超时1秒
                priority, text = self.tts_queue.get(timeout=1)

                # 执行TTS播放
                try:
                    import subprocess
                    cmd = f'powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{text}\')"'
                    subprocess.run(cmd, shell=True, capture_output=True)
                except Exception as e:
                    print(f"TTS播报失败: {e}")

                # 标记任务完成
                self.tts_queue.task_done()

            except queue.Empty:
                # 队列为空，继续等待
                continue
            except Exception as e:
                print(f"TTS工作线程错误: {e}")

    def speak_text(self, text, priority=50, source_type="alert"):
        """使用TTS排队播放文本
        优先级: 数字越小优先级越高
        - 阶段切换: priority=10
        - JSON中靠前的警报: priority=20-40
        - 其他警报: priority=50+
        """
        try:
            # 根据来源类型调整优先级
            if source_type == "phase":
                priority = 10  # 阶段最高优先级
            elif source_type == "boss_rage":
                priority = 5   # Boss狂暴最高优先级

            # 将TTS任务加入优先级队列
            self.tts_queue.put((priority, text))

        except Exception as e:
            print(f"添加TTS任务失败: {e}")

    def create_prominent_alert_window(self, timer_window):
        """创建屏幕顶部的明显提醒窗口"""
        if timer_window.prominent_window is not None:
            try:
                timer_window.prominent_window.destroy()
            except:
                pass

        # 创建全屏顶部窗口
        prominent_window = tk.Toplevel()
        prominent_window.title("")
        prominent_window.overrideredirect(True)
        prominent_window.wm_attributes("-topmost", True)
        prominent_window.wm_attributes("-alpha", 0.0)  # 初始透明度为0，准备淡入

        # 获取屏幕尺寸
        screen_width = prominent_window.winfo_screenwidth()
        screen_height = prominent_window.winfo_screenheight()

        # 设置窗口大小和位置（屏幕顶部）
        window_height = 150  # 再增加高度以容纳更大的阶段描述区域
        prominent_window.geometry(f"{screen_width}x{window_height}+0+0")
        prominent_window.configure(bg=self.colors["bg_primary"])

        # 主容器 - 水平分割
        main_container = tk.Frame(
            prominent_window, bg=self.colors["bg_primary"])
        main_container.pack(fill="both", expand=True, padx=20, pady=5)

        # 左侧DPS条区域（占三分之一宽度）
        left_dps_frame = tk.Frame(main_container, bg=self.colors["bg_primary"])
        left_dps_frame.pack(side="left", fill="y", padx=(0, 10))
        left_dps_frame.configure(width=screen_width // 3)  # 三分之一宽度
        left_dps_frame.pack_propagate(False)

        # 右侧内容区域（占三分之二宽度）
        right_content_frame = tk.Frame(
            main_container, bg=self.colors["bg_primary"])
        right_content_frame.pack(side="right", fill="both", expand=True)

        # 创建DPS条区域
        self.create_prominent_dps_bars(left_dps_frame, timer_window)

        # 将main_container指向右侧区域，以便原有代码正常工作
        original_main_container = main_container
        main_container = right_content_frame

        # 添加右上角退出按钮
        def close_prominent_window():
            try:
                timer_window.prominent_window = None
                prominent_window.destroy()
            except:
                pass

        close_button = self.create_enhanced_button(
            prominent_window,
            "✕",
            close_prominent_window,
            self.colors["neon_red"],
            width=3,
            height=1
        )
        close_button.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # JASON阶段控制按钮组（在右上角）
        jason_control_frame = tk.Frame(
            prominent_window, bg=self.colors["bg_primary"])
        jason_control_frame.place(relx=1.0, rely=0.0, anchor="ne", x=-60, y=10)

        # 当前阶段显示
        timer_window.prominent_jason_label = tk.Label(
            jason_control_frame,
            text=f"阶段{self.current_jason_phase}",
            font=self.get_font(10, "bold"),
            bg=self.colors["bg_primary"],
            fg=self.get_jason_phase_info()["color"]
        )
        timer_window.prominent_jason_label.pack(side="right", padx=5)

        # 阶段控制按钮
        jason_btn_frame = tk.Frame(
            jason_control_frame, bg=self.colors["bg_primary"])
        jason_btn_frame.pack(side="right")

        # 推进阶段按钮
        advance_btn = self.create_enhanced_button(
            jason_btn_frame,
            "▶",
            self.advance_jason_phase,
            self.colors["neon_cyan"],
            width=2,
            height=1
        )
        advance_btn.pack(side="left", padx=1)

        # 重置按钮
        reset_btn = self.create_enhanced_button(
            jason_btn_frame,
            "⟲",
            self.reset_jason_rage_time,
            self.colors["neon_orange"],
            width=2,
            height=1
        )
        reset_btn.pack(side="left", padx=1)

        # 自动推进按钮
        auto_advance_btn = self.create_enhanced_button(
            jason_btn_frame,
            "⚡",
            self.toggle_jason_auto_advance,
            self.colors["neon_green"] if self.jason_auto_advance_enabled else self.colors["neon_red"],
            width=2,
            height=1
        )
        auto_advance_btn.pack(side="left", padx=1)
        timer_window.prominent_jason_auto_btn = auto_advance_btn

        # 阶段选择按钮 - 修复：使用动态配置
        # 检查当前配置是否有JASON阶段
        if self.current_act_config and 'jason_phases' in self.current_act_config:
            jason_phases_config = self.current_act_config['jason_phases']
            phase_definitions = []

            # 处理不同的配置格式
            if isinstance(jason_phases_config, list):
                # 新格式：直接的阶段数组
                phase_definitions = jason_phases_config
                print(f"[DEBUG] 使用新格式JASON配置，包含 {len(phase_definitions)} 个阶段")
            elif isinstance(jason_phases_config, dict) and 'phase_definitions' in jason_phases_config:
                # 旧格式：包含phase_definitions的对象
                phase_definitions = jason_phases_config['phase_definitions']
                print(f"[DEBUG] 使用旧格式JASON配置，包含 {len(phase_definitions)} 个阶段")
            else:
                print(f"[DEBUG] JASON配置格式不正确: {type(jason_phases_config)}")

            for i in range(1, 4):
                # 从动态配置中获取阶段信息
                phase_info = None
                for phase in phase_definitions:
                    if phase.get("id") == i:
                        phase_info = phase
                        break

                if phase_info:
                    btn = self.create_enhanced_button(
                        jason_btn_frame,
                        str(i),
                        lambda p=i: self.set_jason_phase(p),
                        phase_info.get("color", "#ffffff"),
                        width=2,
                        height=1
                    )
                    btn.pack(side="left", padx=1)
                    print(
                        f"[DEBUG] 创建阶段按钮 {i}: {phase_info.get('name', f'阶段{i}')}")
                else:
                    # 如果配置中没有定义该阶段，使用默认设置
                    default_colors = ["#00ff00", "#ffff00", "#ff0000"]
                    btn = self.create_enhanced_button(
                        jason_btn_frame,
                        str(i),
                        lambda p=i: self.set_jason_phase(p),
                        default_colors[i-1],
                        width=2,
                        height=1
                    )
                    btn.pack(side="left", padx=1)
                    print(f"[DEBUG] 创建默认阶段按钮 {i}")
        else:
            print(f"[DEBUG] 无JASON配置或配置中缺少jason_phases")
            print(
                f"[DEBUG] current_act_config: {bool(self.current_act_config)}")
            if self.current_act_config:
                print(f"[DEBUG] 配置键: {list(self.current_act_config.keys())}")

        # 添加明显模式JASON信息更新方法
        def update_prominent_jason_info():
            """更新明显模式的JASON阶段信息显示"""
            try:
                phase_info = self.get_jason_phase_info()
                timer_window.prominent_jason_label.config(
                    text=f"阶段{self.current_jason_phase}",
                    fg=phase_info["color"]
                )
                # 更新自动推进按钮状态
                if hasattr(timer_window, 'prominent_jason_auto_btn'):
                    btn_color = self.colors["neon_green"] if self.jason_auto_advance_enabled else self.colors["neon_red"]
                    timer_window.prominent_jason_auto_btn.config(fg=btn_color)
            except:
                pass

        timer_window.update_prominent_jason_info = update_prominent_jason_info

        # 创建内容区域的水平分割
        content_container = tk.Frame(
            main_container, bg=self.colors["bg_primary"])
        content_container.pack(fill="both", expand=True, pady=(0, 10))

        # 左侧时间显示区域（包含阶段数和倒计时）
        time_container = tk.Frame(
            content_container, bg=self.colors["bg_primary"])
        time_container.pack(side="left", fill="both",
                            expand=True, padx=(0, 10))

        # 右侧阶段描述专用幕布区域
        phase_desc_container = tk.Frame(
            content_container, bg=self.colors["bg_primary"])
        phase_desc_container.pack(side="right", fill="both")
        phase_desc_container.configure(width=screen_width // 4)  # 右侧1/4宽度
        phase_desc_container.pack_propagate(False)

        # 阶段描述画布
        phase_desc_canvas = tk.Canvas(
            phase_desc_container,
            bg=self.colors["bg_primary"],
            highlightthickness=0,
            bd=0
        )
        phase_desc_canvas.pack(fill="both", expand=True)

        # 时间显示Canvas（只包含阶段数和倒计时）
        time_canvas = tk.Canvas(
            time_container,
            height=80,  # 保持高度
            bg=self.colors["bg_primary"],
            highlightthickness=0,
            bd=0
        )
        time_canvas.pack(fill="x")

        def draw_prominent_time(time_text="00:00:00", text_color=None, glow_effect=False, phase_info=None):
            # 只绘制阶段数和倒计时，阶段描述在独立画布
            time_canvas.delete("all")
            font_tuple = self.get_font(36, "bold")  # 倒计时字体

            if text_color is None:
                text_color = self.colors["neon_cyan"]

            canvas_width = time_canvas.winfo_width()
            canvas_height = time_canvas.winfo_height()
            if canvas_width > 1 and canvas_height > 1:
                # 时间画布只包含阶段数和倒计时
                center_x = canvas_width // 2
                center_y = canvas_height // 2  # 画布中心Y坐标

                # 调整布局：阶段数保持左移，倒计时更靠右移动
                left_zone_x = canvas_width // 8      # 左边区域中心（阶段数，向左移）
                center_zone_x = canvas_width * 6 // 12   # 倒计时区域

                # 绘制阶段数信息
                if phase_info:
                    phase_name = phase_info.get('name', '')
                    phase_format = phase_info.get('format', {})

                    # 阶段数显示在左边 - 使用大号加粗字体
                    if phase_name:
                        # 修复：处理阶段名称中的换行符
                        phase_name = phase_name.replace(
                            '/n', '\n')  # 将 /n 转换为 \n

                        # 更大更醒目的阶段数字体
                        name_font_size = 20  # 增大字体
                        name_font = self.get_font(name_font_size, "bold")
                        name_color = self.colors["neon_purple"]

                        # 处理多行阶段名称
                        name_lines = phase_name.split('\n')
                        line_height = 25  # 行高，适配大字体
                        total_height = len(name_lines) * line_height
                        # 向下偏移5像素，让阶段数更好地Y轴居中
                        start_y = center_y - total_height * 1 // 3

                        for i, line in enumerate(name_lines):
                            current_y = start_y + i * line_height

                            # 多层阴影效果让阶段数更突出
                            shadow_layers = [
                                (3, 3, "#000000"),
                                (2, 2, "#111111"),
                                (1, 1, "#222222")
                            ]

                            for dx, dy, shadow_color in shadow_layers:
                                time_canvas.create_text(
                                    left_zone_x + dx, current_y + dy, text=line, font=name_font,
                                    fill=shadow_color, anchor="center"
                                )

                            # 边框效果
                            for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                                time_canvas.create_text(
                                    left_zone_x + dx, current_y + dy, text=line, font=name_font,
                                    fill="#444444", anchor="center"
                                )

                            # 主文字
                            time_canvas.create_text(
                                left_zone_x, current_y, text=line, font=name_font,
                                fill=name_color, anchor="center"
                            )

                # 倒计时显示在中央
                time_y = center_y

                # 如果启用辉光效果，绘制荧光辉光（更大的辉光适配更大字体）
                if glow_effect:
                    # 明显提醒窗口的辉光层更大更明显
                    glow_layers = [
                        (18, 0.15),  # 最外层
                        (12, 0.25),  # 中层
                        (8, 0.35),   # 内层
                        (6, 0.45),   # 最内层
                    ]

                    # 计算辉光颜色
                    def add_alpha_to_color(hex_color, alpha):
                        hex_color = hex_color.lstrip('#')
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        # 混合到背景色
                        bg_r, bg_g, bg_b = 30, 30, 40  # 背景色近似
                        final_r = int(r * alpha + bg_r * (1 - alpha))
                        final_g = int(g * alpha + bg_g * (1 - alpha))
                        final_b = int(b * alpha + bg_b * (1 - alpha))
                        return f"#{final_r:02x}{final_g:02x}{final_b:02x}"

                    # 绘制辉光层 - 使用正确的倒计时位置
                    for radius, alpha in glow_layers:
                        glow_color = add_alpha_to_color(text_color, alpha)
                        for angle in range(0, 360, 12):  # 每12度一个点，更密集
                            import math
                            dx = int(radius * math.cos(math.radians(angle)))
                            dy = int(radius * math.sin(math.radians(angle)))
                            time_canvas.create_text(
                                center_zone_x + dx, time_y + dy,
                                text=time_text, font=font_tuple,
                                fill=glow_color, anchor="center"
                            )

                # 绘制阴影
                shadow_layers = [
                    (6, 6, "#000000"),
                    (4, 4, "#111111"),
                    (2, 2, "#222222")
                ]

                for dx, dy, shadow_color in shadow_layers:
                    time_canvas.create_text(
                        center_zone_x + dx, time_y + dy,
                        text=time_text, font=font_tuple,
                        fill=shadow_color, anchor="center"
                    )

                # 绘制主文字
                time_canvas.create_text(
                    center_zone_x, time_y,
                    text=time_text, font=font_tuple,
                    fill=text_color, anchor="center"
                )

            # 绘制阶段描述到独立画布
            draw_phase_description(phase_info)

        def draw_phase_description(phase_info):
            """在独立画布上绘制阶段描述，Y轴居中"""
            phase_desc_canvas.delete("all")

            if not phase_info:
                return

            phase_desc = phase_info.get('description', '')
            if not phase_desc:
                return

            # 修复：处理两种换行符格式
            phase_desc = phase_desc.replace('/n', '\n')  # 将 /n 转换为 \n

            phase_format = phase_info.get('format', {})
            desc_font_size = phase_format.get('font_size', 14)  # 稍大的字体
            desc_color = self.colors.get(phase_format.get(
                'color', 'neon_cyan'), self.colors['neon_cyan'])
            desc_style = phase_format.get('font_style', 'italic')
            desc_font = self.get_font(desc_font_size, desc_style)

            canvas_width = phase_desc_canvas.winfo_width()
            canvas_height = phase_desc_canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                # 处理多行描述
                desc_lines = phase_desc.split('\n')
                line_height = desc_font_size + 5  # 增加行间距
                total_desc_height = len(desc_lines) * line_height - 5

                # Y轴居中计算
                canvas_center_y = canvas_height * 3 // 4
                desc_start_y = canvas_center_y - total_desc_height // 2

                # X轴稍微左移
                canvas_center_x = canvas_width * 2 // 5

                for i, desc_line in enumerate(desc_lines):
                    desc_y = desc_start_y + i * line_height

                    # 阴影效果
                    phase_desc_canvas.create_text(
                        canvas_center_x + 2, desc_y + 2, text=desc_line, font=desc_font,
                        fill="#000000", anchor="center"
                    )

                    # 主文字
                    phase_desc_canvas.create_text(
                        canvas_center_x, desc_y, text=desc_line, font=desc_font,
                        fill=desc_color, anchor="center"
                    )

        # 警告显示区域 - 只在左侧时间区域显示
        alert_container = tk.Frame(
            time_container, bg=self.colors["bg_primary"])
        # 警告区域占左侧时间区域的全宽
        alert_container.pack(fill="x", pady=(10, 0))

        alert_canvas = tk.Canvas(
            alert_container,
            height=40,
            bg=self.colors["bg_primary"],
            highlightthickness=0,
            bd=0
        )
        alert_canvas.pack(fill="x")

        prominent_window.draw_prominent_time = draw_prominent_time
        prominent_window.alert_canvas = alert_canvas
        prominent_window.alert_alpha = 0.0

        timer_window.prominent_window = prominent_window

        # 添加淡入效果
        self.fade_window_in(prominent_window, self.current_alpha, 0.2)

        # 启动DPS数据更新（在窗口创建完成后）
        prominent_window.after(
            1000, lambda: self.update_prominent_dps_data(timer_window))

        return prominent_window

    def fade_window_in(self, window, target_alpha=None, duration=0.2, callback=None):
        """窗口淡入效果"""
        if target_alpha is None:
            target_alpha = self.current_alpha

        steps = 10  # 动画步数
        step_time = int(duration * 1000 / steps)  # 每步间隔时间(毫秒)
        step_alpha = target_alpha / steps

        def animate_step(current_step):
            if current_step <= steps:
                alpha = current_step * step_alpha
                try:
                    window.wm_attributes("-alpha", alpha)
                    window.after(
                        step_time, lambda: animate_step(current_step + 1))
                except:
                    # 窗口可能已被销毁
                    pass
            elif callback:
                callback()

        # 开始时设置为透明
        try:
            window.wm_attributes("-alpha", 0.0)
            animate_step(0)
        except:
            pass

    def fade_window_out(self, window, duration=0.2, callback=None):
        """窗口淡出效果"""
        try:
            current_alpha = window.wm_attributes("-alpha")
        except:
            current_alpha = self.current_alpha

        steps = 10  # 动画步数
        step_time = int(duration * 1000 / steps)  # 每步间隔时间(毫秒)
        step_alpha = current_alpha / steps

        def animate_step(current_step):
            if current_step <= steps:
                alpha = current_alpha - (current_step * step_alpha)
                try:
                    window.wm_attributes("-alpha", max(0.0, alpha))
                    window.after(
                        step_time, lambda: animate_step(current_step + 1))
                except:
                    # 窗口可能已被销毁
                    pass
            elif callback:
                callback()

        animate_step(0)

    def show_alert_with_duration(self, timer_window, message, color, duration):
        """在明显提醒窗口中显示指定时长的警告"""
        if not timer_window.prominent_window:
            return

        alert_canvas = timer_window.prominent_window.alert_canvas
        if color is None:
            color = self.colors["neon_red"]

        def draw_alert_text(alpha=1.0):
            alert_canvas.delete("all")
            font_tuple = self.get_font(18, "bold")

            canvas_width = alert_canvas.winfo_width()
            if canvas_width > 1:
                center_x = canvas_width // 2
                center_y = 20

                # 计算透明度颜色
                def hex_to_rgba(hex_color, alpha):
                    hex_color = hex_color.lstrip('#')
                    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                    return f"#{int(rgb[0]*alpha):02x}{int(rgb[1]*alpha):02x}{int(rgb[2]*alpha):02x}"

                fade_color = hex_to_rgba(color, alpha)

                # 绘制警告文字
                alert_canvas.create_text(
                    center_x, center_y,
                    text=f"⚠️ {message}",
                    font=font_tuple,
                    fill=fade_color,
                    anchor="center"
                )

        # 自定义时长的淡入淡出动画
        total_frames = int(duration * 20)  # 20fps
        fade_in_frames = min(15, total_frames // 4)  # 淡入帧数
        fade_out_frames = min(15, total_frames // 4)  # 淡出帧数
        hold_frames = max(0, total_frames - fade_in_frames -
                          fade_out_frames)  # 持续显示帧数

        def fade_animation(step=0):
            if step >= total_frames:  # 动画结束
                alert_canvas.delete("all")
                return

            # 计算alpha值
            if step < fade_in_frames:  # 淡入
                alpha = step / fade_in_frames
            elif step < fade_in_frames + hold_frames:  # 持续显示
                alpha = 1.0
            else:  # 淡出
                fade_out_progress = (
                    step - fade_in_frames - hold_frames) / fade_out_frames
                alpha = 1.0 - fade_out_progress

            draw_alert_text(alpha)
            timer_window.prominent_window.after(
                50, lambda: fade_animation(step + 1))  # 50ms = 20fps

        fade_animation()

    def show_alert_fade(self, timer_window, message, color=None):
        """在明显提醒窗口中显示淡入淡出的警告（保留向后兼容）"""
        self.show_alert_with_duration(
            timer_window, message, color, 3.0)  # 默认3秒显示

    def refresh_act_configs(self):
        """刷新ACT配置文件列表"""
        try:
            import os
            import json

            # 查找当前运行目录下的所有.json文件
            config_files = []

            # 获取当前运行目录（而不是脚本目录）
            current_dir = os.getcwd()

            # 如果是打包环境，也检查可执行文件所在目录
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
                scan_dirs = [current_dir, exe_dir]
            else:
                scan_dirs = [current_dir, os.path.dirname(
                    os.path.abspath(__file__))]

            print(f"[DEBUG] 扫描配置文件目录: {scan_dirs}")

            # 内置的示例配置文件（只保留两个example）
            builtin_configs = [
                'act_raid_config.json',     # 统一配置示例
                'act_pvp_arena.json'        # PVP示例配置
            ]

            # 扫描所有目录
            for scan_dir in scan_dirs:
                if not os.path.exists(scan_dir):
                    continue

                print(f"[DEBUG] 正在扫描目录: {scan_dir}")

                for file in os.listdir(scan_dir):
                    if file.endswith('.json'):
                        try:
                            config_path = os.path.join(scan_dir, file)
                            with open(config_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)

                            # 检查是否是有效的战斗配置文件
                            if self._is_valid_config(data):
                                display_name = data.get('name', file[:-5])
                                file_key = file[:-5]  # 去掉.json扩展名

                                # 避免重复添加
                                if not any(existing_file == file_key for existing_file, _ in config_files):
                                    config_files.append(
                                        (file_key, display_name))
                                    print(
                                        f"[DEBUG] 找到配置文件: {file} -> {display_name}")

                        except Exception as e:
                            print(f"[DEBUG] 验证配置文件 {file} 失败: {e}")
                            continue

            # 更新下拉框选项
            if hasattr(self, 'config_combobox'):
                # 只显示配置名称，但保存完整信息
                display_values = [display_name for _,
                                  display_name in config_files]
                self.config_file_mapping = {
                    display_name: file_name for file_name, display_name in config_files}

                self.config_combobox['values'] = display_values
                if display_values:
                    self.config_combobox.set(display_values[0])

            print(f"[DEBUG] 找到 {len(config_files)} 个有效配置文件")
            for file_name, display_name in config_files:
                print(f"[DEBUG] - {display_name} ({file_name})")

        except Exception as e:
            print(f"[DEBUG] 刷新配置文件列表失败: {e}")
            import traceback
            traceback.print_exc()

    def _is_valid_config(self, data):
        """检查是否是有效的战斗配置文件"""
        if not isinstance(data, dict) or 'name' not in data:
            return False

        # 检查是否包含任何战斗配置相关的字段
        required_fields = ['alerts', 'jason_phases',
                           'phases', 'raid_templates', 'total_duration']
        return any(field in data for field in required_fields)

    def on_act_config_changed(self, event=None):
        """当ACT配置文件选择改变时的回调"""
        try:
            display_name = self.act_config_var.get()
            if not display_name or display_name == "无配置文件":
                return

            # 获取实际的文件名
            actual_config_name = display_name
            if hasattr(self, 'config_file_mapping') and display_name in self.config_file_mapping:
                actual_config_name = self.config_file_mapping[display_name]

            # 加载配置文件获取时长和阶段信息
            config = self.load_act_config(actual_config_name)
            if config and 'total_duration' in config:
                total_seconds = config['total_duration']

                # 如果ACT计时器窗口已经存在，更新显示
                if hasattr(self, 'act_timer_window') and self.act_timer_window:
                    try:
                        # 更新计时器的配置和时间显示
                        self.act_timer_window.config_name = actual_config_name
                        self.act_timer_window.remaining_time = total_seconds
                        self.act_timer_window.total_time = total_seconds
                        self.act_timer_window.current_config = config

                        # 立即更新显示
                        self.act_timer_window.update_display()
                        print(
                            f"已更新ACT计时器配置为: {actual_config_name}, 时长: {total_seconds}秒")
                    except Exception as e:
                        print(f"更新ACT计时器显示时出错: {e}")

        except Exception as e:
            print(f"处理配置文件改变时出错: {e}")

    def load_act_config(self, config_name):
        """加载ACT配置文件（从当前运行目录或通过映射查找）"""
        try:
            import os
            import json

            # 如果没有指定配置名称或为空，使用统一配置文件
            if not config_name or config_name.strip() == "":
                config_name = "act_raid_config"

            # 检查是否需要通过映射转换文件名
            actual_file_name = config_name
            if (hasattr(self, 'config_file_mapping') and
                    config_name in self.config_file_mapping):
                actual_file_name = self.config_file_mapping[config_name]
                print(f"[DEBUG] 通过映射转换: {config_name} -> {actual_file_name}")

            # 构建配置文件路径
            if not actual_file_name.endswith('.json'):
                actual_file_name += '.json'

            # 搜索目录列表
            search_dirs = []

            # 当前运行目录（优先）
            search_dirs.append(os.getcwd())

            # 如果是打包环境，添加可执行文件目录
            if getattr(sys, 'frozen', False):
                search_dirs.append(os.path.dirname(sys.executable))

            # 脚本目录（用于开发环境）
            search_dirs.append(os.path.dirname(os.path.abspath(__file__)))

            # 依次在各个目录中查找配置文件
            for search_dir in search_dirs:
                config_path = os.path.join(search_dir, actual_file_name)
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            print(f"[DEBUG] ACT配置文件加载成功: {config_path}")
                            return config
                    except Exception as e:
                        print(f"[DEBUG] 加载配置文件 {config_path} 时出错: {e}")
                        continue

            print(f"[DEBUG] 在所有搜索目录中都找不到配置文件: {actual_file_name}")
            print(f"[DEBUG] 搜索目录: {search_dirs}")

            # 如果加载失败，尝试使用主配置
            if config_name != "act_raid_config.json":
                return self.jason_config  # 使用已加载的主配置

            return None
        except Exception as e:
            print(f"[DEBUG] 加载配置文件时发生异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def process_act_alerts(self, timer_window, elapsed_time, remaining_time):
        """处理ACT配置中的提醒"""
        try:
            config = timer_window.act_config
            if not config or 'alerts' not in config:
                return

            current_time = int(elapsed_time)

            for i, alert in enumerate(config['alerts']):
                alert_id = f"{alert['type']}_{i}_{current_time}"
                alert_key = f"{alert['type']}_{i}"  # 用于跳过机制的键

                if alert['type'] == 'periodic':
                    # 周期性提醒
                    interval = alert['interval']
                    if current_time > 0 and current_time % interval == 0:
                        if alert_id not in timer_window.alerts_triggered:
                            # 检查跳过机制
                            if not self.should_skip_alert(timer_window, alert, alert_key):
                                self.trigger_alert(
                                    timer_window, alert, alert_index=i)
                            timer_window.alerts_triggered.add(alert_id)

                elif alert['type'] == 'timed':
                    # 定时提醒（剩余时间触发）
                    trigger_time = alert['trigger_time']
                    if remaining_time <= trigger_time and remaining_time > trigger_time - 1:
                        if alert_id not in timer_window.alerts_triggered:
                            # 检查跳过机制
                            if not self.should_skip_alert(timer_window, alert, alert_key):
                                self.trigger_alert(
                                    timer_window, alert, alert_index=i)
                            timer_window.alerts_triggered.add(alert_id)

                elif alert['type'] == 'countdown':
                    # 倒计时提醒
                    start_time = alert.get('start_time', 0)
                    interval = alert.get('interval', 10)
                    if remaining_time <= start_time and remaining_time > 0:
                        if (start_time - remaining_time) % interval == 0:
                            if alert_id not in timer_window.alerts_triggered:
                                # 检查跳过机制
                                if not self.should_skip_alert(timer_window, alert, alert_key):
                                    self.trigger_alert(
                                        timer_window, alert, remaining_time, alert_index=i)
                                timer_window.alerts_triggered.add(alert_id)

        except Exception as e:
            print(f"处理ACT提醒时出错: {e}")

    def parse_skip_pattern(self, pattern):
        """解析跳过模式，格式: 'X:Y' 表示每X次跳过Y次"""
        try:
            if ':' in pattern:
                parts = pattern.split(':')
                if len(parts) == 2:
                    trigger_count = int(parts[0])
                    skip_count = int(parts[1])
                    return trigger_count, skip_count
        except:
            pass
        return None, None

    def should_skip_alert(self, timer_window, alert, alert_key):
        """检查是否应该跳过这个警报"""
        # 检查全局跳过机制
        config = timer_window.act_config
        global_skip = config.get('skip_mechanism', {}) if config else {}

        # 检查单个警报的跳过机制
        alert_skip = alert.get('skip_mechanism', {})

        # 优先使用单个警报的跳过设置，否则使用全局设置
        skip_config = alert_skip if alert_skip.get('enabled') else global_skip

        if not skip_config.get('enabled'):
            return False

        pattern = skip_config.get('skip_pattern')
        if not pattern:
            return False

        trigger_count, skip_count = self.parse_skip_pattern(pattern)
        if trigger_count is None or skip_count is None:
            return False

        # 获取或初始化计数器
        if alert_key not in timer_window.skip_counters:
            timer_window.skip_counters[alert_key] = {
                'count': 0, 'skip_count': 0}

        counter = timer_window.skip_counters[alert_key]
        counter['count'] += 1

        # 检查是否应该跳过
        if counter['count'] % trigger_count == 0:
            counter['skip_count'] += 1
            if counter['skip_count'] <= skip_count:
                print(
                    f"[SKIP] 跳过警报: {alert.get('message', '')} (模式: {pattern}, 计数: {counter['count']}, 跳过: {counter['skip_count']})")
                return True
            else:
                # 重置跳过计数
                counter['skip_count'] = 0

        return False

    def trigger_alert(self, timer_window, alert, remaining_time=None, alert_index=0):
        """触发一个提醒"""
        try:
            message = alert['message']
            if remaining_time is not None and alert['type'] == 'countdown':
                message = f"{message}: {int(remaining_time)}秒"

            # 计算TTS优先级，基于在JSON中的位置
            # 位置越靠前，优先级越高（数字越小）
            tts_priority = 20 + alert_index  # 基础优先级20，每个位置+1

            # 获取颜色
            color_name = alert.get('color', 'cyan')
            color_map = {
                'red': self.colors["neon_red"],
                'yellow': self.colors["neon_yellow"],
                'green': self.colors["neon_green"],
                'cyan': self.colors["neon_cyan"],
                'blue': self.colors["neon_blue"],
                'purple': self.colors["neon_purple"],
                'pink': self.colors["neon_pink"],
                'orange': self.colors["neon_yellow"]  # 橙色用黄色代替
            }
            color = color_map.get(color_name, self.colors["neon_cyan"])

            # 添加到事件列表
            self.add_timer_event(timer_window, f"⚠️ {message}")

            # TTS播报
            if hasattr(timer_window, 'tts_enabled') and timer_window.tts_enabled.get():
                self.speak_text(message, priority=tts_priority)

            # 明显提醒模式 - 加入警告队列
            if hasattr(timer_window, 'prominent_alert_enabled') and timer_window.prominent_alert_enabled.get():
                if not timer_window.prominent_window:
                    self.create_prominent_alert_window(timer_window)

                # 初始化警告队列
                if not hasattr(timer_window, 'alert_queue'):
                    timer_window.alert_queue = []
                    timer_window.alert_queue_processing = False

                # 添加警告到队列
                timer_window.alert_queue.append({
                    'message': message,
                    'color': color,
                    'tts_priority': tts_priority
                })

                # 如果没有正在处理的警告，开始处理队列
                if not timer_window.alert_queue_processing:
                    self.process_alert_queue(timer_window)

            # 声音提醒通过TTS队列系统处理

        except Exception as e:
            print(f"触发提醒时出错: {e}")

    def process_alert_queue(self, timer_window):
        """处理警告队列"""
        if not hasattr(timer_window, 'alert_queue') or not timer_window.alert_queue:
            timer_window.alert_queue_processing = False
            return

        timer_window.alert_queue_processing = True

        # 取出队列中的第一个警告
        alert_data = timer_window.alert_queue.pop(0)
        message = alert_data['message']
        color = alert_data['color']

        # 估算TTS播放时间（基于文字长度，中文字符每个约0.5秒，英文单词约0.3秒）
        chinese_chars = len([c for c in message if ord(c) > 127])
        english_chars = len([c for c in message if ord(c) <= 127])
        estimated_duration = chinese_chars * 0.5 + english_chars * 0.15

        # 最小显示时间2秒，最大8秒
        display_duration = max(2.0, min(8.0, estimated_duration + 1.0))

        # 显示当前警告
        self.show_alert_with_duration(
            timer_window, message, color, display_duration)

        # 设置定时器处理下一个警告
        def process_next():
            if hasattr(timer_window, 'alert_queue') and timer_window.alert_queue:
                self.process_alert_queue(timer_window)
            else:
                timer_window.alert_queue_processing = False

        # 在当前警告显示完成后处理下一个
        timer_window.after(int(display_duration * 1000), process_next)

    def add_timer_event(self, timer_window, event_text):
        """添加事件到JASON库记录中"""
        if hasattr(timer_window, 'events_listbox'):
            timestamp = time.strftime("%H:%M:%S")
            event_entry = f"[{timestamp}] {event_text}"
            timer_window.events_listbox.insert(0, event_entry)

            # 保持列表最多显示20条记录
            if timer_window.events_listbox.size() > 20:
                timer_window.events_listbox.delete(20, tk.END)

    def init_global_hotkey(self):
        """初始化全局热键监听"""
        try:
            import keyboard
            # 注册HOME键的全局热键，使用on_press而不是add_hotkey以避免重复触发
            keyboard.on_press_key('home', self.on_home_key_press)
            print("[INFO] 全局HOME键监听已启动")
        except Exception as e:
            print(f"[WARNING] 全局热键初始化失败: {e}")

    def on_home_key_press(self, event):
        """HOME键按下事件处理"""
        # 防止重复触发
        if hasattr(self, '_last_home_press_time'):
            import time
            current_time = time.time()
            if current_time - self._last_home_press_time < 0.5:  # 0.5秒内的重复按键忽略
                return

        import time
        self._last_home_press_time = time.time()

        # 在主线程中执行窗口操作
        if hasattr(self, 'root'):
            self.root.after(0, self.toggle_all_windows)

    def toggle_all_windows(self):
        """切换所有窗口的显示/隐藏状态"""
        try:
            self.hidden_by_home = not self.hidden_by_home

            if self.hidden_by_home:
                # 隐藏所有窗口（不包括明显提醒窗口）
                print("[INFO] HOME键按下 - 隐藏所有窗口")

                # 隐藏主窗口（使用淡出效果）
                if hasattr(self, 'root') and self.root:
                    self.fade_window_out(
                        self.root, 0.2, lambda: self.root.withdraw())

                # 隐藏所有MINI窗口（使用淡出效果）
                if hasattr(self, 'mini_windows'):
                    for mini_info in self.mini_windows:
                        try:
                            mini_window = mini_info.get('window')
                            if mini_window and mini_window.winfo_exists():
                                self.fade_window_out(
                                    mini_window, 0.2, lambda w=mini_window: w.withdraw())
                        except:
                            pass

                # 隐藏所有Timer窗口（但不隐藏明显提醒窗口）（使用淡出效果）
                if hasattr(self, 'timer_windows'):
                    for timer_window in self.timer_windows:
                        try:
                            if timer_window.winfo_exists():
                                self.fade_window_out(
                                    timer_window, 0.2, lambda w=timer_window: w.withdraw())
                                # 不隐藏明显提醒窗口
                        except:
                            pass

            else:
                # 显示所有窗口
                print("[INFO] HOME键再次按下 - 显示所有窗口")

                # 显示主窗口（使用淡入效果）
                if hasattr(self, 'root') and self.root:
                    self.root.deiconify()
                    self.root.lift()  # 确保窗口被提升到前台
                    self.fade_window_in(self.root, self.current_alpha, 0.2)

                # 显示所有MINI窗口（使用淡入效果）
                if hasattr(self, 'mini_windows'):
                    for mini_info in self.mini_windows:
                        try:
                            mini_window = mini_info.get('window')
                            if mini_window and mini_window.winfo_exists():
                                mini_window.deiconify()
                                mini_window.lift()
                                self.fade_window_in(
                                    mini_window, mini_window.current_alpha, 0.2)
                        except:
                            pass

                # 显示所有Timer窗口（使用淡入效果）
                if hasattr(self, 'timer_windows'):
                    for timer_window in self.timer_windows:
                        try:
                            if timer_window.winfo_exists():
                                timer_window.deiconify()
                                timer_window.lift()
                                self.fade_window_in(
                                    timer_window, self.current_alpha, 0.2)
                                # 明显提醒窗口本来就没有被隐藏，所以不需要特别处理
                        except:
                            pass

        except Exception as e:
            print(f"[ERROR] 切换窗口显示状态时出错: {e}")

    def create_data_panel(self, parent):
        """创建数据显示面板"""
        outer_frame, data_frame = self.create_rounded_frame(
            parent,
            bg_color=self.colors["bg_accent"],
            border_color=self.colors["neon_green"],
            padding=3,
        )
        outer_frame.pack(fill="both", expand=True, pady=(0, 10))

        # 标题和UID设置按钮容器
        title_header = tk.Frame(data_frame, bg=self.colors["bg_accent"])
        title_header.pack(fill="x", pady=5)

        # 标题 - 使用阴影效果（向左对齐）
        data_title_canvas = self.create_shadow_text_canvas(
            title_header,
            text="[REAL_TIME_DATA_MATRIX]:",
            font_tuple=self.get_font(12, "bold"),
            fg_color=self.colors["neon_green"],
            bg_color=self.colors["bg_accent"],
            height=30,
            anchor="w"
        )
        data_title_canvas.pack(side="left", fill="x", expand=True)

        # UID设置按钮（右上角）
        uid_btn = self.create_enhanced_button(
            title_header,
            "⚙UID",
            self.show_uid_mapping_dialog,
            self.colors["neon_cyan"],
            width=6,
            height=1
        )
        uid_btn.pack(side="right", padx=(10, 0))

        # 表格容器
        table_container = tk.Frame(data_frame, bg=self.colors["bg_accent"])
        table_container.pack(fill="both", expand=True, padx=10, pady=5)

        # 创建Treeview样式
        style = ttk.Style()
        style.theme_use("clam")

        # 配置Treeview样式
        style.configure(
            "Cyberpunk.Treeview",
            background=self.colors["bg_primary"],
            foreground=self.colors["text_primary"],
            fieldbackground=self.colors["bg_primary"],
            borderwidth=1,
            relief="solid",
            rowheight=25,
            font=self.get_font(9),
        )  # 增加行高

        style.configure(
            "Cyberpunk.Treeview.Heading",
            background=self.colors["bg_secondary"],
            foreground=self.colors["neon_cyan"],
            borderwidth=1,
            relief="solid",
            font=self.get_font(9, "bold"),
        )

        # 选中行样式
        style.map(
            "Cyberpunk.Treeview",
            background=[("selected", self.colors["neon_cyan"])],
            foreground=[("selected", self.colors["bg_primary"])],
        )

        # 创建表格
        columns = ("用户名", "职业", "DPSR", "DPSM",
                   "DPSA", "总伤害", "暴击率", "HITS")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            height=12,
            style="Cyberpunk.Treeview",
        )

        column_widths = {
            "用户名": 80,
            "职业": 70,
            "DPSR": 80,
            "DPSM": 80,
            "DPSA": 100,
            "总伤害": 80,
            "暴击率": 80,
            "HITS": 90,
        }

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col,
                             width=column_widths.get(col, 80),
                             anchor=tk.CENTER)

        # 滚动条
        scrollbar = ttk.Scrollbar(table_container,
                                  orient=tk.VERTICAL,
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_detail_panel(self, parent):
        """创建详细信息面板"""
        outer_frame, detail_frame = self.create_rounded_frame(
            parent,
            bg_color=self.colors["bg_accent"],
            border_color=self.colors["neon_purple"],
            padding=3,
        )
        # 设置详细信息面板的固定高度（单行显示）
        outer_frame.configure(height=60)  # 减小高度，确保状态栏可见
        outer_frame.pack(fill="x", pady=(0, 10))
        outer_frame.pack_propagate(False)  # 防止子控件改变大小

        # 标题 - 使用阴影效果
        detail_title_canvas = self.create_shadow_text_canvas(
            detail_frame,
            text="[DETAILED_STATISTICS]:",
            font_tuple=self.get_font(12, "bold"),
            fg_color=self.colors["neon_purple"],
            bg_color=self.colors["bg_accent"],
            height=30
        )
        detail_title_canvas.pack(pady=5, fill="x")

        # 详细信息容器
        text_container = tk.Frame(detail_frame, bg=self.colors["bg_accent"])
        text_container.pack(fill="x", padx=10, pady=5)

        # 详细信息文本框
        self.detail_text = tk.Text(
            text_container,
            height=1,  # 改为单行高度
            wrap=tk.WORD,
            bg=self.colors["bg_primary"],
            fg=self.colors["text_primary"],
            insertbackground=self.colors["neon_cyan"],
            selectbackground=self.colors["neon_cyan"],
            selectforeground=self.colors["bg_primary"],
            font=self.get_font(9),
            bd=1,
            relief="solid",
        )

        # 移除滚动条以避免兼容性问题
        # detail_scroll = ttk.Scrollbar(text_container,
        #                              orient=tk.VERTICAL,
        #                              command=self.detail_text.yview)
        # self.detail_text.configure(yscrollcommand=detail_scroll.set)

        self.detail_text.pack(fill="x", expand=True, padx=(0, 0))
        # detail_scroll.pack(side="right", fill="y")

    def create_status_bar(self, parent):
        """创建状态栏"""
        outer_frame, status_frame = self.create_rounded_frame(
            parent,
            bg_color=self.colors["bg_secondary"],
            border_color=self.colors["border_light"],
            padding=2,
        )
        # 设置状态栏固定高度
        outer_frame.configure(height=40)
        outer_frame.pack(fill="x")
        outer_frame.pack_propagate(False)

        # 状态栏文本
        self.status_bar = tk.Label(
            status_frame,
            text="[SYSTEM_READY]",
            font=self.get_font(9),
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_accent"],
            anchor=tk.W,
        )
        self.status_bar.pack(fill="x", padx=5, pady=2)

    def start_monitoring(self):
        """开始监控"""
        if not self.running:
            self.running = True
            self.test_mode = False
            self.direct_mode = False
            self.status_label.config(text="● CONNECTING...",
                                     fg=self.colors["warning_yellow"])
            self.update_status("[PROCESS] 启动伤害数据监控...")

            # 启动更新线程
            self.update_thread = threading.Thread(target=self.update_loop,
                                                  daemon=True)
            self.update_thread.start()

    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        self.test_mode = False
        self.direct_mode = False
        self.status_label.config(text="● DISCONNECTED",
                                 fg=self.colors["error_red"])
        self.update_status("[SYSTEM] 监控已停止")

    def start_direct_mode(self):
        """启动直接模式 - 从数据源直接获取数据"""
        if not self.data_source:
            self.update_status("[DIRECT_ERROR] 未设置数据源，请先启动主程序")
            return

        if not self.running:
            self.running = True
            self.test_mode = False
            self.direct_mode = True
            self.status_label.config(text="● DIRECT_MODE",
                                     fg=self.colors["neon_orange"])
            self.update_status("[DIRECT_MODE] 启动直接数据模式...")

            # 启动直接更新线程
            self.update_thread = threading.Thread(
                target=self.direct_update_loop, daemon=True)
            self.update_thread.start()

    def direct_update_loop(self):
        """直接模式数据更新循环"""
        while self.running and self.direct_mode:
            try:
                # 从数据源直接获取数据
                data = self.get_direct_data()

                if data:
                    # 更新UI（在主线程中）
                    self.root.after(0, self.update_data_display, data)

                    # 更新状态
                    self.root.after(
                        0,
                        lambda: self.status_label.config(
                            text="● DIRECT_ACTIVE",
                            fg=self.colors["neon_orange"]),
                    )
                else:
                    # 没有数据时显示等待状态
                    self.root.after(
                        0,
                        lambda: self.status_label.config(
                            text="● DIRECT_WAITING",
                            fg=self.colors["warning_yellow"]),
                    )

            except Exception as e:
                error_msg = f"[DIRECT_ERROR] 直接模式错误: {e}"
                self.root.after(0,
                                lambda msg=error_msg: self.update_status(msg))

            # 等待刷新间隔
            try:
                interval = int(self.refresh_var.get()) / 100.0
            except:
                interval = 1.0

            time.sleep(interval)

    def start_test_mode(self):
        """启动测试模式 - 模拟数据显示"""
        if not self.running:
            self.running = True
            self.test_mode = True
            self.direct_mode = False
            self.test_counter = 0
            self.status_label.config(text="● TEST_MODE",
                                     fg=self.colors["neon_purple"])
            self.update_status("[TEST_MODE] 启动测试模式，模拟战斗数据...")

            # 启动测试更新线程
            self.update_thread = threading.Thread(target=self.test_update_loop,
                                                  daemon=True)
            self.update_thread.start()

    def test_update_loop(self):
        """测试模式数据更新循环"""
        import random

        while self.running and self.test_mode:
            try:
                self.test_counter += 1

                # 生成模拟数据
                test_data = self.generate_test_data()

                # 更新UI（在主线程中）
                self.root.after(0, self.update_data_display, test_data)

                # 更新状态
                self.root.after(
                    0,
                    lambda: self.status_label.config(text="● TEST_MODE_ACTIVE",
                                                     fg=self.colors[
                                                         "neon_purple"]),
                )

            except Exception as e:
                error_msg = f"[TEST_ERROR] 测试模式错误: {e}"
                self.root.after(0,
                                lambda msg=error_msg: self.update_status(msg))

            # 等待刷新间隔
            try:
                interval = int(self.refresh_var.get()) / 100.0
            except:
                interval = 1.0

            time.sleep(interval)

    def generate_test_data(self):
        """生成测试数据"""
        import random

        # 模拟多个玩家数据
        players = ["Player_001", "Player_002", "Player_003", "TestUser_Alpha"]

        user_data = {}

        for i, player in enumerate(players):
            if random.random() < 0.8:  # 80%概率显示玩家
                base_damage = 50000 + (i * 20000) + random.randint(
                    -10000, 30000)
                total_attacks = 100 + (self.test_counter * 5) + random.randint(
                    0, 20)
                crit_attacks = int(total_attacks * random.uniform(0.15, 0.35))
                lucky_attacks = int(total_attacks * random.uniform(0.05, 0.15))
                normal_attacks = total_attacks - crit_attacks - lucky_attacks

                normal_damage = normal_attacks * random.randint(8000, 12000)
                crit_damage = crit_attacks * random.randint(15000, 25000)
                lucky_damage = lucky_attacks * random.randint(20000, 35000)
                crit_lucky_damage = int(
                    (crit_damage + lucky_damage) * random.uniform(0.1, 0.2))

                total_damage = (normal_damage + crit_damage + lucky_damage +
                                crit_lucky_damage)

                realtime_dps = random.randint(int(base_damage * 0.8),
                                              int(base_damage * 1.2))
                max_dps = int(realtime_dps * random.uniform(1.2, 1.8))
                total_dps = int(total_damage / max(1, self.test_counter))

                user_data[player] = {
                    "realtime_dps": realtime_dps,
                    "realtime_dps_max": max_dps,
                    "total_dps": total_dps,
                    "total_damage": {
                        "total": total_damage,
                        "normal": normal_damage,
                        "critical": crit_damage,
                        "lucky": lucky_damage,
                        "crit_lucky": crit_lucky_damage,
                        "hpLessen": int(total_damage * random.uniform(0.05, 0.15)),
                    },
                    "total_count": {
                        "total": total_attacks,
                        "normal": normal_attacks,
                        "critical": crit_attacks,
                        "lucky": lucky_attacks,
                    },
                    "total_healing": {
                        "total": int(total_damage * random.uniform(0.3, 0.8)),
                        "normal": int(normal_damage * random.uniform(0.3, 0.8)),
                        "critical": int(crit_damage * random.uniform(0.3, 0.8)),
                        "lucky": int(lucky_damage * random.uniform(0.3, 0.8)),
                        "crit_lucky": int(crit_lucky_damage * random.uniform(0.3, 0.8)),
                        "hpLessen": 0,
                    },
                    "realtime_hps": int(realtime_dps * random.uniform(0.2, 0.6)),
                    "realtime_hps_max": int(max_dps * random.uniform(0.2, 0.6)),
                    "total_hps": int(total_dps * random.uniform(0.2, 0.6)),
                    "taken_damage": int(total_damage * random.uniform(0.1, 0.3)),
                    "profession": random.choice(["输出", "治疗", "坦克", "辅助", "未知"]),
                }

        return {
            "code": 0,
            "user": user_data,
            "message": "Test data generated successfully",
        }

    def update_loop(self):
        """数据更新循环"""
        while (self.running and not self.test_mode
               and not self.direct_mode):  # 添加direct_mode检查
            try:
                # 获取数据
                response = requests.get(self.api_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()

                    # 更新UI（在主线程中）
                    self.root.after(0, self.update_data_display, data)

                    # 更新状态
                    self.root.after(
                        0,
                        lambda: self.status_label.config(text="● CONNECTED",
                                                         fg=self.colors[
                                                             "success_green"]),
                    )
                else:
                    self.root.after(
                        0,
                        lambda: self.status_label.config(
                            text="● CONNECTION_FAILED",
                            fg=self.colors["error_red"]),
                    )

            except requests.RequestException as e:
                error_msg = f"[ERROR] 连接错误: {e}"
                self.root.after(
                    0,
                    lambda: self.status_label.config(text="● CONNECTION_ERROR",
                                                     fg=self.colors["error_red"
                                                                    ]),
                )
                self.root.after(0,
                                lambda msg=error_msg: self.update_status(msg))
            except Exception as e:
                error_msg = f"[ERROR] 更新错误: {e}"
                self.root.after(0,
                                lambda msg=error_msg: self.update_status(msg))

            # 等待刷新间隔
            try:
                interval = int(self.refresh_var.get()) / 100.0
            except:
                interval = 1.0

            time.sleep(interval)

    def update_data_display(self, data):
        """更新数据显示 - Cyberpunk风格，优化减少闪烁"""
        try:
            # 存储当前数据
            self.current_data = data

            if data.get("code") == 0 and data.get("user"):
                user_data = data["user"]

                # 获取当前表格中的项目
                current_items = self.tree.get_children()
                current_data = {}
                for item in current_items:
                    values = self.tree.item(item, 'values')
                    if values:
                        current_data[values[0]] = item  # 用户名作为键

                # 检查是否需要完全重建表格
                new_users = set(self.get_display_name(uid)
                                for uid in user_data.keys())
                current_users = set(current_data.keys())
                need_rebuild = (len(new_users) != len(current_users) or
                                new_users != current_users)

                if need_rebuild:
                    # 只在用户列表变化时才清空重建
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    current_data = {}

                detail_info = []
                detail_info.append("▓▓▓ DETAILED_COMBAT_ANALYSIS ▓▓▓\n")

                for uid, user_info in user_data.items():
                    # 计算暴击率
                    total_attacks = user_info.get(
                        "total_count", {}).get("total", 0)
                    crit_attacks = user_info.get(
                        "total_count", {}).get("critical", 0)
                    crit_rate = ((crit_attacks / total_attacks *
                                  100) if total_attacks > 0 else 0.0)

                    profession = user_info.get("profession", "未知")

                    # 获取各种数据
                    realtime_dps = user_info.get("realtime_dps", 0)
                    realtime_dps_max = user_info.get("realtime_dps_max", 0)
                    total_dps = user_info.get("total_dps", 0)
                    total_damage = user_info.get(
                        "total_damage", {}).get("total", 0)
                    realtime_hps = user_info.get("realtime_hps", 0)
                    total_healing = user_info.get(
                        "total_healing", {}).get("total", 0)
                    taken_damage = user_info.get("taken_damage", 0)

                    # 使用映射的用户名
                    display_name = self.get_display_name(uid)
                    values = (
                        display_name,
                        profession,
                        f"{realtime_dps:,.0f}",
                        f"{realtime_dps_max:,.0f}",
                        f"{total_dps:,.0f}",
                        f"{total_damage:,}",
                        f"{crit_rate:.1f}%",
                        f"{total_attacks:,}",
                        f"{realtime_hps:,.0f}",
                        f"{total_healing:,}",
                        f"{taken_damage:,}",
                    )

                    # 更新或插入数据（减少闪烁）
                    if display_name in current_data:
                        # 更新现有项目
                        item = current_data[display_name]
                        self.tree.item(item, values=values)
                    else:
                        # 插入新项目
                        self.tree.insert("", tk.END, values=values)

                    # 详细信息 - Cyberpunk风格
                    display_name = self.get_display_name(uid)  # 使用映射的用户名
                    detail_info.append(f"[PLAYER_NAME]: {display_name}")
                    if display_name != uid:  # 如果有映射，也显示原始UID
                        detail_info.append(f"├─ ORIGINAL_UID: {uid}")
                    detail_info.append(f"├─ PROFESSION: {profession}")
                    detail_info.append(
                        f"├─ TOTAL_DAMAGE: {user_info.get('total_damage', {}).get('total', 0):,}"
                    )
                    detail_info.append(
                        f"├─ NORMAL_DAMAGE: {user_info.get('total_damage', {}).get('normal', 0):,}"
                    )
                    detail_info.append(
                        f"├─ CRITICAL_DAMAGE: {user_info.get('total_damage', {}).get('critical', 0):,}"
                    )
                    detail_info.append(
                        f"├─ LUCKY_DAMAGE: {user_info.get('total_damage', {}).get('lucky', 0):,}"
                    )
                    detail_info.append(
                        f"├─ CRIT+LUCKY: {user_info.get('total_damage', {}).get('crit_lucky', 0):,}"
                    )
                    detail_info.append(
                        f"├─ HP_LESSEN: {user_info.get('total_damage', {}).get('hpLessen', 0):,}"
                    )
                    detail_info.append(
                        f"├─ TOTAL_HEALING: {user_info.get('total_healing', {}).get('total', 0):,}"
                    )
                    detail_info.append(
                        f"├─ REALTIME_HPS: {user_info.get('realtime_hps', 0):,.0f}"
                    )
                    detail_info.append(
                        f"├─ MAX_HPS: {user_info.get('realtime_hps_max', 0):,.0f}"
                    )
                    detail_info.append(
                        f"└─ TAKEN_DAMAGE: {user_info.get('taken_damage', 0):,}"
                    )
                    detail_info.append("")

                # 更新详细信息
                self.detail_text.delete(1.0, tk.END)
                self.detail_text.insert(1.0, "\n".join(detail_info))

                # 更新状态栏
                total_users = len(user_data)
                current_time = datetime.now().strftime("%H:%M:%S")
                self.update_status(
                    f"[UPDATE] {current_time} | ACTIVE_PLAYERS: {total_users}")

                # 计算全团总伤害
                total_damage_sum = 0
                for uid, user_info in user_data.items():
                    user_total_damage = user_info.get(
                        "total_damage", {}).get("total", 0)
                    total_damage_sum += user_total_damage

                # 更新全团总伤害
                self.total_damage = total_damage_sum

                # 检查JASON阶段自动推进（包含伤害和时间推进）
                self.check_jason_auto_advance()

            else:
                # 无数据 - Cyberpunk风格
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.detail_text.delete(1.0, tk.END)
                no_data_msg = """▓▓▓ NO_COMBAT_DATA_DETECTED ▓▓▓

[SYSTEM_CHECK_LIST]:
├─ Star_Resonance_Damage_Counter: VERIFY_STATUS
├─ Game_Process: VERIFY_RUNNING
├─ Combat_Activity: VERIFY_ACTIVE
└─ Network_Capture: VERIFY_PACKETS

[WAITING_FOR_DATA_STREAM]..."""
                self.detail_text.insert(1.0, no_data_msg)
                self.update_status("[STANDBY] 等待战斗数据...")

        except Exception as e:
            self.update_status(f"[ERROR] 数据显示错误: {e}")

    def clear_data(self):
        """清除数据 - Cyberpunk风格"""
        try:
            if self.direct_mode:
                # 直接模式：清除数据源中的数据
                if self.clear_direct_data():
                    self.update_status("[SUCCESS] 直接模式数据已清除")
                    self.show_messagebox(
                        "直接模式数据已清除",
                        title="SUCCESS",
                        color=self.colors["success_green"],
                    )
                    # 清空显示
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    self.detail_text.delete(1.0, tk.END)
                    self.detail_text.insert(
                        1.0, "▓▓▓ DATA_CLEARED ▓▓▓\n\n[DIRECT_MODE] 所有统计数据已重置")
                else:
                    self.update_status("[ERROR] 直接模式清除数据失败")
                    self.show_messagebox(
                        "直接模式清除数据失败",
                        title="ERROR",
                        color=self.colors["error_red"],
                    )
            else:
                # HTTP模式：通过API清除数据
                response = requests.get(self.clear_url, timeout=5)
                if response.status_code == 200:
                    self.update_status("[SUCCESS] 数据已清除")
                    self.show_messagebox(
                        "数据已清除",
                        title="SUCCESS",
                        color=self.colors["success_green"],
                    )
                    # 清空显示
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    self.detail_text.delete(1.0, tk.END)
                    self.detail_text.insert(
                        1.0, "▓▓▓ DATA_CLEARED ▓▓▓\n\n[SYSTEM] 所有统计数据已重置")
                else:
                    self.update_status("[ERROR] 清除数据失败")
                    self.show_messagebox("清除数据失败",
                                         title="ERROR",
                                         color=self.colors["error_red"])
        except Exception as e:
            self.update_status(f"[ERROR] 清除数据错误: {e}")
            self.show_messagebox(f"清除数据错误: {e}",
                                 title="ERROR",
                                 color=self.colors["error_red"])

    def on_refresh_changed(self, event=None):
        """刷新间隔改变"""
        interval = self.refresh_var.get()
        self.update_status(f"[CONFIG] 刷新间隔设置为 {interval}ms")

    def update_status(self, message):
        """更新状态栏 - Cyberpunk风格"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_msg = f"[{timestamp}] {message}"
        self.status_bar.config(text=status_msg)

    def on_closing(self):
        """关闭窗口时的处理"""
        self.rgb_animation_running = False
        self.running = False

        # 停止全局热键监听
        try:
            import keyboard
            keyboard.unhook_all()
            print("[INFO] 全局热键监听已停止")
        except Exception as e:
            print(f"[WARNING] 停止全局热键监听失败: {e}")

        # 停止UID映射监控
        self.stop_uid_mapping_monitor()

        # 清理所有Timer窗口和相关的明显提醒窗口
        if hasattr(self, 'timer_windows'):
            for timer_window in self.timer_windows[:]:  # 使用副本避免修改时迭代
                try:
                    # 清理明显提醒窗口
                    if hasattr(timer_window, 'prominent_window') and timer_window.prominent_window:
                        timer_window.prominent_window.destroy()
                    timer_window.destroy()
                except:
                    pass
            self.timer_windows.clear()

        # 清理所有MINI窗口
        if hasattr(self, 'mini_windows'):
            for mini_info in self.mini_windows[:]:  # 使用副本避免修改时迭代
                try:
                    mini_window = mini_info.get('window')
                    if mini_window and mini_window.winfo_exists():
                        mini_window.destroy()
                except:
                    pass
            self.mini_windows.clear()

        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=1)
        self.root.destroy()

    def run(self):
        """运行UI"""
        # 显示欢迎信息
        self.update_status("[SYSTEM] ACT伤害统计面板已启动")

        # 延迟启动耗时功能，避免初始化卡顿
        self.root.after(2000, self._delayed_start_services)

        if self.data_source:
            # 如果已设置数据源，自动启动直接模式
            self.root.after(1000, self._auto_start_direct_mode)
        else:
            # 没有数据源时提示其他选项
            self.root.after(
                1000,
                lambda: self.update_status("[INFO] 点击TEST查看演示 | DIRECT使用直接模式"),
            )

        self.root.mainloop()

    def _delayed_start_services(self):
        """延迟启动服务，避免初始化时卡顿"""
        if not self._delayed_start_scheduled:
            self._delayed_start_scheduled = True
            try:
                # 启动自动UID映射检测
                if self.auto_uid_mapping:
                    self.start_uid_mapping_monitor()
                self.update_status("[SYSTEM] 后台服务已启动")
            except Exception as e:
                self.update_status(f"[WARNING] 后台服务启动失败: {e}")

    def create_prominent_dps_bars(self, parent_frame, timer_window):
        """创建明显模式的DPS条区域 - 左侧1/3，紧凑的DPS条"""
        # DPS容器 - 只占左侧1/3宽度，增加宽度
        dps_main_container = tk.Frame(
            parent_frame, bg=self.colors["bg_primary"], width=600)
        dps_main_container.pack(side="left", fill="y", padx=5, pady=5)
        dps_main_container.pack_propagate(False)  # 保持固定宽度

        # 上半部分 - 三列布局，固定高度比例
        top_container = tk.Frame(
            dps_main_container, bg=self.colors["bg_primary"], height=200)
        top_container.pack(fill="x", pady=(0, 2))
        top_container.pack_propagate(False)

        # 下半部分 - 三列布局，填充剩余空间
        bottom_container = tk.Frame(
            dps_main_container, bg=self.colors["bg_primary"])
        bottom_container.pack(fill="both", expand=True, pady=(2, 0))

        # 上半部分分成三列：个人DPS + 1-2名 + 3-4名
        top_container.grid_columnconfigure(0, weight=41)  # 个人DPS区域稍微大一点点
        top_container.grid_columnconfigure(1, weight=40)
        top_container.grid_columnconfigure(2, weight=40)
        top_container.grid_rowconfigure(0, weight=1)

        # 左上：个人DPS区域
        self_dps_frame = tk.Frame(top_container, bg=self.colors["bg_secondary"],
                                  relief="solid", bd=1)
        self_dps_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 2))

        # 中上：1-2名区域
        top_center_frame = tk.Frame(top_container, bg=self.colors["bg_accent"],
                                    relief="solid", bd=1)
        top_center_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 2))

        # 右上：3-4名区域（原来的1-2名位置）
        top_right_frame = tk.Frame(top_container, bg=self.colors["bg_accent"],
                                   relief="solid", bd=1)
        top_right_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 0))

        # 下半部分分成三列：5-6名 + 7-8名 + 9-10名
        bottom_container.grid_columnconfigure(0, weight=1)
        bottom_container.grid_columnconfigure(1, weight=1)
        bottom_container.grid_columnconfigure(2, weight=1)
        bottom_container.grid_rowconfigure(0, weight=1)

        # 左下：5-6名区域（原来的5-6名位置）
        bottom_left_frame = tk.Frame(bottom_container, bg=self.colors["bg_accent"],
                                     relief="solid", bd=1)
        bottom_left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 2))

        # 中下：7-8名区域（原来的右下位置）
        bottom_center_frame = tk.Frame(bottom_container, bg=self.colors["bg_accent"],
                                       relief="solid", bd=1)
        bottom_center_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 2))

        # 右下：9-10名区域（新增）
        bottom_right_frame = tk.Frame(bottom_container, bg=self.colors["bg_accent"],
                                      relief="solid", bd=1)
        bottom_right_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 0))

        # 存储引用
        timer_window.prominent_self_dps_frame = self_dps_frame
        timer_window.prominent_top_center_frame = top_center_frame      # 1-2名
        timer_window.prominent_top_right_frame = top_right_frame        # 3-4名
        timer_window.prominent_bottom_left_frame = bottom_left_frame    # 5-6名
        timer_window.prominent_bottom_center_frame = bottom_center_frame  # 7-8名
        timer_window.prominent_bottom_right_frame = bottom_right_frame  # 9-10名

    def update_prominent_dps_data(self, timer_window):
        """更新明显模式的DPS数据显示 - 包含最高伤害计算"""
        if not hasattr(timer_window, 'prominent_window') or not timer_window.prominent_window:
            print("[DEBUG] prominent_window不存在，停止更新")
            return

        if not timer_window.prominent_window.winfo_exists():
            print("[DEBUG] prominent_window已销毁，停止更新")
            return

        try:
            print("[DEBUG] 开始更新DPS数据...")

            # 获取实时数据
            data = None
            if not self.direct_mode:
                try:
                    import requests
                    response = requests.get(self.api_url, timeout=1)
                    if response.status_code == 200:
                        data = response.json()
                        print(
                            f"[DEBUG] 从API获取数据成功，用户数: {len(data.get('user', {}))}")
                except Exception as e:
                    print(f"[DEBUG] API获取失败: {e}")

            if not data:
                data = (self.current_data if self.current_data else
                        self.get_direct_data() or {"user": {}})
                print(f"[DEBUG] 使用备用数据，用户数: {len(data.get('user', {}))}")

            user_data = data.get("user", {})
            sorted_users = sorted(
                user_data.items(),
                key=lambda x: x[1].get("total_damage", {}).get(
                    "total", 0) if x[1] else 0,
                reverse=True,
            )

            # 计算最高伤害值（作为进度条的100%基准）
            max_damage = 0
            if sorted_users:
                max_damage = sorted_users[0][1].get(
                    "total_damage", {}).get("total", 0)

            print(
                f"[DEBUG] 排序后用户数: {len(sorted_users)}, 最高伤害: {max_damage:,.0f}")

            # 更新自己的DPS条（传递最高伤害）
            self.update_prominent_self_dps(
                timer_window, sorted_users, max_damage)

            # 更新前6名其他人DPS条（传递最高伤害）
            self.update_prominent_top_dps(
                timer_window, sorted_users, max_damage)

        except Exception as e:
            print(f"[DEBUG] 更新明显模式DPS数据失败: {e}")
            import traceback
            traceback.print_exc()

        # 每2秒更新一次
        if hasattr(timer_window, 'prominent_window') and timer_window.prominent_window:
            timer_window.prominent_window.after(
                2000, lambda: self.update_prominent_dps_data(timer_window))

    def update_prominent_self_dps(self, timer_window, sorted_users, max_damage=None):
        """更新个人DPS条显示 - 紧凑DPS条格式"""
        if not hasattr(timer_window, 'prominent_self_dps_frame'):
            print("[DEBUG] prominent_self_dps_frame不存在")
            return

        container = timer_window.prominent_self_dps_frame

        # 清除旧的显示
        for widget in container.winfo_children():
            widget.destroy()

        # 查找自己的数据
        self_uid = self.personal_uid
        self_data = None
        self_rank = 0

        if self_uid and sorted_users:
            for rank, (uid, info) in enumerate(sorted_users, 1):
                if uid == self_uid:
                    self_data = info
                    self_rank = rank
                    break

        # 如果没有找到个人UID，使用第一名作为示例
        if not self_data and sorted_users:
            self_uid, self_data = sorted_users[0]
            self_rank = 1

        if self_data:
            display_name = self.get_display_name(self_uid)
            dps = self_data.get("total_dps", 0)
            total_damage = self_data.get("total_damage", {}).get("total", 0)
            total_healing = self_data.get("total_healing", {}).get("total", 0)

            # 创建个人DPS条
            self.create_miniui_dps_bar(
                container, display_name, dps, total_damage, self_rank,
                is_self=True, compact=False, max_damage=max_damage)

            # 添加总治疗和排名信息条
            info_frame = tk.Frame(
                container, bg=self.colors["bg_secondary"], height=30)
            info_frame.pack(fill="x", padx=2, pady=(2, 0))
            info_frame.pack_propagate(False)

            # 左侧：排名信息（显示总排名）
            total_players = len(sorted_users)
            rank_label = tk.Label(
                info_frame,
                text=f"排名: #{self_rank}/{total_players}",
                font=self.get_font(9, "bold"),
                bg=self.colors["bg_secondary"],
                fg=self.colors["neon_yellow"],
                anchor="w"
            )
            rank_label.pack(side="left", padx=5, pady=5)

            # 右侧：总治疗
            healing_text = f"治疗: {total_healing:,.0f}"
            if total_healing >= 1000000:
                healing_text = f"治疗: {total_healing/1000000:.1f}M"
            elif total_healing >= 1000:
                healing_text = f"治疗: {total_healing/1000:.1f}K"

            healing_label = tk.Label(
                info_frame,
                text=healing_text,
                font=self.get_font(9, "bold"),
                bg=self.colors["bg_secondary"],
                fg=self.colors["neon_cyan"],
                anchor="e"
            )
            healing_label.pack(side="right", padx=5, pady=5)

            print(
                f"[DEBUG] 个人DPS更新: {display_name} - 排名#{self_rank}, DPS:{dps:,.0f}, 治疗:{total_healing:,.0f}")
        else:
            # 显示等待个人数据的标签
            no_data_label = tk.Label(
                container,
                text="等待个人数据...",
                font=self.get_font(9),
                bg=self.colors["bg_secondary"],
                fg=self.colors["text_secondary"]
            )
            no_data_label.pack(expand=True)
            print("[DEBUG] 未找到个人DPS数据")

    def update_prominent_top_dps(self, timer_window, sorted_users, max_damage=None):
        """更新前10名其他人DPS条显示 - 新的5盒子布局"""
        # 检查新的5个Frame容器是否存在
        if not hasattr(timer_window, 'prominent_top_center_frame') or \
           not hasattr(timer_window, 'prominent_top_right_frame') or \
           not hasattr(timer_window, 'prominent_bottom_left_frame') or \
           not hasattr(timer_window, 'prominent_bottom_center_frame') or \
           not hasattr(timer_window, 'prominent_bottom_right_frame'):
            print("[DEBUG] DPS容器不存在")
            return

        # 获取五个Frame容器，按新的排名顺序
        containers = [
            timer_window.prominent_top_center_frame,   # 1-2名
            timer_window.prominent_top_right_frame,    # 3-4名
            timer_window.prominent_bottom_left_frame,  # 5-6名
            timer_window.prominent_bottom_center_frame,  # 7-8名
            timer_window.prominent_bottom_right_frame  # 9-10名
        ]

        # 清除旧的显示
        for container in containers:
            for widget in container.winfo_children():
                widget.destroy()

        print(f"[DEBUG] 准备显示前10名玩家（新5盒子布局）")

        if not sorted_users:
            return

        # 直接取前10名玩家
        top_players = sorted_users[:10]

        print(f"[DEBUG] 找到{len(top_players)}名玩家数据")

        if not top_players:
            for container in containers:
                no_data_label = tk.Label(
                    container,
                    text="暂无数据",
                    font=self.get_font(8),
                    bg=self.colors["bg_accent"],
                    fg=self.colors["text_secondary"]
                )
                no_data_label.pack(expand=True)
            return

        # 分配玩家到五个区域：2人 + 2人 + 2人 + 2人 + 2人
        player_groups = [
            top_players[:2],      # 1-2名
            top_players[2:4],     # 3-4名
            top_players[4:6],     # 5-6名
            top_players[6:8],     # 7-8名
            top_players[8:10]     # 9-10名
        ]

        for group_idx, (players, container) in enumerate(zip(player_groups, containers)):
            for idx, (uid, info) in enumerate(players):
                display_name = self.get_display_name(uid)
                dps = info.get("total_dps", 0)
                total_damage = info.get("total_damage", {}).get("total", 0)
                rank = group_idx * 2 + idx + 1

                # 创建紧凑的DPS条
                self.create_miniui_dps_bar(
                    container, display_name, dps, total_damage, rank,
                    is_self=False, compact=True, max_damage=max_damage)

                print(f"[DEBUG] 第{rank}名: {display_name} - DPS: {dps:,.0f}")

        print(f"[DEBUG] 前10名玩家DPS更新完成（新5盒子布局），显示{len(top_players)}名")

    def create_miniui_dps_bar(self, parent, name, dps, total_damage, rank, is_self=False, compact=False, max_damage=None):
        """创建紧凑的DPS条块 - 类似MINIUI但更紧凑，带有完整进度条"""
        # 条目容器 - 固定小高度
        bar_container = tk.Frame(
            parent, bg=self.colors["bg_primary"], height=28)
        bar_container.pack(fill="x", padx=2, pady=1)
        bar_container.pack_propagate(False)

        # 根据排名确定颜色
        if is_self:
            text_color = self.colors["neon_yellow"]
            bar_color = self.colors["neon_yellow"]
        elif rank == 1:
            text_color = self.colors["neon_green"]
            bar_color = self.colors["neon_green"]
        elif rank == 2:
            text_color = self.colors["neon_cyan"]
            bar_color = self.colors["neon_cyan"]
        elif rank == 3:
            text_color = self.colors["neon_yellow"]
            bar_color = self.colors["neon_yellow"]
        else:
            text_color = self.colors["text_primary"]
            bar_color = self.colors["text_secondary"]

        # 上半部分：名字和排名
        name_frame = tk.Frame(
            bar_container, bg=self.colors["bg_primary"], height=14)
        name_frame.pack(fill="x")
        name_frame.pack_propagate(False)

        rank_name = f"#{rank} {name[:10]}" + ("..." if len(name) > 10 else "")
        name_label = tk.Label(
            name_frame,
            text=rank_name,
            font=self.get_font(8, "bold"),
            bg=self.colors["bg_primary"],
            fg=text_color,
            anchor="w"
        )
        name_label.pack(side="left", pady=1)

        # 总伤害和DPS数值（右侧）
        # 总伤害
        damage_text = self.format_damage_number(total_damage)

        damage_label = tk.Label(
            name_frame,
            text=damage_text,
            font=self.get_font(6),
            bg=self.colors["bg_primary"],
            fg=text_color,
            anchor="e"
        )
        damage_label.pack(side="right", pady=1, padx=(0, 2))

        # DPS数值
        dps_text = f"{dps:,.0f}"
        if dps >= 1000000:
            dps_text = f"{dps/1000000:.1f}M"
        elif dps >= 1000:
            dps_text = f"{dps/1000:.1f}K"

        dps_label = tk.Label(
            name_frame,
            text=dps_text,
            font=self.get_font(7, "normal"),  # 改为normal，让字体变细
            bg=self.colors["bg_primary"],
            fg=text_color,
            anchor="e"
        )
        dps_label.pack(side="right", pady=1)

        # 下半部分：进度条
        progress_frame = tk.Frame(
            bar_container, bg=self.colors["bg_primary"], height=14)
        progress_frame.pack(fill="x")
        progress_frame.pack_propagate(False)

        # 进度条背景
        progress_bg = tk.Frame(
            progress_frame, bg=self.colors["bg_secondary"], height=6)
        progress_bg.pack(fill="x", padx=2, pady=4)

        # 进度条 - 基于最高伤害
        if max_damage and max_damage > 0 and total_damage > 0:
            progress_ratio = min(1.0, total_damage / max_damage)
            if progress_ratio > 0:
                progress_bar = tk.Frame(progress_bg, bg=bar_color, height=6)
                progress_bar.place(x=0, y=0, relwidth=progress_ratio, height=6)

    def _auto_start_direct_mode(self):
        """自动启动直接模式"""
        try:
            self.update_status("[AUTO] 检测到数据源，自动启动直接模式...")
            # 自动启动直接模式
            self.start_direct_mode()
        except Exception as e:
            self.update_status(f"[ERROR] 自动启动直接模式失败: {e}")
            self.update_status("[INFO] 请手动点击DIRECT按钮启动")


def create_act_ui():
    """创建并运行ACT UI - Cyberpunk风格"""
    ui = ACTDamageUI()
    ui.run()


def hide_console():
    """隐藏控制台窗口"""
    if os.name == 'nt':
        try:
            whnd = ctypes.windll.kernel32.GetConsoleWindow()
            if whnd != 0:
                ctypes.windll.user32.ShowWindow(whnd, 0)  # 0 = SW_HIDE
        except Exception as e:
            print(f"隐藏控制台失败: {e}")


# 只在直接运行时隐藏控制台，打包版本由launcher控制
if __name__ == "__main__":
    hide_console()
    create_act_ui()
