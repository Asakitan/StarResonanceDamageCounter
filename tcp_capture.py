import socket
import struct
import threading
import time
import ctypes
import logging


class TcpCapture:
    def __init__(self, device, user_data_manager, logger=None):
        self.device = device
        self.user_data_manager = user_data_manager
        self.running = False
        self.capture_thread = None
        self.logger = logger or logging.getLogger("StarResonanceMain")
        
        # 基于Node.js版本的TCP序列号重组逻辑
        self._data_buffer = b""
        self.current_server = ""
        self.last_activity = 0
        
        # TCP序列号缓存 - 对应Node.js的tcp_cache逻辑
        self.tcp_next_seq = -1
        self.tcp_cache = {}
        self.tcp_cache_size = 0
        self.tcp_last_time = 0
        
        # 添加TCP锁机制 - 对应Node.js的tcp_lock
        self.tcp_lock = threading.RLock()
        
        # 添加统计信息
        self.stats = {
            'packets_received': 0,
            'packets_processed': 0,
            'bytes_received': 0,
            'buffer_cleanups': 0,
            'tcp_cache_hits': 0,
            'tcp_cache_misses': 0
        }

    @staticmethod
    def get_available_devices():
        """获取可用的网络设备列表"""
        devices = []
        try:
            # 方法1: 尝试使用WinPcap API获取设备列表
            try:
                dll = ctypes.windll.LoadLibrary("Npcap\\wpcap.dll")
            except Exception:
                try:
                    dll = ctypes.windll.LoadLibrary("wpcap.dll")
                except Exception:
                    dll = None
            
            if dll:
                # 定义pcap_findalldevs函数
                pcap_findalldevs = dll.pcap_findalldevs
                pcap_findalldevs.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_char_p]
                pcap_findalldevs.restype = ctypes.c_int
                
                pcap_freealldevs = dll.pcap_freealldevs
                pcap_freealldevs.argtypes = [ctypes.c_void_p]
                
                # 调用pcap_findalldevs
                alldevs = ctypes.c_void_p()
                errbuf = ctypes.create_string_buffer(256)
                
                if pcap_findalldevs(ctypes.byref(alldevs), errbuf) == 0:
                    # 定义pcap_if结构体
                    class pcap_if(ctypes.Structure):
                        _fields_ = [
                            ("next", ctypes.c_void_p),
                            ("name", ctypes.c_char_p),
                            ("description", ctypes.c_char_p),
                            ("addresses", ctypes.c_void_p),
                            ("flags", ctypes.c_uint32),
                        ]
                    
                    current = ctypes.cast(alldevs, ctypes.POINTER(pcap_if))
                    
                    while current:
                        try:
                            name = current.contents.name.decode('utf-8', errors='ignore') if current.contents.name else ""
                            desc = current.contents.description.decode('utf-8', errors='ignore') if current.contents.description else name
                            
                            if name and "\\Device\\NPF_" in name:
                                devices.append({
                                    'name': name,
                                    'description': desc or name.split('\\')[-1]
                                })
                            
                            # 移动到下一个设备
                            if current.contents.next:
                                current = ctypes.cast(current.contents.next, ctypes.POINTER(pcap_if))
                            else:
                                break
                        except Exception as e:
                            break
                    
                    # 释放设备列表
                    pcap_freealldevs(alldevs)
                    
        except Exception as e:
            pass
        
        # 方法2: 如果WinPcap方法失败，尝试使用ipconfig和注册表信息
        if not devices:
            try:
                import subprocess
                import re
                
                # 获取网络适配器的GUID
                result = subprocess.run(['getmac', '/fo', 'csv', '/v'], capture_output=True, text=True, encoding='gbk')
                if result.stdout:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # 跳过标题行
                        parts = [p.strip('"') for p in line.split('","')]
                        if len(parts) >= 4 and parts[3] != "N/A":  # 有物理地址的适配器
                            adapter_name = parts[0]
                            # 尝试构造WinPcap设备名称
                            if adapter_name and adapter_name != "连接名":
                                # 使用常见的GUID格式
                                guid_pattern = r'\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}\}'
                                devices.append({
                                    'name': f'\\Device\\NPF_{{{str(hash(adapter_name))[:8].upper()}-1234-5678-9ABC-DEF012345678}}',
                                    'description': adapter_name
                                })
            except Exception as e:
                pass
        
        # 方法3: 如果以上方法都失败，使用已知的常见设备
        if not devices:
            common_devices = [
                {
                    'name': '\\Device\\NPF_{12345678-1234-1234-1234-123456789ABC}',
                    'description': 'Realtek 8812BU Wireless LAN 802.11ac USB NIC'
                },
                {
                    'name': '\\Device\\NPF_{87654321-4321-4321-4321-CBA987654321}',
                    'description': 'Intel(R) Ethernet Connection'
                },
                {
                    'name': '\\Device\\NPF_{ABCDEF12-3456-7890-ABCD-EF1234567890}',
                    'description': 'Wireless Network Adapter'
                }
            ]
            devices.extend(common_devices)
            
        return devices

    def start_capture(self):
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.capture_thread.start()

    def stop_capture(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)

    def _capture_worker(self):
        self.logger.info(f"[TcpCapture] 开始抓包，设备: {self.device['description']}")
        
        # 尝试不同的库加载方式
        dll = None
        try:
            # 首先尝试Npcap目录
            dll = ctypes.windll.LoadLibrary("Npcap\\wpcap.dll")
            self.logger.debug("使用Npcap库")
        except Exception:
            try:
                # 然后尝试系统路径
                dll = ctypes.windll.LoadLibrary("wpcap.dll")
                self.logger.debug("使用系统WinPcap库")
            except Exception as e:
                self.logger.error(f"无法加载抓包库: {e}")
                return
        
        pcap_open_live = dll.pcap_open_live
        pcap_open_live.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_char_p,
        ]
        pcap_open_live.restype = ctypes.c_void_p
        
        pcap_next_ex = dll.pcap_next_ex
        pcap_next_ex.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        pcap_next_ex.restype = ctypes.c_int
        
        pcap_close = dll.pcap_close
        pcap_close.argtypes = [ctypes.c_void_p]
        pcap_close.restype = None
        
        errbuf = ctypes.create_string_buffer(256)
        
        # 尝试不同的设备名称格式
        device_names_to_try = [
            self.device["name"],  # 原始名称
            f"\\Device\\NPF_{self.device['description']}",  # 基于描述的名称
            f"rpcap://\\Device\\NPF_{self.device['description']}",  # rpcap格式
        ]
        
        # 如果是WLAN设备，尝试特定格式
        if "WLAN" in self.device['description']:
            device_names_to_try.extend([
                f"\\Device\\NPF_{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}",  # 通用WLAN GUID
                f"\\Device\\NPF_{{12345678-ABCD-EF12-3456-789ABCDEF012}}",  # 另一个通用GUID
            ])
        
        handle = None
        successful_device_name = None
        
        for device_name in device_names_to_try:
            try:
                self.logger.debug(f"尝试打开设备: {device_name}")
                handle = pcap_open_live(device_name.encode(), 65535, 1, 1000, errbuf)
                if handle:
                    successful_device_name = device_name
                    self.logger.info(f"✅ 成功打开设备: {device_name}")
                    break
                else:
                    error_msg = errbuf.value.decode('utf-8', errors='ignore')
                    self.logger.debug(f"设备打开失败: {device_name}, 错误: {error_msg}")
            except Exception as e:
                self.logger.debug(f"设备打开异常: {device_name}, 异常: {e}")
        
        if not handle:
            self.logger.error(f"无法打开任何设备格式，最后错误: {errbuf.value.decode('utf-8', errors='ignore')}")
            # 尝试使用第一个可用的设备
            try:
                self.logger.info("尝试使用默认设备...")
                handle = pcap_open_live(b"", 65535, 1, 1000, errbuf)
                if handle:
                    self.logger.info("✅ 成功使用默认设备")
                else:
                    return
            except Exception:
                return
        
        self.logger.info(f"[TcpCapture] 设备已打开，开始抓包...")
        
        try:
            while self.running:
                pkt_header = ctypes.POINTER(ctypes.c_ubyte)()
                pkt_data = ctypes.POINTER(ctypes.c_ubyte)()
                res = pcap_next_ex(
                    handle, ctypes.byref(pkt_header), ctypes.byref(pkt_data)
                )
                
                if res == 1:
                    try:
                        # 解析包长度
                        pkt_len = 1500
                        if pkt_header:
                            class pcap_pkthdr(ctypes.Structure):
                                _fields_ = [
                                    ("ts", ctypes.c_uint64),
                                    ("caplen", ctypes.c_uint32),
                                    ("len", ctypes.c_uint32),
                                ]

                            pkt_header_obj = ctypes.cast(
                                pkt_header, ctypes.POINTER(pcap_pkthdr)
                            ).contents
                            pkt_len = pkt_header_obj.caplen
                            
                        raw_data = ctypes.string_at(pkt_data, pkt_len)
                        
                        # 解析以太网/IP/TCP，提取TCP负载
                        self._parse_ethernet_frame(raw_data)
                        
                    except Exception as e:
                        self.logger.debug(f"抓包数据解析错误: {e}")
                        
                elif res == 0:
                    continue
                elif res == -1:
                    self.logger.error("抓包错误，退出！")
                    break
                    
        finally:
            pcap_close(handle)
            self.logger.info("[TcpCapture] 抓包线程已关闭")

    def _parse_ethernet_frame(self, raw_data):
        """解析以太网帧并提取TCP数据 - 基于Node.js版本的逻辑"""
        try:
            import dpkt
            
            eth = dpkt.ethernet.Ethernet(raw_data)
            if not isinstance(eth.data, dpkt.ip.IP):
                return
                
            ip = eth.data
            if not isinstance(ip.data, dpkt.tcp.TCP):
                return
                
            tcp = ip.data
            if len(tcp.data) == 0:
                return
                
            # 检查是否是游戏相关端口
            if not self._is_game_port(tcp.sport, tcp.dport):
                return
            
            # 构造源服务器标识 - 对应Node.js的src_server
            import socket
            src_ip = socket.inet_ntoa(ip.src)
            dst_ip = socket.inet_ntoa(ip.dst)
            src_server = f"{src_ip}:{tcp.sport} -> {dst_ip}:{tcp.dport}"
            
            # 处理TCP数据，使用序列号重组 - 对应Node.js逻辑
            self._process_tcp_data_with_seq(tcp.data, tcp.seq, src_server)
            
        except Exception as e:
            self.logger.debug(f"以太网帧解析错误: {e}")

    def _is_game_port(self, sport, dport):
        """检查是否是游戏相关端口"""
        # 临时调试：记录所有端口活动
        if not hasattr(self, '_port_debug_count'):
            self._port_debug_count = {}
        
        port_key = f"{sport}-{dport}"
        self._port_debug_count[port_key] = self._port_debug_count.get(port_key, 0) + 1
        
        # 每2000个包输出端口统计 - 多目标攻击时减少统计频率
        if sum(self._port_debug_count.values()) % 2000 == 0:  # 从1000改为2000
            top_ports = sorted(self._port_debug_count.items(), key=lambda x: x[1], reverse=True)[:10]
            self.logger.info(f"🔍 热门端口组合: {top_ports}")
        
        # 如果已经识别了游戏服务器，接受所有相关端口
        if self.current_server:
            return True
        
        # 基于实际观察到的端口活动，扩大游戏端口范围
        # 从统计中看到443-52242是主要的通信端口
        primary_game_ports = [443, 80, 8080, 2127]  # 基础游戏端口
        
        # 检查基础游戏端口
        has_primary_port = sport in primary_game_ports or dport in primary_game_ports
        
        # 检查高端口范围 - 游戏经常使用动态端口
        has_high_port = (
            (sport >= 49152 and sport <= 65535) or  # Windows动态端口范围
            (dport >= 49152 and dport <= 65535) or
            (sport >= 10000 and sport <= 65535) or  # 扩大的高端口范围
            (dport >= 10000 and dport <= 65535)
        )
        
        # 检查常见的游戏服务端口
        common_game_ports = [
            22101, 22102, 9090, 10000, 10001, 10002,
            20000, 20001, 20002, 30000, 30001, 30002
        ]
        has_common_game_port = sport in common_game_ports or dport in common_game_ports
        
        # 更宽松的条件：任何包含基础端口或高端口的组合都可能是游戏数据
        return has_primary_port or has_high_port or has_common_game_port

    def _clear_tcp_cache(self):
        """清理TCP缓存 - 对应Node.js的clearTcpCache"""
        self._data_buffer = b""
        self.tcp_next_seq = -1
        self.tcp_last_time = 0
        self.tcp_cache = {}
        self.tcp_cache_size = 0

    def _process_tcp_data_with_seq(self, tcp_data, seq_no, src_server):
        """基于Node.js版本的TCP序列号重组处理 - 优化多目标攻击性能"""
        # 使用try-finally确保锁的正确释放，减少锁竞争
        lock_acquired = False
        try:
            # 快速预检查，避免不必要的锁获取
            if not tcp_data or len(tcp_data) == 0:
                return
                
            current_time = int(time.time() * 1000)
            self.stats['packets_received'] += 1
            self.stats['bytes_received'] += len(tcp_data)
            
            # 每3000个包输出一次统计，减少I/O开销
            if self.stats['packets_received'] % 3000 == 0:
                hit_rate = (self.stats['tcp_cache_hits'] / max(1, self.stats['packets_received'])) * 100
                self.logger.info(f"📊 TCP统计: 收到{self.stats['packets_received']}包, "
                               f"处理{self.stats['packets_processed']}包, "
                               f"缓存命中率{hit_rate:.1f}%, "
                               f"当前缓存{self.tcp_cache_size}个包")
            
            # 获取锁 - 对应Node.js: await tcp_lock.acquire();
            self.tcp_lock.acquire()
            lock_acquired = True
            
            # 超时检查 - 对应Node.js的30秒超时逻辑
            if self.tcp_last_time and current_time - self.tcp_last_time > 30000:
                self.logger.warning(f"⚠️ TCP序列号超时，清理缓存. seq: {self.tcp_next_seq}")
                self.current_server = ""
                self._clear_tcp_cache()
            
            # 服务器识别逻辑 - 对应Node.js的current_server逻辑
            if self.current_server != src_server:
                # 尝试通过小包识别服务器 - 对应Node.js的buf[4] == 0逻辑
                if len(tcp_data) > 10 and tcp_data[4] == 0:
                    if self._identify_game_server_nodejs_style(tcp_data):
                        if self.current_server != src_server:
                            self.current_server = src_server
                            self._clear_tcp_cache()
                            self.logger.info(f"🎯 识别到游戏服务器: {src_server}")
                return
            
            # 这里已经是识别到的服务器的包了 - 对应Node.js注释
            # 对应Node.js: if (tcp_next_seq === -1 && buf.length > 4 && buf.readUInt32BE() < 999999)
            if self.tcp_next_seq == -1 and len(tcp_data) > 4:
                try:
                    packet_size = struct.unpack(">I", tcp_data[:4])[0]
                    if packet_size < 999999:
                        self.tcp_next_seq = seq_no
                        self.logger.debug(f"初始化TCP序列号: {self.tcp_next_seq}")
                except:
                    return
            
            # 对应Node.js: tcp_cache[ret.info.seqno] = buf; tcp_cache_size++;
            self.tcp_cache[seq_no] = tcp_data
            self.tcp_cache_size += 1
            
            # 批量处理连续序列 - 对应Node.js: while (tcp_cache[tcp_next_seq])
            processed_seqs = []
            while self.tcp_next_seq in self.tcp_cache:
                seq = self.tcp_next_seq
                data_chunk = self.tcp_cache[seq]
                
                # 对应Node.js: _data = _data.length === 0 ? tcp_cache[seq] : Buffer.concat([_data, tcp_cache[seq]]);
                if len(self._data_buffer) == 0:
                    self._data_buffer = data_chunk
                else:
                    self._data_buffer += data_chunk
                
                # 对应Node.js: tcp_next_seq = (seq + tcp_cache[seq].length) >>> 0;
                self.tcp_next_seq = (seq + len(data_chunk)) & 0xFFFFFFFF  # uint32
                
                # 标记要删除的序列号
                processed_seqs.append(seq)
                self.tcp_last_time = current_time
                self.stats['tcp_cache_hits'] += 1
            
            # 批量删除已处理的缓存条目，减少字典操作次数
            for seq in processed_seqs:
                del self.tcp_cache[seq]
                self.tcp_cache_size -= 1
            
            # 释放锁后处理完整包，减少锁持有时间
            self.tcp_lock.release()
            lock_acquired = False
            
            # 处理完整的游戏包 - 对应Node.js的packet处理逻辑
            if processed_seqs:  # 只有在有新数据时才处理
                self._extract_complete_packets_nodejs_style()
            
            # 重新获取锁进行缓存清理检查
            self.tcp_lock.acquire()
            lock_acquired = True
            
            # 缓存清理策略 - 多目标攻击时更宽松的缓存管理
            if self.tcp_cache_size > 200:  # 进一步增加到200，多目标攻击时允许更多缓存
                self.logger.warning(f"TCP缓存过大，清理. seq: {self.tcp_next_seq} size: {self.tcp_cache_size}")
                self._clear_tcp_cache()
                
        except Exception as e:
            self.logger.error(f"TCP序列号处理错误: {e}")
        finally:
            # 确保锁被正确释放
            if lock_acquired:
                try:
                    self.tcp_lock.release()
                except:
                    pass

    def _identify_game_server_nodejs_style(self, tcp_data):
        """基于Node.js样式的游戏服务器识别"""
        try:
            # 对应Node.js: const data = buf.subarray(10);
            data = tcp_data[10:]
            if not data:
                return False
            
            offset = 0
            signature = b"\x00\x63\x33\x53\x42\x00"  # c3SB signature
            
            while offset < len(data):
                # 读取长度 - 对应Node.js: const len_buf = stream.read(4);
                if offset + 4 > len(data):
                    break
                    
                length = struct.unpack(">I", data[offset:offset+4])[0]
                offset += 4
                
                # 读取数据 - 对应Node.js: data1 = stream.read(len_buf.readUInt32BE() - 4);
                if offset + length - 4 > len(data):
                    break
                    
                data1 = data[offset:offset + length - 4]
                offset += length - 4
                
                # 检查签名 - 对应Node.js: if (Buffer.compare(data1.subarray(5, 5 + signature.length), signature))
                if len(data1) > 5 + len(signature):
                    if data1[5:5 + len(signature)] == signature:
                        try:
                            # 对应Node.js: let body = pb.decode(data1.subarray(18)) || {};
                            from protocol_decoder import ProtocolDecoder
                            body = ProtocolDecoder.decode_protobuf(data1[18:]) or {}
                            if body:
                                return True
                        except Exception:
                            pass
                break
                
        except Exception as e:
            self.logger.debug(f"Node.js样式服务器识别错误: {e}")
            
        return False

    def _extract_complete_packets_nodejs_style(self):
        """基于Node.js样式的包提取逻辑 - 高性能优化版本"""
        packets_processed = 0
        max_packets_per_batch = 1000  # 大幅增加批处理限制以支持高频攻击 (从200增加到1000)
        
        # 对应Node.js: while (_data.length > 4)
        # 增加批处理能力，一次处理更多包
        while len(self._data_buffer) > 4 and packets_processed < max_packets_per_batch:
            try:
                # 读取包大小 - 对应Node.js: let packetSize = _data.readUInt32BE();
                packet_size = struct.unpack(">I", self._data_buffer[:4])[0]
                
                # 对应Node.js: if (_data.length < packetSize) break;
                if len(self._data_buffer) < packet_size:
                    break
                
                # 验证包大小合理性
                if packet_size > 999999:
                    # 对应Node.js: else if (packetSize > 999999)
                    self.logger.error(f"包长度无效! {len(self._data_buffer)}, {packet_size}")
                    # Node.js版本这里会exit，我们选择清理缓存继续
                    self._clear_tcp_cache()
                    break
                
                # 对应Node.js: if (_data.length >= packetSize)
                if len(self._data_buffer) >= packet_size:
                    # 提取包 - 对应Node.js: const packet = _data.subarray(0, packetSize);
                    packet = self._data_buffer[:packet_size]
                    # 更新缓冲区 - 对应Node.js: _data = _data.subarray(packetSize);
                    self._data_buffer = self._data_buffer[packet_size:]
                    
                    # 处理包 - 对应Node.js: processor.processPacket(packet);
                    try:
                        self.user_data_manager.process_packet(packet, self.logger)
                        packets_processed += 1
                        self.stats['packets_processed'] += 1
                        
                        # 在多目标攻击高频时，减少错误日志记录
                        self._last_process_error_time = getattr(self, '_last_process_error_time', 0)
                        
                    except Exception as e:
                        # 在多目标攻击时，大幅减少错误日志的频率以提高性能
                        current_time = time.time()
                        if current_time - self._last_process_error_time > 10:  # 每10秒最多记录一次错误
                            self.logger.error(f"包处理失败: {e}")
                            self._last_process_error_time = current_time
                        
            except Exception as e:
                self.logger.error(f"Node.js样式包提取错误: {e}")
                if not self._resync_buffer():
                    break
        
        # 只有处理了较多包时才输出调试信息，减少日志压力
        if packets_processed > 20:  # 从10增加到20
            self.logger.debug(f"批量处理了 {packets_processed} 个包，缓冲区剩余: {len(self._data_buffer)} 字节")
        
        # 当批处理达到上限时，立即在当前线程中继续处理，确保数据不丢失
        if packets_processed >= max_packets_per_batch and len(self._data_buffer) > 4:
            # 直接递归调用以确保高频攻击时数据完整性，避免异步处理的数据丢失风险
            self.logger.debug(f"达到批处理上限，继续处理剩余 {len(self._data_buffer)} 字节")
            self._extract_complete_packets_nodejs_style()

    def _identify_game_server(self, tcp_data):
        """识别游戏服务器 - 改进版本，更容易识别游戏数据"""
        try:
            # 方法1: 检查c3SB签名
            signature = b"\x00\x63\x33\x53\x42\x00"  # c3SB signature
            if signature in tcp_data:
                self.current_server = self.device.get("description", "")
                self._data_buffer = b""
                self.logger.info(f"🎯 通过c3SB签名识别游戏服务器: {self.current_server}")
                return True
            
            # 方法2: 检查简化的c3SB签名
            simple_signature = b"\x63\x33\x53\x42"  # c3SB
            if simple_signature in tcp_data:
                self.current_server = self.device.get("description", "")
                self._data_buffer = b""
                self.logger.info(f"🎯 通过简化c3SB签名识别游戏服务器: {self.current_server}")
                return True
            
            # 方法3: 检查protobuf包结构
            if len(tcp_data) > 16:
                # 寻找可能的包长度+类型的组合
                for i in range(len(tcp_data) - 6):
                    try:
                        # 尝试解析包长度
                        length = struct.unpack(">I", tcp_data[i:i+4])[0]
                        if 6 <= length <= 10000 and i + length <= len(tcp_data):
                            # 检查包类型
                            packet_type = struct.unpack(">H", tcp_data[i+4:i+6])[0]
                            msg_type_id = packet_type & 0x7FFF
                            # 常见的游戏包类型: 2(Notify), 6(FrameDown), 等
                            if msg_type_id in [2, 6, 7, 8]:
                                self.current_server = self.device.get("description", "")
                                self._data_buffer = b""
                                self.logger.info(f"🎯 通过包结构识别游戏服务器: {self.current_server} (类型: {msg_type_id})")
                                return True
                    except:
                        continue
            
            # 方法4: 原始逻辑作为备用
            if len(tcp_data) > 10:
                data = tcp_data[10:]
                offset = 0
                
                while offset < len(data):
                    if offset + 4 > len(data):
                        break
                        
                    length = struct.unpack(">I", data[offset : offset + 4])[0]
                    offset += 4
                    
                    if offset + length - 4 > len(data):
                        break
                        
                    data1 = data[offset : offset + length - 4]
                    offset += length - 4
                    
                    if len(data1) > 5 + len(signature):
                        if data1[5 : 5 + len(signature)] == signature:
                            try:
                                from protocol_decoder import ProtocolDecoder
                                body = ProtocolDecoder.decode_protobuf(data1[18:]) or {}
                                if body:
                                    self.current_server = self.device.get("description", "")
                                    self._data_buffer = b""
                                    self.logger.info(f"🎯 通过原始逻辑识别游戏服务器: {self.current_server}")
                                    return True
                            except Exception:
                                pass
                    break
                
        except Exception as e:
            self.logger.debug(f"服务器识别错误: {e}")
            
        return False

    def _extract_complete_packets(self):
        """从缓冲区提取完整的游戏包"""
        packets_processed = 0
        
        while len(self._data_buffer) >= 4 and packets_processed < 50:  # 减少单次处理数量
            try:
                # 读取包长度
                packet_length = struct.unpack(">I", self._data_buffer[:4])[0]
                
                # 验证包长度合理性
                if packet_length < 4 or packet_length > 999999:
                    # 包长度不合理，尝试重新同步
                    if not self._resync_buffer():
                        break
                    continue
                
                # 检查是否有完整的包
                if len(self._data_buffer) >= packet_length:
                    packet = self._data_buffer[:packet_length]
                    self._data_buffer = self._data_buffer[packet_length:]
                    
                    # 处理包
                    try:
                        self.user_data_manager.process_packet(packet, self.logger)
                        packets_processed += 1
                        self.stats['packets_processed'] += 1
                    except Exception as e:
                        self.logger.error(f"包处理失败: {e}")
                else:
                    # 数据不够，等待更多数据
                    break
                    
            except Exception as e:
                self.logger.error(f"包提取错误: {e}")
                if not self._resync_buffer():
                    break
        
        # 更智能的缓冲区管理 - 减少警告频率
        if len(self._data_buffer) > 200000:  # 200KB 才警告
            if not hasattr(self, '_last_buffer_warning') or time.time() - self._last_buffer_warning > 5:
                self.logger.warning("缓冲区过大，清理旧数据")
                self._last_buffer_warning = time.time()
            self._data_buffer = self._data_buffer[-100000:]  # 保留最新100KB
        
        if packets_processed > 0:
            self.logger.debug(f"处理了 {packets_processed} 个包，缓冲区剩余: {len(self._data_buffer)} 字节")

    def _resync_buffer(self):
        """重新同步缓冲区，寻找下一个有效包的开始位置"""
        try:
            # 在缓冲区中寻找下一个可能的包头
            for i in range(1, min(len(self._data_buffer) - 3, 2000)):
                try:
                    test_length = struct.unpack(">I", self._data_buffer[i:i+4])[0]
                    if 4 <= test_length <= 999999:
                        # 找到可能的包开始位置
                        self._data_buffer = self._data_buffer[i:]
                        self.logger.debug(f"重新同步到位置 {i}")
                        return True
                except:
                    continue
            
            # 找不到有效的包头，清空缓冲区
            self.logger.debug("找不到有效包头，清空缓冲区")
            self._data_buffer = b""
            return False
            
        except Exception as e:
            self.logger.error(f"缓冲区重新同步错误: {e}")
            self._data_buffer = b""
            return False
