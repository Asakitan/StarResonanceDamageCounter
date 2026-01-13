import tkinter as tk
import colorsys
import socket
import subprocess
import psutil
import ipaddress
import re


class DeviceSelector:
    def __init__(self):
        self.selected_device = None
        self.selected_log_level = "info"
        self.root = None
        self.colors = {
            "bg_primary": "#0F0F23",
            "bg_secondary": "#181833",
            "bg_accent": "#1A1A3A",
            "neon_cyan": "#00FFFF",
            "neon_green": "#00FF00",
            "neon_pink": "#FF0080",
            "neon_purple": "#8000FF",
            "neon_yellow": "#FFFF00",
            "text_primary": "#E0E0E0",
            "text_accent": "#B0B0B0",
            "border_light": "#404060",
        }
        self.rgb_animation_running = False
        self.rgb_color_index = 0
        self.border_frame = None
        self.border_colors = []
        self.generate_gradient_colors()

    def get_active_network_interfaces(self):
        """获取当前活动的网络接口"""
        active_interfaces = []
        try:
            # 获取网络接口统计信息
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()

            for interface_name, interface_stats in stats.items():
                # 检查接口是否启用且连接
                if interface_stats.isup:
                    # 过滤掉明显的虚拟接口
                    name_lower = interface_name.lower()
                    virtual_interface_keywords = [
                        'loopback', 'teredo', 'isatap', 'bluetooth', 'vmware',
                        'virtualbox', 'hyper-v', 'tap', 'tun', 'vpn'
                    ]

                    # 跳过虚拟接口
                    is_virtual = any(
                        keyword in name_lower for keyword in virtual_interface_keywords)
                    if is_virtual:
                        continue

                    # 获取接口地址信息
                    if interface_name in addrs:
                        for addr in addrs[interface_name]:
                            # 寻找IPv4地址且不是回环地址
                            if (addr.family == socket.AF_INET and
                                not addr.address.startswith('127.') and
                                    not addr.address.startswith('169.254.')):  # 排除APIPA地址

                                # 检查是否有网络流量（活跃度）
                                io_counters = psutil.net_io_counters(
                                    pernic=True)
                                if interface_name in io_counters:
                                    counter = io_counters[interface_name]
                                    # 如果有数据传输（发送或接收）
                                    if counter.bytes_sent > 0 or counter.bytes_recv > 0:
                                        active_interfaces.append({
                                            'name': interface_name,
                                            'address': addr.address,
                                            'netmask': addr.netmask,
                                            'bytes_sent': counter.bytes_sent,
                                            'bytes_recv': counter.bytes_recv
                                        })
                                        print(
                                            f"发现活动接口: {interface_name} ({addr.address}) - 流量: {counter.bytes_sent + counter.bytes_recv} bytes")
                                        break

        except Exception as e:
            print(f"获取活动网络接口时出错: {e}")

        # 按流量排序，流量最大的在前面
        active_interfaces.sort(
            key=lambda x: x['bytes_sent'] + x['bytes_recv'], reverse=True)
        return active_interfaces

    def get_default_gateway_interface(self):
        """获取默认网关对应的网络接口"""
        try:
            # 获取默认网关
            gateways = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            # 尝试通过路由表找到默认网关
            import platform
            if platform.system() == "Windows":
                try:
                    result = subprocess.run(['route', 'print', '0.0.0.0'],
                                            capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if '0.0.0.0' in line and 'Default Gateway' not in line:
                                parts = line.split()
                                if len(parts) >= 4:
                                    gateway_ip = parts[2]
                                    interface_ip = parts[3]

                                    # 找到对应的接口
                                    for interface_name, addrs in gateways.items():
                                        if interface_name in stats and stats[interface_name].isup:
                                            for addr in addrs:
                                                if (addr.family == socket.AF_INET and
                                                        addr.address == interface_ip):
                                                    return interface_name, interface_ip
                                    break
                except Exception as e:
                    print(f"通过路由表获取默认网关失败: {e}")

            # 备用方法：尝试连接外部地址来确定使用的接口
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.connect(("8.8.8.8", 80))
                local_ip = sock.getsockname()[0]
                sock.close()

                # 找到对应IP的接口
                for interface_name, addrs in gateways.items():
                    if interface_name in stats and stats[interface_name].isup:
                        for addr in addrs:
                            if (addr.family == socket.AF_INET and
                                    addr.address == local_ip):
                                return interface_name, local_ip

            except Exception as e:
                print(f"通过连接测试获取默认接口失败: {e}")

        except Exception as e:
            print(f"获取默认网关接口时出错: {e}")

        return None, None

    def is_real_network_adapter(self, device):
        """判断是否为真实的网络适配器（排除虚拟设备）"""
        if not device or 'description' not in device:
            return False

        description = device['description'].lower()

        # 排除的虚拟设备关键词
        virtual_keywords = [
            'wan miniport', 'miniport', 'loopback', 'teredo',
            'isatap', 'tunnel', 'vmware', 'virtualbox', 'hyper-v',
            'tap-', 'tun-', 'pptp', 'l2tp', 'sstp', 'ras', 'vpn', 'bridge',
            'bluetooth', 'microsoft wi-fi direct', 'software loopback',
            'adapter for loopback', 'personal area network'
        ]

        # 如果包含虚拟设备关键词，返回False
        for keyword in virtual_keywords:
            if keyword in description:
                return False

        # 检查是否有有效的IP地址（支持新的addresses格式）
        addresses = []
        if 'addresses' in device and isinstance(device['addresses'], list):
            # 新格式：addresses数组
            addresses = device['addresses']
        elif 'address' in device and device['address']:
            # 旧格式：单个address字段
            addresses = [{'addr': device['address']}]

        # 检查是否有有效的IPv4地址
        has_valid_ipv4 = False
        for addr_info in addresses:
            if isinstance(addr_info, dict) and 'addr' in addr_info:
                addr = addr_info['addr']
                # 检查是否为有效的IPv4地址（排除回环、APIPA、空地址）
                if (addr and ':' not in addr and  # 排除IPv6
                    not addr.startswith('127.') and  # 排除回环
                    not addr.startswith('169.254.') and  # 排除APIPA
                        addr != '0.0.0.0' and addr != ''):  # 排除空/无效地址
                    has_valid_ipv4 = True
                    break

        return has_valid_ipv4

    def get_device_ipv4_addresses(self, device):
        """从设备中提取所有IPv4地址"""
        ipv4_addresses = []

        # 支持新格式：addresses数组
        if 'addresses' in device and isinstance(device['addresses'], list):
            for addr_info in device['addresses']:
                if isinstance(addr_info, dict) and 'addr' in addr_info:
                    addr = addr_info['addr']
                    # 只保留IPv4地址
                    if addr and ':' not in addr and not addr.startswith('fe80'):
                        ipv4_addresses.append(addr)

        # 支持旧格式：单个address字段
        elif 'address' in device and device['address']:
            addr = device['address']
            if addr and ':' not in addr:
                ipv4_addresses.append(addr)

        return ipv4_addresses

    def find_best_matching_device(self, devices):
        """在设备列表中找到最佳匹配的活动设备"""
        if not devices:
            return None

        # 首先过滤出真实的网络适配器
        real_devices = [
            device for device in devices if self.is_real_network_adapter(device)]
        print(f"过滤后的真实网络设备数量: {len(real_devices)}/{len(devices)}")

        # 如果没有真实设备，使用原始列表
        if not real_devices:
            real_devices = devices
            print("警告: 未找到真实网络设备，使用所有设备")

        # 首先尝试获取默认网关接口
        default_interface, default_ip = self.get_default_gateway_interface()
        if default_interface and default_ip:
            print(f"检测到默认网关接口: {default_interface} ({default_ip})")

            # 在真实设备中查找匹配的设备
            for device in real_devices:
                device_ips = self.get_device_ipv4_addresses(device)
                if default_ip in device_ips:
                    print(f"找到匹配的默认网关设备: {device['description']}")
                    return device

                # 也检查描述中是否包含接口名的关键部分
                interface_keywords = default_interface.lower().split()
                device_desc = device['description'].lower()
                for keyword in interface_keywords:
                    if len(keyword) > 3 and keyword in device_desc:  # 只匹配较长的关键词
                        print(f"通过接口名匹配到设备: {device['description']}")
                        return device

        # 如果默认网关方法失败，使用活动接口方法
        active_interfaces = self.get_active_network_interfaces()
        if active_interfaces:
            print(f"检测到 {len(active_interfaces)} 个活动网络接口")

            # 尝试匹配最活跃的接口
            for active_iface in active_interfaces:
                for device in real_devices:
                    device_ips = self.get_device_ipv4_addresses(device)
                    if active_iface['address'] in device_ips:
                        print(
                            f"找到匹配的活动设备: {device['description']} (流量: {active_iface['bytes_sent'] + active_iface['bytes_recv']} bytes)")
                        return device

        # 如果都没找到精确匹配，选择第一个真实的有效设备
        for device in real_devices:
            device_ips = self.get_device_ipv4_addresses(device)
            # 检查是否有有效的非APIPA地址
            for ip in device_ips:
                if (ip and ip != '0.0.0.0' and
                    not ip.startswith('169.254.') and
                        not ip.startswith('127.')):
                    print(f"使用第一个真实可用设备: {device['description']} (IP: {ip})")
                    return device

        # 最后备选：返回第一个真实设备
        if real_devices:
            print(f"使用第一个真实设备作为备选: {real_devices[0]['description']}")
            return real_devices[0]

        # 如果连真实设备都没有，返回原始列表的第一个
        if devices:
            print(f"警告: 使用第一个设备作为最后备选: {devices[0]['description']}")
            return devices[0]

        return None

    def generate_gradient_colors(self):
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
        # 检查窗口和组件是否仍然有效
        if (self.rgb_animation_running and
            self.border_frame and
            self.root and
                self.root.winfo_exists()):
            try:
                color = self.border_colors[self.rgb_color_index]
                self.border_frame.configure(bg=color)
                self.rgb_color_index = (
                    self.rgb_color_index + 1) % len(self.border_colors)
                # 使用try-except保护after调用
                self.root.after(50, self.animate_rgb_border)
            except tk.TclError:
                # 如果窗口已销毁，停止动画
                self.rgb_animation_running = False

    def start_rgb_animation(self):
        if self.root and self.root.winfo_exists():
            self.rgb_animation_running = True
            self.animate_rgb_border()

    def stop_rgb_animation(self):
        self.rgb_animation_running = False

    def create_rgb_border(self, parent):
        self.border_frame = tk.Frame(parent, bg="#ff0000", bd=0, relief="flat")
        self.border_frame.pack(fill="both", expand=True, padx=3, pady=3)
        main_frame = tk.Frame(
            self.border_frame, bg=self.colors["bg_primary"], bd=0, relief="flat"
        )
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        return main_frame

    def create_styled_button(self, parent, text, command, width=20):
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
        return tk.Label(
            parent,
            text=text,
            bg=self.colors["bg_primary"],
            fg=self.colors[color],
            font=("Consolas", font_size, "bold"),
        )

    def show_device_selector(self, devices):
        """显示设备选择器窗口"""
        self.devices = devices
        self.root = tk.Tk()
        self.root.title("◊ STAR_RESONANCE_DEVICE_SELECTOR ◊")
        self.root.geometry("900x700")
        self.root.configure(bg="#000000")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.95)
        main_frame = self.create_rgb_border(self.root)
        title_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        title_frame.pack(fill="x", padx=20, pady=(20, 10))
        title_label = self.create_styled_label(
            title_frame,
            "◊ 星痕共鸣伤害统计器 - 网络设备选择 ◊",
            font_size=16,
            color="neon_cyan",
        )
        title_label.pack()
        version_label = self.create_styled_label(
            title_frame,
            f"Python Port from Node.js Version | 设备数量: {len(devices)}",
            font_size=10,
            color="text_accent",
        )
        version_label.pack()
        info_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        info_frame.pack(fill="x", padx=20, pady=(0, 10))
        info_text = "请选择用于数据包捕获的网络设备。通常选择当前连接到互联网的网卡。"
        info_label = self.create_styled_label(
            info_frame, info_text, font_size=9, color="text_accent"
        )
        info_label.pack()
        device_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        device_frame.pack(fill="both", expand=True, padx=20, pady=10)
        device_label = self.create_styled_label(
            device_frame,
            "◊ 网络设备列表 (双击或按Enter确认):",
            font_size=12,
            color="neon_green",
        )
        device_label.pack(anchor="w", pady=(0, 10))
        list_frame = tk.Frame(
            device_frame, bg=self.colors["bg_secondary"], bd=1, relief="solid"
        )
        list_frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(list_frame, bg=self.colors["bg_accent"])
        scrollbar.pack(side="right", fill="y")
        self.device_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg=self.colors["bg_secondary"],
            fg=self.colors["text_primary"],
            selectbackground=self.colors["neon_cyan"],
            selectforeground=self.colors["bg_primary"],
            font=("Consolas", 9),
            bd=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.device_listbox.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar.config(command=self.device_listbox.yview)
        # 设备信息显示
        best_device_index = None
        best_device = self.find_best_matching_device(devices)

        for i, device in enumerate(devices):
            name_short = (
                device["name"].split("\\")[-1]
                if "\\" in device["name"]
                else device["name"]
            )
            # 显示更详细的设备信息
            display_text = f"{i:2d}. {device['description']}"
            if 'address' in device and device['address']:
                display_text += f" | IP: {device['address']}"

            # 标记推荐的设备
            if best_device and device == best_device:
                display_text += " ★ 推荐"
                best_device_index = i

            if len(display_text) > 85:
                display_text = display_text[:82] + "..."
            self.device_listbox.insert(tk.END, display_text)

        # 自动选择推荐的设备，如果没有则选择第一个
        if best_device_index is not None:
            self.device_listbox.selection_set(best_device_index)
            self.device_listbox.see(best_device_index)  # 确保选中的项可见
            print(f"自动选择推荐设备: {best_device['description']}")
        elif devices:
            self.device_listbox.selection_set(0)
        # 添加帮助信息
        help_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        help_frame.pack(fill="x", padx=20, pady=(0, 10))

        help_text = ("💡 提示：\n"
                     "• ★ 标记的设备是程序自动检测的活动网卡(推荐)\n"
                     "• 程序已自动选择当前连接到互联网的网卡\n"
                     "• 以太网通常比WiFi更稳定\n"
                     "• 如果自动选择不正确，可手动选择其他设备\n"
                     "• 程序会自动检测游戏服务器连接")
        help_label = self.create_styled_label(
            help_frame, help_text, font_size=8, color="text_accent"
        )
        help_label.pack(anchor="w")

        # 日志级别配置
        log_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        log_frame.pack(fill="x", padx=20, pady=10)
        log_label = self.create_styled_label(
            log_frame, "◊ 日志级别设置:", font_size=12, color="neon_purple"
        )
        log_label.pack(anchor="w")
        log_option_frame = tk.Frame(log_frame, bg=self.colors["bg_primary"])
        log_option_frame.pack(fill="x", pady=(5, 0))
        self.log_level_var = tk.StringVar(value="info")
        info_radio = tk.Radiobutton(
            log_option_frame,
            text="Info (推荐) - 显示基本伤害信息",
            variable=self.log_level_var,
            value="info",
            bg=self.colors["bg_primary"],
            fg=self.colors["text_primary"],
            selectcolor=self.colors["bg_accent"],
            activebackground=self.colors["bg_primary"],
            activeforeground=self.colors["neon_green"],
            font=("Consolas", 9),
        )
        info_radio.pack(anchor="w")
        debug_radio = tk.Radiobutton(
            log_option_frame,
            text="Debug (详细) - 显示详细调试信息",
            variable=self.log_level_var,
            value="debug",
            bg=self.colors["bg_primary"],
            fg=self.colors["text_primary"],
            selectcolor=self.colors["bg_accent"],
            activebackground=self.colors["bg_primary"],
            activeforeground=self.colors["neon_green"],
            font=("Consolas", 9),
        )
        debug_radio.pack(anchor="w", pady=(5, 0))
        status_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        status_frame.pack(fill="x", padx=20, pady=(0, 10))
        status_text = "状态: 等待用户选择设备... | 快捷键: Enter确认, Escape取消"
        self.status_label = self.create_styled_label(
            status_frame, status_text, font_size=8, color="text_accent"
        )
        self.status_label.pack()
        button_frame = tk.Frame(main_frame, bg=self.colors["bg_primary"])
        button_frame.pack(fill="x", padx=20, pady=(5, 20))
        confirm_btn = self.create_styled_button(
            button_frame, "◊ 确认启动 ◊", self.on_confirm, width=15
        )
        confirm_btn.pack(side="left", padx=(0, 10))
        cancel_btn = self.create_styled_button(
            button_frame, "◊ 取消 ◊", self.on_cancel, width=15
        )
        cancel_btn.pack(side="left")
        exit_btn = self.create_styled_button(
            button_frame, "◊ 退出 ◊", self.on_exit, width=15
        )
        exit_btn.pack(side="right")
        self.center_window()
        self.start_rgb_animation()
        self.device_listbox.bind("<Double-1>", lambda e: self.on_confirm())
        self.device_listbox.bind("<<ListboxSelect>>", self.on_device_select)
        self.root.bind("<Return>", lambda e: self.on_confirm())
        self.root.bind("<Escape>", lambda e: self.on_cancel())

        # 添加窗口关闭协议处理
        def on_window_close():
            self.stop_rgb_animation()
            self.selected_device = None
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass

        self.root.protocol("WM_DELETE_WINDOW", on_window_close)
        self.device_listbox.focus_set()
        self.devices = devices

        try:
            self.root.mainloop()
        except tk.TclError:
            # 处理窗口已被销毁的情况
            pass

        return self.selected_device, self.log_level_var.get()

    def on_device_select(self, event):
        """当设备被选择时显示详细信息"""
        selection = self.device_listbox.curselection()
        if selection:
            device_index = selection[0]
            device = self.devices[device_index]

            # 构建详细状态信息
            status_parts = [
                f"已选择: {device['description'][:50]}{'...' if len(device['description']) > 50 else ''}",
            ]

            # 处理设备名（避免f-string中的反斜杠）
            device_name = device['name']
            if '\\' in device_name:
                device_name_short = device_name.split('\\')[-1]
            else:
                device_name_short = device_name
            status_parts.append(f"设备名: {device_name_short}")

            if 'address' in device and device['address']:
                status_parts.append(f"IP地址: {device['address']}")

            if 'netmask' in device and device['netmask']:
                status_parts.append(f"子网掩码: {device['netmask']}")

            status_parts.append("按Enter确认启动")
            status_text = " | ".join(status_parts)

            # 如果状态文本太长，进行换行显示
            if len(status_text) > 100:
                status_text = "\n".join(
                    status_parts[:2]) + "\n" + " | ".join(status_parts[2:])

            self.status_label.configure(text=status_text)

    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")

    def on_confirm(self):
        selection = self.device_listbox.curselection()
        if not selection:
            self.status_label.configure(text="⚠️ 请选择一个网络设备！")
            return
        device_index = selection[0]
        self.selected_device = self.devices[device_index]
        self.stop_rgb_animation()
        # 立即销毁窗口
        try:
            self.root.quit()  # 退出mainloop
            self.root.destroy()
        except:
            pass

    def on_cancel(self):
        self.selected_device = None
        self.stop_rgb_animation()
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass

    def on_exit(self):
        self.selected_device = "EXIT"
        self.stop_rgb_animation()
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
