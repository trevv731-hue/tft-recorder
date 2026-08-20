# TFT 战绩统计助手 (TFT Record Assistant)

> 一款专为云顶之弈（Teamfight Tactics）玩家设计的本地桌面工具，自动记录对局数据、统计分析走势、查询对手情报、提供海克斯强化评级参考。

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## ✨ 核心功能

### 1. 📊 战绩自动记录
- 通过 **League Client Update (LCU)** 本地接口自动检测对局结束
- 自动录入每场对局的名次、阵容、装备、海克斯等数据
- 数据存储在本地 **SQLite** 数据库，不上传任何服务器

### 2. 📈 数据统计分析
- 赛季对局数、平均名次、登顶率（吃鸡率）、前四率
- 名次走势曲线、段位走势曲线
- 单场 / 每日汇总双维度视图
- 支持 CSV 导出和数据库备份

### 3. 👥 对手情报查询
- 对局中实时查询对手的最近战绩和常用阵容
- 显示对手段位、近10局平均名次、吃鸡数
- **国服**通过腾讯 SGP 接口查询
- **外服**通过 Riot 官方 API 查询（需配置 API Key）

### 4. 🔮 海克斯强化评级
- 海克斯选择界面悬浮显示 **S/A/B/C/D** 评级
- 基于社区 tier list（datatft.com）数据
- 支持中文游戏界面（OCR 中文识别）
- 评级标签悬浮在每个海克斯卡片上方，不遮挡游戏操作

### 5. 🃏 全局牌库统计
- 实时统计自己和对手场上的棋子数量
- 计算牌池剩余数量，辅助追三星决策
- 三星预警提醒

---

## 🛠 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Python 3.8+ |
| 前端 UI | HTML / CSS / JavaScript (eel) |
| 悬浮窗 | tkinter (全屏透明置顶窗口) |
| 系统托盘 | pystray |
| 数据库 | SQLite3 |
| 游戏接口 | LCU (League Client Update) REST API |
| 截屏 | mss / PIL |
| OCR | Tesseract OCR (中文简体 + 英文) |
| 对手数据 | 腾讯 SGP (国服) / Riot 官方 API (外服) |

---

## 📦 安装与使用

### 环境要求
- Windows 10/11
- Python 3.8 或更高版本
- 英雄联盟客户端（国服或外服）

### 安装步骤

1. **克隆仓库**
```bash
git clone https://github.com/trevv731-hue/tft-recorder.git
cd tft-recorder
```

2. **安装 Python 依赖**
```bash
pip install eel pystray requests pillow mss pytesseract psutil
```

3. **安装 Tesseract OCR（海克斯评级功能需要）**
   - 下载：https://github.com/UB-Mannheim/tesseract/wiki
   - 安装时勾选 **Chinese (Simplified)** 语言包
   - 或将 `chi_sim.traineddata` 放入项目 `tessdata/` 目录

4. **配置 Riot API Key（外服对手情报需要，国服可跳过）**
   - 前往 https://developer.riotgames.com 获取 API Key
   - 启动应用后在侧边栏「Riot API 设置」中粘贴保存
   - 个人开发 Key 24小时过期，可在 UI 中随时更新

5. **启动应用**
```bash
python app.py
```

### 打包为 EXE
```bash
pip install pyinstaller
pyinstaller 战绩统计.spec
```
打包产物在 `dist/` 目录。

---

## 🎮 使用说明

### 战绩记录
1. 启动应用后，点击「读取当前客户端」连接英雄联盟
2. 应用自动检测对局结束并录入战绩
3. 在主面板查看统计数据和走势曲线

### 对手情报
- 进入对局后，应用自动查询对手情报
- 在「实时」面板查看对手段位、最近战绩、常用阵容
- 国服自动使用 SGP，外服使用 Riot API

### 海克斯评级
1. 进入海克斯选择界面（2-1 / 3-2 / 4-2）
2. 右键系统托盘图标 → 「海克斯评级」→ 选择当前阶段
3. 悬浮窗显示每个海克斯的 S/A/B/C/D 评级
4. 选择完毕后自动关闭，或手动点 X 关闭

---

## 📁 项目结构

```
tft-recorder/
├── app.py              # 主程序 (LCU连接、数据库、eel服务、托盘)
├── augments.py         # 海克斯评级数据 (中文→S/A/B/C/D)
├── augment_ocr.py      # 海克斯OCR识别 (截屏+Tesseract)
├── augment_overlay.py  # 海克斯评级悬浮窗 (tkinter透明置顶)
├── overlay.py          # 记牌器悬浮窗
├── web/
│   └── index.html      # 主面板UI (统计、图表、设置)
├── icons/              # 英雄头像资源
├── tessdata/           # OCR语言包 (需自行放置)
├── tft_assistant.db    # 本地数据库 (运行后生成, 已gitignore)
├── config.json         # 配置文件 (含API Key, 已gitignore)
├── 战绩统计.spec        # PyInstaller打包配置
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🔒 隐私与安全

- **所有数据仅存储在用户本地设备**，不上传到任何服务器
- **不与第三方共享**任何用户数据
- Riot API Key 加密存储在本地 `config.json`，仅用于调用 Riot 官方接口
- 本工具为**非商业个人项目**，遵循 Riot Games API 使用条款

---

## 📄 License

[MIT License](LICENSE)

---

## ⚠️ 免责声明

本项目与 Riot Games 无任何关联。League of Legends 和 Teamfight Tactics 是 Riot Games, Inc. 的商标。本工具仅用于学习和个人数据分析目的，不保证任何游戏内表现提升。
