# 飞牛NAS与智能体中枢

> 把一台飞牛 fnOS NAS 跑成家庭 AI 中枢的完整资料库：
> **AstrBot / OpenClaw 双端协同**打底，**TDAI 统一记忆**打通三端长期记忆，
> 配套自建 AI 实操指南、fnOS 部署细节与网关破坏性升级复盘。

本文库全部内容均为**脱敏版本**：IP、Token、密钥、路径均已替换为占位符，
拿到后请先按自己的实际环境替换，再动手操作。

---

## 一、五个模块对照表

| 序号 | 目录 | 内容主题 | 原始仓库 | 适合谁看 |
|---|---|---|---|---|
| 01 | [`01_AstrBot与OpenClaw双端协同`](01_AstrBot与OpenClaw双端协同/) | 用 AstrBot + NapCat 在 NAS 上跑 QQ 机器人「鲸鱼娘」，再用一层极薄的 relay 桥把 QQ 指令转交给 OpenClaw 真执行 | `astrbot-openclaw-whale-guide` | 想让聊天机器人「不只是聊天、还能干活」的人 |
| 02 | [`02_TDAI统一记忆持久化`](02_TDAI统一记忆持久化/) | TencentDB Agent Memory（TDAI）三端共享记忆库完整部署与排错，含 L0→L3 分层蒸馏与「静默丢弃」故障的正解 | `tdai-unified-memory-guide` | 想让 NAS / Windows / WorkBuddy 三端共用一份长期记忆的人 |
| 03 | [`03_NAS自建AI实操指南`](03_NAS自建AI实操指南/) | 自托管 AI 工具栈的总索引与各子主题仓库导航 | `nas-selfhosted-ai-guides` | 刚上手自建 AI、需要一张地图的人 |
| 04 | [`04_飞牛fnOS部署指南`](04_飞牛fnOS部署指南/) | OpenClaw 在飞牛 fnOS 上的完整实践：安装、每日健康报告、微信通知、浏览器 CDP 接入 | `openclaw-fnOS-guide` | 已有一台飞牛 NAS、要落地 OpenClaw 的人 |
| 05 | [`05_网关破坏性升级复盘`](05_网关破坏性升级复盘/) | OpenClaw 网关双端（Windows + NAS）升级实证研究，以及破坏性变更下 QQ 通道失效的诊断与重装 | `openclaw-upgrade-empirical-study` | 要升级网关、怕踩破坏性变更坑的人 |

## 二、附加载物

| 路径 | 说明 |
|---|---|
| [`文档/版本迁移指引.md`](文档/版本迁移指引.md) | 五个旧仓库到本仓库中文目录的迁移映射关系与历史链接处理说明 |
| [`小AI/设备压力评估专家/SKILL.md`](小AI/设备压力评估专家/SKILL.md) | OpenClaw 运维技能卡：CPU / 内存 / 磁盘 / 带宽压力评估铁律与双端部署 |
| [`小AI/记忆沉淀助手/SKILL.md`](小AI/记忆沉淀助手/SKILL.md) | TDAI 记忆技能卡：L0→L3 四层记忆结构与落库校验流程 |

---

## 三、快速开始

### 推荐阅读顺序

1. **先看地图** —— [`03_NAS自建AI实操指南`](03_NAS自建AI实操指南/)，搞清楚整个自建 AI 工具栈由哪几块拼成。
2. **再落地底座** —— 按 [`04_飞牛fnOS部署指南`](04_飞牛fnOS部署指南/) 在你的 fnOS NAS 上把 OpenClaw 跑起来。
   - 关键提醒：OpenClaw 在 NAS 上是**用户级 systemd** 服务，**不要套 `sudo`**，否则配置会写进 root 目录导致读不到。
3. **然后接入口** —— 按 [`01_AstrBot与OpenClaw双端协同`](01_AstrBot与OpenClaw双端协同/) 搭 AstrBot + NapCat，再用 relay 桥把 QQ 指令转给 OpenClaw。
4. **最后通记忆** —— 按 [`02_TDAI统一记忆持久化`](02_TDAI统一记忆持久化/) 部署 TDAI，让三端共享同一份长期记忆。
5. **升级前必读** —— 动网关版本之前，先翻 [`05_网关破坏性升级复盘`](05_网关破坏性升级复盘/)，照着别人的坑少走弯路。

### 最低环境假设

- 一台飞牛 fnOS（或其他 Linux）NAS，能跑 Docker
- 一台 Windows 11 机器（可选，用于双端部署）
- 至少一个可用的大模型 API（云端或自建反代均可）

### 动手前的三条通用铁律

1. **先备份再改**。改配置、升版本前先 `cp` 一份，尤其是 `~/.config/openclaw/` 这类目录。
2. **密钥不进仓库**。所有 Token / API Key 只放本地配置文件，本文档中的占位符不要照抄。
3. **改完要验证**。每个模块都给了端到端验收步骤，别只看「命令返回 0」就当成功——
   TDAI 那类故障恰恰是「HTTP 200、模型也回复、但记忆根本没落库」。

---

## 四、免责声明

本仓库内容由 AI 生成并经过实测整理，**仅供参考**。
部署涉及你的 NAS、QQ 账号与各类 API Key，实操前请自行确认风险。
文中所有密钥与 Token 均已脱敏为占位符，真实值请以你本地配置文件为准。

## 五、许可

MIT License，详见 [LICENSE](LICENSE)。
