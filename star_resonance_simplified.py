#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
星痕共鸣伤害统计器 - 简化启动器
使用预编译的Node.js服务器来避免依赖问题
增强错误处理和稳定性
"""

import os
import re
import sys
import json
import time
import ctypes
import signal
import socket
import psutil
import sqlite3
import threading
import subprocess
import tkinter as tk
import colorsys
from tkinter import ttk, messagebox
from device_selector import DeviceSelector
from pathlib import Path


class StarResonanceLauncher:
    def __init__(self, debug_mode=False):
        # 调试模式标志
        self.debug_mode = debug_mode

        # 处理PyInstaller打包后的路径
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件
            self.base_dir = Path(sys._MEIPASS)
        else:
            # 如果是源码运行
            self.base_dir = Path(__file__).parent

        # 检查并确定使用哪种ACT启动方式
        self.server_exe = self.base_dir / "star-resonance-server.exe"
        self.server_js = self.base_dir / "server.js"
        self.node_exe = self.find_node_executable()

        # 优先使用预编译可执行文件（适合打包成单一exe）
        self.use_nodejs = False
        if self.server_exe.exists():
            print("[INFO] 使用预编译可执行文件启动方式")
        elif self.node_exe and self.server_js.exists():
            self.use_nodejs = True
            print("[INFO] 使用 Node.js + server.js 启动方式（备选）")
        else:
            print("[ERROR] 找不到可用的ACT启动方式")

        self.node_process = None
        self.ui_process = None
        self.server_monitor_thread = None
        self.monitor_running = False

        # Cyberpunk配色方案
        self.colors = {
            "bg_primary": "#0F0F23",
            "bg_secondary": "#181833",
            "bg_accent": "#1A1A3A",
            "neon_cyan": "#00FFFF",
            "neon_green": "#00FF00",
            "neon_pink": "#FF0080",
            "neon_purple": "#8000FF",
            "neon_yellow": "#FFFF00",
            "neon_orange": "#FF8000",
            "text_primary": "#E0E0E0",
            "text_accent": "#B0B0B0",
            "border_light": "#404060",
        }

        # RGB动画相关属性
        self.rgb_animation_running = False
        self.rgb_color_index = 0
        self.border_frame = None
        self.border_colors = []
        self.generate_gradient_colors()

        # 窗口拖动相关属性
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_topmost = True

        # 服务器输出监控相关属性
        self.server_output_lines = []
        self.output_monitor_thread = None
        self.monitor_running = False

        # 确保日志目录存在
        self.log_dir = self.base_dir / "temp_logs"
        self.log_dir.mkdir(exist_ok=True)
        self.server_log_file = self.log_dir / "server_output.log"

        # 确保路径存在
        self.validate_paths()

    def find_node_executable(self):
        """查找Node.js可执行文件"""
        # 可能的Node.js路径
        possible_paths = [
            self.base_dir / "portable" / "node.exe",
            self.base_dir / "portable" / "node" / "node.exe",
            self.base_dir / "node.exe",
        ]

        for path in possible_paths:
            if path.exists():
                print(f"[INFO] 找到Node.js: {path}")
                return str(path)

        # 如果都找不到，尝试系统node命令
        try:
            result = subprocess.run(["node", "--version"],
                                    capture_output=True, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode == 0:
                print(f"[INFO] 使用系统Node.js: {result.stdout.strip()}")
                return "node"  # 返回命令名
        except:
            pass

        print("[WARNING] 未找到Node.js")
        return None

    def start_output_monitor(self):
        """启动服务器输出监控线程"""
        if not self.node_process or not self.node_process.stdout:
            return

        def monitor_output():
            try:
                print("[INFO] 启动服务器输出监控...")
                for line in iter(self.node_process.stdout.readline, ''):
                    if not line:
                        break

                    line = line.strip()
                    if line:
                        # 存储输出行
                        self.server_output_lines.append(line)

                        # 只保留最近1000行
                        if len(self.server_output_lines) > 1000:
                            self.server_output_lines = self.server_output_lines[-1000:]

                        # 写入日志文件供ACT UI读取
                        try:
                            with open(self.server_log_file, 'a', encoding='utf-8') as f:
                                f.write(f"[SERVER] {line}\n")
                        except Exception as e:
                            print(f"[ERROR] 写入日志文件失败: {e}")

                        # 如果是调试模式，打印到控制台
                        if self.debug_mode:
                            print(f"[SERVER] {line}")

            except Exception as e:
                print(f"[ERROR] 输出监控异常: {e}")
            finally:
                print("[INFO] 服务器输出监控线程已退出")

        # 启动监控线程
        self.output_monitor_thread = threading.Thread(
            target=monitor_output, daemon=True)
        self.output_monitor_thread.start()
        self.monitor_running = True
        print("[INFO] 服务器输出监控线程已启动")

    def generate_gradient_colors(self):
        """生成RGB彩虹渐变色彩"""
        gradient_colors = []
        steps = 60
        for i in range(steps):
            hue = i / steps
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
            )
            gradient_colors.append(hex_color)
        self.border_colors = gradient_colors

    def animate_rgb_border(self):
        """RGB边框动画"""
        if (self.rgb_animation_running and
            self.border_frame and
            hasattr(self, 'control_window') and
            self.control_window and
                self.control_window.winfo_exists()):
            try:
                color = self.border_colors[self.rgb_color_index]
                self.border_frame.configure(bg=color)
                self.rgb_color_index = (
                    self.rgb_color_index + 1) % len(self.border_colors)
                self.control_window.after(50, self.animate_rgb_border)
            except tk.TclError:
                self.rgb_animation_running = False

    def start_rgb_animation(self):
        """启动RGB动画"""
        if hasattr(self, 'control_window') and self.control_window and self.control_window.winfo_exists():
            self.rgb_animation_running = True
            self.animate_rgb_border()

    def stop_rgb_animation(self):
        """停止RGB动画"""
        self.rgb_animation_running = False

    def create_rgb_border(self, parent):
        """创建RGB彩虹边框"""
        self.border_frame = tk.Frame(parent, bg="#ff0000", bd=0, relief="flat")
        self.border_frame.pack(fill="both", expand=True, padx=3, pady=3)
        main_frame = tk.Frame(
            self.border_frame, bg=self.colors["bg_primary"], bd=0, relief="flat"
        )
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        return main_frame

    def create_styled_button(self, parent, text, command, width=20):
        """创建样式化按钮"""
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.colors["bg_accent"],
            fg=self.colors["neon_cyan"],
            activebackground=self.colors["neon_cyan"],
            activeforeground=self.colors["bg_primary"],
            font=("Consolas", 10, "bold"),
            bd=1,
            relief="solid",
            width=width,
            cursor="hand2",
        )

        def on_enter(event):
            button.configure(
                bg=self.colors["neon_cyan"], fg=self.colors["bg_primary"])

        def on_leave(event):
            button.configure(
                bg=self.colors["bg_accent"], fg=self.colors["neon_cyan"])

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
        return button

    def create_styled_label(self, parent, text, font_size=10, color="text_primary"):
        """创建样式化标签"""
        return tk.Label(
            parent,
            text=text,
            bg=self.colors["bg_primary"],
            fg=self.colors[color],
            font=("Consolas", font_size, "bold"),
        )

    def add_window_dragging(self, widget):
        """为窗口添加拖动功能"""
        def start_drag(event):
            self.drag_start_x = event.x
            self.drag_start_y = event.y

        def on_drag(event):
            x = self.control_window.winfo_x() + event.x - self.drag_start_x
            y = self.control_window.winfo_y() + event.y - self.drag_start_y
            self.control_window.geometry(f"+{x}+{y}")

        widget.bind("<Button-1>", start_drag)
        widget.bind("<B1-Motion>", on_drag)

        for child in widget.winfo_children():
            if isinstance(child, (tk.Frame, tk.Label)):
                child.bind("<Button-1>", start_drag)
                child.bind("<B1-Motion>", on_drag)

    def toggle_topmost(self):
        """切换窗口置顶状态"""
        self.is_topmost = not self.is_topmost
        self.control_window.wm_attributes("-topmost", self.is_topmost)
        status = "置顶" if self.is_topmost else "取消置顶"
        self.log_status(f"[INFO] 窗口已{status} (F6切换)")

    def validate_paths(self):
        """验证必要的文件路径"""
        if not self.use_nodejs:
            # 优先检查预编译可执行文件
            if not self.server_exe.exists():
                self.show_error(f"预编译服务器不存在: {self.server_exe}")
                return False
        else:
            # 备选方案：Node.js + server.js
            if not self.server_js.exists():
                self.show_error(f"服务器脚本不存在: {self.server_js}")
                return False
            if not self.node_exe:
                self.show_error("未找到Node.js可执行文件")
                return False
        return True

    def get_network_devices(self):
        """获取网络设备列表"""
        try:
            if not self.use_nodejs:
                # 使用预编译可执行文件获取设备列表
                print("[INFO] 使用预编译服务器获取设备列表...")
                temp_server = subprocess.Popen(
                    [str(self.server_exe), "--list-devices"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(self.base_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            else:
                # 使用Node.js + server.js获取设备列表
                print("[INFO] 使用Node.js获取设备列表...")
                cmd = [self.node_exe, str(self.server_js), "--list-devices"]
                temp_server = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=str(self.base_dir),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )

            stdout, stderr = temp_server.communicate(timeout=15)

            if temp_server.returncode == 0 and stdout:
                try:
                    # 解析设备列表JSON
                    devices = json.loads(stdout.strip())
                    print(f"获取到 {len(devices)} 个网络设备")
                    return devices
                except json.JSONDecodeError as e:
                    print(f"解析设备列表JSON失败: {e}")
            else:
                print(f"ACT返回错误: {stderr}")

        except subprocess.TimeoutExpired:
            print("获取设备列表超时")
            temp_server.kill()
        except Exception as e:
            print(f"获取设备列表异常: {e}")

        # 如果获取失败，返回模拟的设备列表作为备选
        print("使用模拟设备列表作为备选")
        return [
            {
                "name": "\\Device\\NPF_{12345678-1234-1234-1234-123456789ABC}",
                "description": "以太网 - Realtek PCIe GbE Family Controller",
                "address": "192.168.1.100",
                "netmask": "255.255.255.0"
            },
            {
                "name": "\\Device\\NPF_{87654321-4321-4321-4321-CBA987654321}",
                "description": "Wi-Fi - Intel(R) Wireless-AC 9560 160MHz",
                "address": "192.168.1.101",
                "netmask": "255.255.255.0"
            }
        ]

    def show_device_selector(self):
        """显示设备选择器"""
        devices = self.get_network_devices()
        if not devices:
            self.show_error("无法获取网络设备列表！")
            return None, None

        print(f"显示设备选择器，找到 {len(devices)} 个设备")
        selector = DeviceSelector()
        device, log_level = selector.show_device_selector(devices)

        print(f"设备选择器返回: device={device}, log_level={log_level}")

        if device == "EXIT":
            print("用户选择退出")
            sys.exit(0)
        elif device is None:
            print("用户取消选择或未选择设备")
            return None, None

        print(f"用户选择了设备: {device['description']}, 日志级别: {log_level}")
        return device, log_level

    def is_port_in_use(self, port):
        """检查端口是否被占用"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                s.close()
            except socket.error:
                return True

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                return result == 0
            except:
                return False

    def kill_process_on_port(self, port):
        """杀死占用指定端口的进程"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    # 获取进程的网络连接
                    connections = proc.connections(kind='inet')
                    if connections:
                        for conn in connections:
                            if hasattr(conn.laddr, 'port') and conn.laddr.port == port:
                                print(
                                    f"找到占用端口{port}的进程: {proc.info['name']} (PID: {proc.info['pid']})")
                                proc.terminate()
                                proc.wait(timeout=5)
                                print(f"已终止进程: {proc.info['name']}")
                                return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    continue
        except Exception as e:
            print(f"杀死端口 {port} 进程失败: {e}")
        return False

    def start_node_server(self, device, log_level):
        """启动服务器"""
        if self.is_port_in_use(8989):
            print("端口8989被占用，尝试关闭...")
            self.kill_process_on_port(8989)
            time.sleep(2)

        # 重新获取最新的设备列表
        devices = self.get_network_devices()
        device_index = None
        for i, dev in enumerate(devices):
            if dev['name'] == device['name']:
                device_index = i
                break

        if device_index is None:
            self.show_error("找不到选择的设备索引！")
            return False

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 根据启动方式构建命令
                if not self.use_nodejs:
                    # 使用预编译可执行文件
                    cmd = [
                        str(self.server_exe),
                        str(device_index),
                        log_level
                    ]
                    print(f"[INFO] 使用预编译服务器启动")
                else:
                    # 使用Node.js + server.js
                    cmd = [
                        self.node_exe,
                        str(self.server_js),
                        str(device_index),
                        log_level
                    ]
                    print(f"[INFO] 使用Node.js启动")

                print(
                    f"启动命令 (尝试 {attempt + 1}/{max_retries}): {' '.join(cmd)}")
                print(f"设备: {device['description']}")
                print(f"日志级别: {log_level}")

                # 启动进程
                startupinfo = None
                creation_flags = 0

                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    creation_flags = subprocess.CREATE_NO_WINDOW

                # 启动服务器进程，根据调试模式和类型选择启动方式
                if not self.use_nodejs:
                    # 预编译可执行文件
                    if self.debug_mode:
                        # 调试模式：显示控制台窗口
                        self.node_process = subprocess.Popen(
                            cmd,
                            cwd=str(self.base_dir)
                        )
                    else:
                        # 发布模式：隐藏窗口
                        if os.name == 'nt':
                            # 正确的隐藏窗口方法
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = subprocess.SW_HIDE
                            creation_flags = subprocess.CREATE_NO_WINDOW

                            self.node_process = subprocess.Popen(
                                cmd,
                                startupinfo=startupinfo,
                                creationflags=creation_flags,
                                cwd=str(self.base_dir),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL
                            )
                        else:
                            self.node_process = subprocess.Popen(
                                cmd,
                                cwd=str(self.base_dir),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL
                            )
                else:
                    # Node.js方式
                    if self.debug_mode:
                        # 调试模式：不隐藏窗口
                        self.node_process = subprocess.Popen(
                            cmd,
                            cwd=str(self.base_dir)
                        )
                    else:
                        # 发布模式：隐藏窗口
                        if os.name == 'nt':
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = subprocess.SW_HIDE
                            creation_flags = subprocess.CREATE_NO_WINDOW
                        else:
                            startupinfo = None
                            creation_flags = 0

                        self.node_process = subprocess.Popen(
                            cmd,
                            startupinfo=startupinfo,
                            creationflags=creation_flags,
                            cwd=str(self.base_dir),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL
                        )
                print("ACT启动中...")

                # 等待ACT启动
                print("等待ACT启动...")
                startup_success = False

                for i in range(60):  # 等待最多60秒
                    if self.is_port_in_use(8989):
                        print("[OK] ACT启动成功！")
                        startup_success = True
                        break

                    # 检查进程是否异常退出
                    if self.node_process.poll() is not None:
                        error_msg = f"服务器进程退出 (尝试 {attempt + 1}), 退出码: {self.node_process.returncode}"
                        print(error_msg)

                        if hasattr(self, 'status_text'):
                            self.log_status(f"[WARNING] {error_msg}")

                        # 如果是最后一次尝试，返回失败
                        if attempt == max_retries - 1:
                            return False

                        # 否则等待一段时间后重试
                        print(f"等待 3 秒后重试...")
                        time.sleep(3)
                        break

                    # 每5秒显示一次等待状态
                    if i % 5 == 0:
                        print(f"等待中... ({i}/60秒)")

                    time.sleep(1)

                if startup_success:
                    # 启动服务器监控线程
                    self.start_server_monitor()
                    return True

                # 如果启动超时但进程还在运行，尝试终止它
                if self.node_process.poll() is None:
                    print(f"服务器启动超时 (尝试 {attempt + 1})，终止进程...")
                    try:
                        self.node_process.terminate()
                        self.node_process.wait(timeout=5)
                    except:
                        try:
                            self.node_process.kill()
                        except:
                            pass

            except Exception as e:
                error_msg = f"启动服务器异常 (尝试 {attempt + 1}): {str(e)}"
                print(error_msg)
                if hasattr(self, 'status_text'):
                    self.log_status(f"[ERROR] {error_msg}")

                # 清理进程
                if hasattr(self, 'node_process') and self.node_process:
                    try:
                        self.node_process.terminate()
                        self.node_process.wait(timeout=3)
                    except:
                        try:
                            self.node_process.kill()
                        except:
                            pass

            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries - 1:
                print(f"等待 5 秒后进行下一次尝试...")
                time.sleep(5)

        # 所有尝试都失败了
        self.show_error(f"服务器启动失败，已尝试 {max_retries} 次")
        return False

    def start_server_monitor(self):
        """启动服务器监控线程"""
        if self.server_monitor_thread and self.server_monitor_thread.is_alive():
            return

        self.monitor_running = True
        self.server_monitor_thread = threading.Thread(
            target=self.monitor_server, daemon=True)
        self.server_monitor_thread.start()
        print("[INFO] 服务器监控线程已启动")

    def monitor_server(self):
        """监控服务器进程状态"""
        while self.monitor_running and self.node_process:
            try:
                # 检查进程是否还在运行
                if self.node_process.poll() is not None:
                    print(
                        f"[WARNING] 服务器进程已退出，退出码: {self.node_process.returncode}")
                    if hasattr(self, 'status_text'):
                        self.log_status(
                            f"[ERROR] 服务器进程异常退出！退出码: {self.node_process.returncode}")
                    break

                # 检查端口是否还在监听
                if not self.is_port_in_use(8989):
                    print("[WARNING] 端口8989不再监听")
                    if hasattr(self, 'status_text'):
                        self.log_status("[WARNING] 服务器端口8989不再监听")

                time.sleep(5)  # 每5秒检查一次

            except Exception as e:
                print(f"[ERROR] 服务器监控异常: {e}")
                break

        print("[INFO] 服务器监控线程已退出")

    def stop_server_monitor(self):
        """停止服务器监控"""
        self.monitor_running = False
        if self.server_monitor_thread and self.server_monitor_thread.is_alive():
            self.server_monitor_thread.join(timeout=2)

    def start_ui(self):
        """启动ACT UI界面"""
        try:
            print("[DEBUG] 开始导入act_damage_ui模块...")
            from act_damage_ui import ACTDamageUI
            print("[DEBUG] act_damage_ui模块导入成功")

            print("[DEBUG] 创建UI实例...")

            def ui_worker():
                try:
                    print("[DEBUG] 在线程中创建UI实例...")
                    ui = ACTDamageUI()
                    print("[DEBUG] UI实例创建成功，开始运行...")
                    ui.run()
                    print("[DEBUG] UI运行结束")
                except Exception as e:
                    print(f"[ERROR] UI线程中发生错误: {e}")
                    import traceback
                    traceback.print_exc()

            # 在打包环境中，不使用daemon线程，而是普通线程
            print("[DEBUG] 启动UI线程...")
            ui_thread = threading.Thread(target=ui_worker, daemon=False)
            ui_thread.start()

            # 等待一小段时间确保UI启动
            print("[DEBUG] 等待UI启动...")
            time.sleep(3)
            print("[DEBUG] UI启动等待完成")
            return True
        except Exception as e:
            error_msg = f"启动UI界面失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()
            self.show_error(error_msg)
            return False

    def show_error(self, message):
        """显示错误消息"""
        print(f"[ERROR] {message}")
        try:
            messagebox.showerror("错误", message)
        except:
            pass

    def show_success(self, message):
        """显示成功消息"""
        print(f"[SUCCESS] {message}")
        try:
            messagebox.showinfo("成功", message)
        except:
            pass

    def create_control_window(self):
        """创建控制窗口"""
        self.control_window = tk.Tk()
        self.control_window.title("[*] STAR_RESONANCE_CONTROL_CENTER [*]")
        self.control_window.geometry("700x600")
        self.control_window.configure(bg="#000000")
        self.control_window.overrideredirect(True)
        self.control_window.wm_attributes("-topmost", True)
        self.control_window.wm_attributes("-alpha", 0.95)
        self.control_window.resizable(False, False)

        # 创建RGB边框
        main_frame = self.create_rgb_border(self.control_window)

        # 设置窗口居中
        self.control_window.update_idletasks()
        width = self.control_window.winfo_reqwidth()
        height = self.control_window.winfo_reqheight()
        x = (self.control_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.control_window.winfo_screenheight() // 2) - (height // 2)
        self.control_window.geometry(f"+{x}+{y}")

        # 标题框架
        title_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        # 主标题
        title_label = self.create_styled_label(
            title_frame,
            "[*] 星痕共鸣伤害统计器控制台 [*]",
            font_size=16,
            color="neon_cyan"
        )
        title_label.pack()

        # 副标题
        subtitle_label = self.create_styled_label(
            title_frame,
            "STAR RESONANCE DAMAGE COUNTER - CONTROL CENTER",
            font_size=10,
            color="text_accent"
        )
        subtitle_label.pack(pady=(5, 0))

        # 状态信息框架
        status_info_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        status_info_frame.pack(fill="x", padx=20, pady=(0, 10))

        info_label = self.create_styled_label(
            status_info_frame,
            "[*] 系统状态监控:",
            font_size=12,
            color="neon_green"
        )
        info_label.pack(anchor="w")

        # 状态显示区域
        status_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        status_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # 创建带边框的文本区域
        text_border_frame = tk.Frame(
            status_frame, bg=self.colors["border_light"], bd=1, relief="solid"
        )
        text_border_frame.pack(fill="both", expand=True)

        # 滚动条
        scrollbar = tk.Scrollbar(
            text_border_frame, bg=self.colors["bg_accent"])
        scrollbar.pack(side="right", fill="y")

        # 状态文本框
        self.status_text = tk.Text(
            text_border_frame,
            height=20,
            width=70,
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_primary"],
            font=("Consolas", 9),
            wrap=tk.WORD,
            bd=0,
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
            insertbackground=self.colors["neon_cyan"]
        )
        self.status_text.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar.config(command=self.status_text.yview)

        # 帮助信息框架
        help_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        help_frame.pack(fill="x", padx=20, pady=(0, 10))

        help_text = ("[INFO] 使用提示：\n"
                     "• 确保游戏正在运行点击Start\n"
                     "• 如遇问题可尝试重新启动\n"
                     "• 快捷键: F5重启 | F6置顶 | F7退出 | ESC退出")
        help_label = self.create_styled_label(
            help_frame, help_text, font_size=8, color="text_accent"
        )
        help_label.pack(anchor="w")

        # 按钮框架
        button_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        button_frame.pack(fill="x", padx=20, pady=(5, 20))

        # 重启按钮
        restart_btn = self.create_styled_button(
            button_frame,
            "[*] 重新启动 [*]",
            self.restart_application,
            width=15
        )
        restart_btn.pack(side="left", padx=(0, 10))

        # 关闭按钮
        close_btn = self.create_styled_button(
            button_frame,
            "[*] 关闭程序 [*]",
            self.close_application,
            width=15
        )
        close_btn.pack(side="right")

        # 添加窗口拖动功能
        self.add_window_dragging(main_frame)

        # 绑定键盘事件
        self.control_window.bind(
            "<Escape>", lambda e: self.close_application())
        self.control_window.bind("<F5>", lambda e: self.restart_application())
        self.control_window.bind("<F6>", lambda e: self.toggle_topmost())
        self.control_window.bind("<F7>", lambda e: self.close_application())

        # 关闭窗口事件
        def on_window_close():
            self.stop_rgb_animation()
            self.close_application()

        self.control_window.protocol("WM_DELETE_WINDOW", on_window_close)

        # 启动RGB动画
        self.start_rgb_animation()

        return self.control_window

    def log_status(self, message):
        """记录状态信息"""
        if hasattr(self, 'status_text') and self.status_text:
            try:
                timestamp = time.strftime("%H:%M:%S")
                # 添加颜色标记
                if "[OK]" in message or "成功" in message:
                    color_tag = "success"
                elif "[ERROR]" in message or "失败" in message or "错误" in message:
                    color_tag = "error"
                elif "[WARNING]" in message or "警告" in message:
                    color_tag = "warning"
                else:
                    color_tag = "info"

                # 配置文本标签颜色
                self.status_text.tag_configure(
                    "success", foreground=self.colors["neon_green"])
                self.status_text.tag_configure(
                    "error", foreground=self.colors["neon_pink"])
                self.status_text.tag_configure(
                    "warning", foreground=self.colors["neon_yellow"])
                self.status_text.tag_configure(
                    "info", foreground=self.colors["text_primary"])
                self.status_text.tag_configure(
                    "timestamp", foreground=self.colors["neon_cyan"])

                # 插入时间戳
                self.status_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
                # 插入消息
                self.status_text.insert(tk.END, f"{message}\n", color_tag)
                self.status_text.see(tk.END)
                self.status_text.update()
            except Exception as e:
                print(f"日志记录失败: {e}")

    def restart_application(self):
        """重新启动应用程序"""
        self.log_status("[INFO] 正在重新启动应用程序...")
        self.stop_rgb_animation()
        self.cleanup()
        time.sleep(2)

        # 关闭当前控制窗口
        if hasattr(self, 'control_window') and self.control_window:
            try:
                self.control_window.destroy()
            except:
                pass

        # 重新运行
        self.run()

    def cleanup(self):
        """清理资源"""
        print("正在清理资源...")

        # 停止RGB动画
        self.stop_rgb_animation()

        # 停止服务器监控
        self.stop_server_monitor()

        # 关闭Node.js进程
        if self.node_process and self.node_process.poll() is None:
            try:
                print("正在终止服务器进程...")
                self.node_process.terminate()

                # 等待进程正常退出
                try:
                    self.node_process.wait(timeout=10)
                    print("[OK] 服务器已正常关闭")
                except subprocess.TimeoutExpired:
                    print("服务器进程终止超时，强制杀死...")
                    self.node_process.kill()
                    try:
                        self.node_process.wait(timeout=5)
                        print("[OK] 服务器已强制关闭")
                    except:
                        print("[WARNING] 无法确认服务器进程状态")

            except Exception as e:
                print(f"关闭服务器进程时出错: {e}")
                try:
                    self.node_process.kill()
                except:
                    pass

        # 关闭占用的端口
        if self.is_port_in_use(8989):
            print("清理端口8989...")
            self.kill_process_on_port(8989)
            time.sleep(1)

        print("资源清理完成")

    def close_application(self):
        """关闭应用程序"""
        if hasattr(self, 'status_text'):
            self.log_status("[INFO] 正在关闭应用程序...")

        self.cleanup()
        print("应用程序已关闭")

        # 关闭控制窗口
        if hasattr(self, 'control_window') and self.control_window:
            try:
                self.control_window.quit()
                self.control_window.destroy()
            except:
                pass

        os._exit(0)

    def run(self):
        """运行主程序"""
        print("=" * 60)
        print("[INFO] 启动星痕共鸣伤害统计器...")
        print("[INFO] STAR RESONANCE DAMAGE COUNTER INITIALIZING...")
        print("=" * 60)

        # 先显示设备选择器
        print("[INFO] 显示设备选择器...")
        device, log_level = self.show_device_selector()

        if device is None:
            print("[INFO] 用户取消了设备选择")
            return

        print(f"[OK] 已选择设备: {device['description']}")
        print(f"[OK] 日志级别: {log_level}")

        # 启动服务器
        print("[INFO] 正在启动服务器...")
        if not self.start_node_server(device, log_level):
            print("[ERROR] 服务器启动失败")
            return

        print("[OK] 服务器启动成功")

        # 启动UI界面
        print("[INFO] 正在启动UI界面...")
        if self.start_ui():
            print("[OK] UI界面启动成功")
        else:
            print("[ERROR] UI界面启动失败")

        print("=" * 50)
        print("[OK] 应用程序启动完成！")
        print("=" * 50)

        # 创建并显示控制窗口
        control_window = self.create_control_window()

        # 在控制窗口中显示状态
        self.log_status("[OK] 应用程序启动完成！")
        self.log_status(
            f"[OK] 选择设备: {device['description'][:50]}{'...' if len(device['description']) > 50 else ''}")
        self.log_status(f"[OK] 日志级别: {log_level}")
        self.log_status("[OK] ACT正在运行...")
        self.log_status("[OK] 系统已就绪，等待游戏连接...")
        self.log_status("[INFO] 快捷键: F5重启 | F6置顶 | F7退出 | 拖动标题栏移动窗口")

        # 运行控制窗口（阻塞直到窗口关闭）
        try:
            control_window.mainloop()
        except KeyboardInterrupt:
            self.close_application()


def hide_console():
    """隐藏控制台窗口"""
    if os.name == 'nt':
        try:
            whnd = ctypes.windll.kernel32.GetConsoleWindow()
            if whnd != 0:
                ctypes.windll.user32.ShowWindow(whnd, 0)
                print("控制台窗口已隐藏")
        except Exception as e:
            print(f"隐藏控制台失败: {e}")


def main():
    """主函数"""
    try:
        # 检查是否启用调试模式
        debug_mode = '--debug' in sys.argv or '-d' in sys.argv

        if not debug_mode:
            # 非调试模式：隐藏控制台窗口（发布版本）
            hide_console()

        # 设置信号处理
        def signal_handler(signum, frame):
            print("\n收到中断信号，正在关闭...")
            os._exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        launcher = StarResonanceLauncher(debug_mode=debug_mode)
        if debug_mode:
            print("[DEBUG] 调试模式已启用，服务器窗口将保持可见")
        launcher.run()

    except ImportError as e:
        print(f"模块导入错误: {e}")
        # 在发生错误时显示控制台
        if not debug_mode and os.name == 'nt':
            try:
                whnd = ctypes.windll.kernel32.GetConsoleWindow()
                if whnd != 0:
                    ctypes.windll.user32.ShowWindow(whnd, 1)  # 显示控制台
            except:
                pass
        input("按回车键退出...")
    except Exception as e:
        print(f"程序运行错误: {e}")
        import traceback
        traceback.print_exc()
        # 在发生错误时显示控制台
        if not debug_mode and os.name == 'nt':
            try:
                whnd = ctypes.windll.kernel32.GetConsoleWindow()
                if whnd != 0:
                    ctypes.windll.user32.ShowWindow(whnd, 1)  # 显示控制台
            except:
                pass
        input("按回车键退出...")


if __name__ == "__main__":
    main()
