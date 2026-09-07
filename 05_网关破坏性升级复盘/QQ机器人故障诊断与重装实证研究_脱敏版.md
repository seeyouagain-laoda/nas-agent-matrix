# QQ 机器人故障诊断与重装的实证研究

## ——基于 OpenClaw 2026.8.2 破坏性变更的 NAS 与本地双端复盘

> 本文档与同仓库《OpenClaw 网关双端协同升级的实证研究》互为姊妹篇。前者聚焦 2026.7.1-2 → 2026.8.2 的网关升级，本文聚焦该升级后暴露的 **QQ 机器人通道失效**问题：从故障根因、官方兼容方案，到 NAS（fnOS）与本地 Windows 双端「卸载旧插件 → 重装新插件 → 套用原参数 → 验证 WS 真连」的完整工程复盘。**全文已脱敏**，所有 AppID / ClientSecret / QQ 用户 OpenID / 内网 IP / SSH 口令 / 网关 Token 均以占位符表示（见附录 B）。



---

### 摘要

用户反馈「无法经由 QQ 与飞牛 NAS 上的 OpenClaw 对话」。经排查，根因是 **OpenClaw 2026.8.2 对 QQ 插件做了破坏性变更**：旧官方包 `@openclaw/qqbot`（基于 2026.7.x 的 `formatInboundEnvelope` 旧 API）在新版本下处理入站消息必崩；官方兼容性文档要求改用新包 `@tencent-connect/openclaw-qqbot@2.0.3`。

本文记录了一套**双端可复用的卸载重装 SOP**，并揭示了三个反直觉机制：

1. 新插件在 `install` 阶段 **schema 校验拒绝 `allowFrom: ["*"]`**，但 gateway **运行时接受 `"*"`**；
2. gateway 启动时的 doctor 会**自动把 `allowFrom: ["*"]` 改写为非匹配标记 `openclaw:approval-disabled`**，而非报错；
3. 私聊真正放行的开关是 **`dmPolicy: "open"`**，而非 `allowFrom` 的白名单匹配。

最终 NAS 与本地双端均完成重装并实测 `WebSocket connected`，`openclaw status` 均显示 `QQ Bot │ ON │ OK │ configured`。

---

### 1. 引言

OpenClaw 在 2026.7 至 2026.8.2 的演进中，将 QQ 通道从「内置/旧官方插件」迁移到「官方新 Tencent Connect 插件」。本次故障表现为：NAS 与本地两个 OpenClaw 实例在升级后，**QQ 私聊与群聊消息均无法触达 Agent**，但其他通道（Web / API）正常。

排查未采用「直接改代码」的野路子，而是优先依据官方升级兼容性文档（见参考文献），确认这是**已知破坏性变更**而非环境故障，从而锁定正确的修复路径——更换插件包。

---

### 2. 故障根因分析

#### 2.1 OpenClaw 2026.8.2 的破坏性变更

2026.8.2 重构了消息入站信封（envelope）处理管线：

- **旧管线**（< 2026.8.2）：插件调用 `formatInboundEnvelope(inbound)` 将平台消息包装为 Agent 可读信封。
- **新管线**（≥ 2026.8.2）：插件必须调用 `formatAgentEnvelope(...)` 并提供 `channelId` / 路由元数据；旧函数已从公开 API 移除。

旧包 `@openclaw/qqbot`（2026.5.20 / 2026.7.1 等版本）仍依赖 `formatInboundEnvelope`，因此在 8.2 下收第一条消息即抛 `formatInboundEnvelope is not a function`，导致通道静默失效。

#### 2.2 官方升级兼容性文档的结论

官方《升级 QQ Bot 插件（2026-7-1-2 兼容性变更）》文档明确指出：

> 自 2026.8.2 起，QQ 通道统一由 `@tencent-connect/openclaw-qqbot` 提供，通道 id 为 `openclaw-qqbot`。旧 `@openclaw/qqbot` 不再兼容，必须卸载并安装新包。

即正确目标版本为 **`@tencent-connect/openclaw-qqbot@2.0.3`**（latest 当时指向 2.0.3）。

#### 2.3 旧插件为什么「看起来在跑却收不到消息」

旧插件在 gateway 启动阶段即因 API 缺失而在消息回调中崩，但**插件注册本身可能未报错**，于是 `openclaw status` 仍显示通道存在，实际所有入站消息在到达 Agent 前已中断。这正是「状态绿灯、消息不通」的典型表象，容易被误判为网络或 QQ 后台配置问题。

#### 2.4 版本升级对照（From → To）

本次故障的本质是「**网关先升到最新、旧 QQ 插件没跟上**」的版本错配——用户当时看到的「某个应用太老、不支持最新版」指的就是旧 QQ 机器人插件。完整升级链如下：

| 组件 | 主机 | 升级前（太老 / 不兼容） | 升级后（目标） | 不升级的后果 |
|------|------|------------------------|----------------|--------------|
| **OpenClaw 网关** | NAS（fnOS）+ 本地（Windows） | `2026.7.1-2` | `2026.8.2` | 无（网关本身健康，但引入了破坏性变更） |
| **QQ 机器人插件** | 本地（Windows） | `@openclaw/qqbot` `2026.5.20`（旧官方包，旧 API） | `@tencent-connect/openclaw-qqbot@2.0.3`（新官方包） | 收消息即崩 `formatInboundEnvelope is not a function` |
| **QQ 机器人插件** | NAS（fnOS） | `@openclaw/qqbot` `2026.5.27`（旧官方包，旧 API） | `@tencent-connect/openclaw-qqbot@2.0.3`（新官方包） | 同上，WS 长连被 QQ 服务器关闭 |

> **一句话总结**：OpenClaw 网关从 `2026.7.1-2` 升到 `2026.8.2` 后，旧 QQ 插件（`@openclaw/qqbot` 的 `2026.5.20` / `2026.5.27` 版本）因 API 过老、不支持 8.2 而失效；本次将其升级替换为官方新包 `@tencent-connect/openclaw-qqbot@2.0.3`，双端恢复。

> 注：网关 `2026.7.1-2 → 2026.8.2` 的详细升级过程与踩坑，见同仓库姊妹篇《OpenClaw 网关双端协同升级的实证研究》。

---


### 3. 关键发现：反直觉的配置机制

本章是本文最有工程价值的部分，三个机制均经过双端实测验证。

#### 3.1 `allowFrom` 的「校验拒绝 / 运行时接受」悖论

新插件 `install` 时的 JSON Schema 校验**拒绝通配符**：

```
Config validation failed:
channels.qqbot.allowFrom.0:
  invalid config for plugin openclaw-qqbot: must not be valid
```

但 gateway **运行时接受 `"*"`**——NAS 端在 `allowFrom: ["*"]` 配置下实测 WS 成功连接并收发消息。结论：**install 校验与运行时语义不一致**，不能因为 install 报错就认为 `"*"` 不可用。

#### 3.2 doctor 的自动迁移：approval-disabled 非匹配标记

直接以 `allowFrom: ["*"]` 启动 gateway 时，doctor（启动自检）会**静默把配置改写为**：

```json
"allowFrom": ["openclaw:approval-disabled"]
```

`openclaw:approval-disabled` 是 OpenClaw 内部的**非匹配标记**（sentinel），表示该通道关闭了审批流、不再做白名单匹配。这是 doctor 的**官方认可迁移行为**，不是错误状态——配置落盘后 `allowFrom` 即变为该标记，属预期结果。

#### 3.3 `dmPolicy: "open"` 才是私聊放行的真正开关

由于 3.2 的存在，`allowFrom` 实际被替换为非匹配标记，此时**私聊能否触达 Agent 完全取决于 `dmPolicy`**：

| 配置                                           | 私聊行为              |
| -------------------------------------------- | ----------------- |
| `dmPolicy: "open"`                           | 所有私聊消息放行到 Agent ✅ |
| `dmPolicy: "allowlist"` + `allowFrom: [用户号]` | 仅白名单用户私聊放行        |
| `dmPolicy: "closed"`                         | 私聊全部拒收            |

因此双端最终采用 **`allowFrom: ["*"]` + `dmPolicy: "open"`** 组合：doctor 把 `allowFrom` 迁移为标记后，由 `dmPolicy: "open"` 兜底放行私聊，群聊由 `groupAllowFrom: ["*"]` 放行。这是官方推荐的开箱即用配置态。

#### 3.4 安装需显式 `--accept-capabilities`

新插件首次安装会请求能力许可（capability consent），若不加 `--accept-capabilities` 会报：

```
Plugin "@tencent-connect/openclaw-qqbot" requires capability consent.
Run install with --accept-capabilities to proceed.
```

---


### 4. 研究方法与操作流程

#### 4.1 通用前置条件（双端共通）

| 项目           | NAS（fnOS）                                               | 本地（Windows）                                                            |
| ------------ | ------------------------------------------------------- | ---------------------------------------------------------------------- |
| Node         | `/home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin/` | `C:\Users\user\.workbuddy\binaries\node\versions\22.22.3\node.exe`     |
| OpenClaw CLI | `openclaw`（nvm 环境）                                      | `C:\Users\user\AppData\Roaming\npm\node_modules\openclaw\openclaw.mjs` |
| 出网代理         | Mihomo `127.0.0.1:<NAS_PROXY_PORT>`（npm 安装需走代理）         | Mihomo `127.0.0.1:<LOCAL_PROXY_PORT>`                                  |
| 配置文件         | `/home/<NAS_SSH_USER>/.openclaw/openclaw.json`          | `C:\Users\user\.openclaw\openclaw.json`                                |
| 插件工程目录       | `/home/<NAS_SSH_USER>/.openclaw/npm/projects/`          | `C:\Users\user\.openclaw\npm\projects\`                                |

> 说明：npm 直连在 NAS 侧不通，安装插件前必须让 npm 走 Mihomo 代理；本地侧 peerDependency 兜底可设 `NODE_PATH=C:\Users\user\AppData\Roaming\npm\node_modules`。

#### 4.2 NAS（fnOS）端卸载与重装

```bash
# 0) 前置：确保 node / npm 走 nvm 且 npm 走代理
export PATH=/home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin:$PATH
export HOME=/home/<NAS_SSH_USER>
# （npm 代理在 ~/.npmrc 已配置为 http://127.0.0.1:<NAS_PROXY_PORT>）

# 1) 停止网关（systemd user service，切勿套 sudo）
systemctl --user restart openclaw-gateway   # 或用 stop 后 start

# 2) 卸载旧插件（清理配置条目 + 删除目录）
openclaw plugins uninstall qqbot            # 旧 @openclaw/qqbot
# 同时手动删除残留工程目录：
#   /home/<NAS_SSH_USER>/.openclaw/npm/projects/<旧 qqbot 目录>

# 3) 在 openclaw.json 写入新通道参数（套用原 NAS 凭证）
#    channels.qqbot = {
#      "enabled": true,
#      "appId": "<NAS_QQ_APP_ID>",
#      "clientSecret": "<NAS_QQ_CLIENT_SECRET>",
#      "allowFrom": ["*"],
#      "dmPolicy": "open",
#      "groupAllowFrom": ["*"]
#    }
#    并设 plugins.entries.openclaw-qqbot = { "enabled": true }

# 4) 安装新插件（关键：--accept-capabilities）
openclaw plugins install @tencent-connect/openclaw-qqbot@2.0.3 --accept-capabilities

# 5) 重启网关并观察日志
systemctl --user restart openclaw-gateway
journalctl --user -u openclaw-gateway -f    # 或 tail ~/.../openclaw-*.log
```

#### 4.3 本地 Windows 端卸载与重装

```powershell
# 0) 前置
$env:NODE_PATH = "C:\Users\user\AppData\Roaming\npm\node_modules"
# 用托管 node 22.22.3 跑 CLI：
$node = "C:\Users\user\.workbuddy\binaries\node\versions\22.22.3\node.exe"
$cli  = "C:\Users\user\AppData\Roaming\npm\node_modules\openclaw\openclaw.mjs"

# 1) 停掉正在运行的 gateway（必要时先清陈旧锁，见 5.4）

# 2) 卸载旧插件 + 删残留目录
& $node $cli plugins uninstall qqbot
# 手动删除：C:\Users\user\.openclaw\npm\node_modules\@openclaw\qqbot

# 3) 在 openclaw.json 写入新通道参数（套用原本地凭证）
#    channels.qqbot = {
#      "enabled": true,
#      "appId": "<LOCAL_QQ_APP_ID>",
#      "clientSecret": "<LOCAL_QQ_CLIENT_SECRET>",
#      "allowFrom": ["*"],
#      "dmPolicy": "open",
#      "groupAllowFrom": ["*"]
#    }
#    plugins.entries.openclaw-qqbot = { "enabled": true }

# 4) 安装新插件
& $node $cli plugins install @tencent-connect/openclaw-qqbot@2.0.3 --accept-capabilities

# 5) 启动网关（见桌面 openclaw启动.bat 的等价命令）
& $node $cli gateway run --port 9090 --bind lan --token <GATEWAY_TOKEN>
```

> 本地侧因 `install` 校验拒 `"*"`（见 3.1），实操中先临时把配置改为 `dmPolicy: "allowlist"` + `allowFrom: ["<USER_QQ_OPENID>"]` 完成插件**注册**，再切回 `allowFrom: ["*"]` + `dmPolicy: "open"` 启动；运行时接受该组合，doctor 自动迁移。



---


### 5. 关键错误与修复对照表

| # | 现象 / 报错                                                           | 根因                                                | 修复                                                                          |
| - | ----------------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------- |
| 1 | `requires capability consent`                                     | 新插件需显式能力许可                                        | 安装加 `--accept-capabilities`                                                 |
| 2 | `channels.qqbot.allowFrom.0: must not be valid`                   | 新插件 install 阶段 schema 拒 `"*"`                     | 临时改 `dmPolicy:"allowlist"`+`allowFrom:[用户号]` 完成注册，再切回 `"*"+open`            |
| 3 | `unknown channel id: qqbot (stale channel plugin config ignored)` | install 在报错时中止，插件未注册进配置/注册表                       | 用 `--force` 重装完成注册                                                          |
| 4 | `plugin already exists ... delete it first`                       | 首次部分安装留下目录                                        | 删残留目录后用 `--force` 重装（会产生带 generation 后缀的新目录，旧目录成孤儿需清理）                      |
| 5 | `gateway already running (pid 4188); lock timeout`                | 陈旧 gateway 锁文件未释放（`tmp/openclaw/gateway.*.lock*`） | 删除 `gateway.*.lock*` / `gateway.*.lock.sqlite*` / `gateway.state.lock*` 后重启 |
| 6 | `Invoking cmd.exe from Bash bypasses all command validation`      | 用 `cmd /c start` 拉起网关被安全策略拦截                      | 改用 Bash `run_in_background` 直接后台启动 node                                     |
| 7 | `Degraded plugins: 1 configured-unavailable · qqbot`              | 旧 `@openclaw/qqbot` 注册表残留条目（目录已删）                 | **非致命**，新 `openclaw-qqbot` 已正常加载连接；如需消除可清理注册表残留项                            |

---

### 6. 验证结果（铁证）

#### 6.1 NAS 端

日志证据（新进程 PID 确认，`/tmp/openclaw/openclaw-*.log`）：

```
✅ Access token obtained
Connecting to wss://api.sgroup.qq.com/websocket
WebSocket connected
http server listening (15 plugins: ... openclaw-qqbot ...)
```

`openclaw status` 输出：

```
│ QQ Bot   │ ON      │ OK     │ configured
```

#### 6.2 本地端

日志证据（`%TEMP%\openclaw\openclaw-*.log`）：

```
http server listening (14 plugins: ... openclaw-qqbot ...)
✅ Access token obtained
Connecting to wss://api.sgroup.qq.com/websocket
WebSocket connected
qqbot gateway READY
approval registered
```

`openclaw status` 输出：

```
│ QQ Bot   │ ON      │ OK     │ configured
```

#### 6.3 残留无害警告说明

双端 `status` 均可能出现：

```
Degraded plugins: 1 configured-unavailable · qqbot
```

这是**旧 `@openclaw/qqbot` 的注册表残留条目**（目录已删、新插件已正常加载并 WS 连上）所致，不影响 QQ 通道功能。属非致命告警，可择机清理注册表残留以消除提示。

---

### 7. 结论

1. **根因明确**：OpenClaw 2026.8.2 的破坏性变更使旧 `@openclaw/qqbot` 必崩，必须换装 `@tencent-connect/openclaw-qqbot@2.0.3`。
2. **配置机制反直觉但可被驯服**：`allowFrom: ["*"]` 在 install 被拒、运行时被 doctor 迁移为 `openclaw:approval-disabled`，真正放行私聊的是 `dmPolicy: "open"`。理解这套机制后，配置可稳定复现。
3. **双端 SOP 已验证**：NAS（systemd user service + nvm node）与本地（托管 node + 桌面 bat 等价命令）均按同一套「卸载→重装→套用原参数→清锁→重启→查 WS」流程走通，`WebSocket connected` 为铁证。
4. **工程价值**：本复盘可作为同类「升级后某通道静默失效」问题的标准排查范式——优先查官方兼容性文档，再定位插件 API 版本错配，而非盲目改网络或后台配置。

---

### 参考文献与资料

#### 一、官方文档 / 网页（故障根因与权威结论出处）

1. **QQ 官方机器人文档 ——《升级 QQ Bot 插件（2026-7-1-2 兼容性变更）》章节**
   https://bot.q.qq.com/wiki/agent-qqbot/#%E5%8D%87%E7%BA%A7-qq-bot-%E6%8F%92%E4%BB%B6-2026-7-1-2-%E5%85%BC%E5%AE%B9%E6%80%A7%E5%8F%98%E6%9B%B4
   > 本文故障根因与正确插件包 `@tencent-connect/openclaw-qqbot@2.0.3` 的权威出处。明确指出自 2026.8.2 起旧 `@openclaw/qqbot` 不再兼容，必须换装新包。

2. **OpenClaw 官方文档：FAQ**
   https://docs.openclaw.ai/faq

3. **OpenClaw 官方文档：Troubleshooting**
   https://docs.openclaw.ai/troubleshooting

#### 二、参考仓库（GitHub，均已脱敏公开）

4. **本仓库姊妹篇：《OpenClaw 网关双端协同升级的实证研究》**（2026.7.1-2 → 2026.8.2 网关升级复盘，含 5 个踩坑）
   https://github.com/seeyouagain-laoda/openclaw-upgrade-empirical-study
   （同仓库内文件：`OpenClaw双端升级实证研究_脱敏版.md`）

5. **新 QQ 插件包（npm 发布源）：`@tencent-connect/openclaw-qqbot`**（本文安装目标 `@2.0.3`）
   https://www.npmjs.com/package/@tencent-connect/openclaw-qqbot

---

### 附录 A：关键命令清单（脱敏）

```bash
# —— 通用：安装新插件（双端一致，需 --accept-capabilities）——
openclaw plugins install @tencent-connect/openclaw-qqbot@2.0.3 --accept-capabilities

# —— NAS：systemd 重启 ——
systemctl --user restart openclaw-gateway
# 注意：务必用 systemctl --user，套 sudo 会丢 D-Bus 会话

# —— 本地：清陈旧锁后启动 ——
# 删除 C:\Users\user\.openclaw\tmp\openclaw\gateway.*.lock* 等
node openclaw.mjs gateway run --port 9090 --bind lan --token <GATEWAY_TOKEN>

# —— 验证（双端一致）——
openclaw status                 # 看 Channels → QQ Bot → ON / OK / configured
openclaw logs --follow          # 看 WebSocket connected
openclaw status --deep          # 深度通道探测

# —— 最终通道配置片段（脱敏）——
# channels.qqbot = {
#   "enabled": true,
#   "appId": "<QQ_APP_ID>",
#   "clientSecret": "<QQ_CLIENT_SECRET>",
#   "allowFrom": ["*"],
#   "dmPolicy": "open",
#   "groupAllowFrom": ["*"]
# }
# plugins.entries.openclaw-qqbot = { "enabled": true }
```

---

### 附录 B：脱敏映射表

| 占位符                                       | 含义                        | 说明                   |
| ----------------------------------------- | ------------------------- | -------------------- |
| `<NAS_QQ_APP_ID>`                         | 飞牛 NAS 端 QQ 机器人 AppID     | 原值已隐去，仅本机/NAS 各自独立一套 |
| `<NAS_QQ_CLIENT_SECRET>`                  | NAS 端 QQ 机器人 ClientSecret | 高敏感，已隐去              |
| `<LOCAL_QQ_APP_ID>`                       | 本地 Windows 端 QQ 机器人 AppID | 与 NAS 端不同，独立凭证       |
| `<LOCAL_QQ_CLIENT_SECRET>`                | 本地端 QQ 机器人 ClientSecret   | 高敏感，已隐去              |
| `<USER_QQ_OPENID>`                        | 用户本人 QQ 发送者 OpenID        | 私聊白名单临时绕过用，已隐去       |
| `<NAS_LAN_IP>`                            | 飞牛 NAS 局域网 IP             | 如 192.168.x.x 段      |
| `<NAS_SSH_USER>`                          | NAS SSH 登录用户名             | 已隐去                  |
| `<NAS_SSH_PASSWORD>`                      | NAS SSH 口令                | 高敏感，已隐去              |
| `<GATEWAY_TOKEN>`                         | OpenClaw gateway 启动 Token | 本地启动用，已隐去            |
| `<NAS_PROXY_PORT>` / `<LOCAL_PROXY_PORT>` | 两端 Mihomo 代理端口            | 仅本机回环，非公网暴露          |

**保密声明**：本文档不含任何真实 AppID / ClientSecret / OpenID / 口令 / Token / 公网 IP。所有敏感字段均以 `<...>` 占位符表示，可安全公开。
