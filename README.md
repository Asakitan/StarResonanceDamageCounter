# Star Resonance Damage Counter

一款专为《星痕共鸣》设计的实时伤害统计工具，提供 Cyberpunk 2077 风格的可视化界面。

## 主要特性

- **实时伤害统计** - 精确捕获并显示团队和个人伤害数据
- **赛博朋克风格界面** - 炫酷的霓虹灯效果和RGB渐变动画
- **JASON阶段控制** - 智能战斗阶段管理，支持手动和自动推进
- **多种显示模式** - 支持普通模式、突出模式和计时器窗口
- **语音提醒系统** - TTS语音播报重要战斗事件
- **快捷键支持** - 丰富的快捷键操作，提升战斗体验
- **实时DPS统计** - 精确的每秒伤害输出统计

## 系统要求

### 必需依赖
- **Python 3.8+**
- **Node.js 14+** (如使用源码运行)
- **Windows 操作系统**

### Python依赖包
```bash
psutil>=5.8.0
requests>=2.28.0
Pillow>=9.5.0
keyboard>=0.13.0
pyttsx3>=2.90
```

## 快速开始

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/Asakitan/StarResonanceDamageCounter.git
cd StarResonanceDamageCounter
```

2. **安装Python依赖**
```bash
pip install -r requirements.txt
```

3. **安装Node.js依赖**
```bash
npm install
# 或使用 pnpm
pnpm install
```

### 运行程序

**方式一：使用Python启动器（推荐）**
```bash
python star_resonance_simplified.py
```

**方式二：分别启动服务器和UI**
```bash
# 终端1：启动后端服务器
node server.js

# 终端2：启动UI界面
python act_damage_ui.py
```

## 使用说明

### 启动流程

1. 运行程序后，首先选择网络设备（网卡）
2. 程序会自动启动后端服务器和UI界面
3. 进入游戏后，伤害数据将自动显示

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Prior` | 推进到下一阶段 |
| `Next` | 重置暴走时间 |
| `F1` | 跳转到第一阶段 |
| `F2` | 跳转到第二阶段 |
| `F3` | 跳转到第三阶段 |

### 配置文件

项目支持多种配置文件：

- `act_raid_config.json` - 主要的统一配置（推荐）
- `act_example_raid.json` - 示例配置
- `act_ICEDRAGON.json` - 冰龙副本配置
- `act_pvp_arena.json` - PVP竞技场配置
- `uid_mapping.json` - 玩家UID映射

## 项目结构

```
StarResonanceDamageCounter/
├── server.js                    # Node.js后端服务器
├── star_resonance_simplified.py # Python启动器
├── act_damage_ui.py            # UI界面主程序
├── tcp_capture.py              # 网络数据包捕获
├── device_selector.py          # 网络设备选择器
├── algo/                       # 数据包解析算法
│   ├── packet.js
│   ├── pb.js
│   └── blueprotobuf.js
├── public/                     # Web静态资源
├── fonts/                      # Orbitron字体文件
├── act_*.json                  # 配置文件
└── requirements.txt            # Python依赖
```

## 高级配置

### JASON阶段系统

支持三阶段战斗机制：
- **第一阶段（标准阶段）**：手动控制
- **第二阶段（特殊机制）**：手动控制
- **第三阶段（最终阶段）**：可在暴走前自动推进

### 伤害提醒

可在配置文件中设置：
- 团队总伤害里程碑提醒
- 个人DPS表现提醒
- 阶段转换提醒
- 时间节点提醒

## 故障排除

### 常见问题

**Q: 启动后无法捕获数据？**
- 检查是否选择了正确的网络设备
- 确认游戏正在运行
- 以管理员权限运行程序

**Q: UI界面字体显示异常？**
- 程序会自动安装Orbitron字体
- 如失败，手动安装`fonts/`目录下的字体文件

**Q: Node.js服务器启动失败？**
- 检查Node.js是否正确安装
- 运行 `npm install` 重新安装依赖
- 检查端口3000是否被占用

## 许可证

本项目采用 [MPL-2.0 License](LICENSE)

## 贡献者

- **原作者**: Dimole <dmlgzs@qq.com>
- **维护者**: Asakitan

## 致谢

感谢所有为本项目做出贡献的开发者和用户。

---

**注意**: 本工具仅用于个人学习和研究目的，请勿用于任何商业用途或违反游戏服务条款的行为。
