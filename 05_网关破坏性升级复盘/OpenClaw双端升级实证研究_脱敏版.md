# OpenClaw 网关双端协同升级的实证研究
## ——从 2026.7.1-2 到 2026.8.2 的本地主机与 NAS 部署复盘

> 本文档为技术复盘报告，所有涉及网络地址、账号、密钥、设备标识等敏感信息均已做脱敏处理，仅保留用于复现与理解所必需的结构性信息。

---

### 摘要

本文记录并分析了对 **OpenClaw 网关**（版本 `2026.7.1-2` → `2026.8.2`）在异构双端环境中的一次生产级升级实践，两端分别为一台运行 Windows 操作系统的本地主机与一台运行 Linux 的网络附加存储（NAS）设备。研究采用"配置备份—包升级—配置迁移—服务验证"的标准方法论，并在升级后对双端网关进行了端到端任务验证。在升级与验证过程中，共暴露出五类典型故障，本文对每一类故障进行了根因定位（root cause analysis）与修复验证。结果表明：(1) 升级后双端核心服务均通过健康检查（HTTP 200）；(2) 端到端推理任务在多种模型供应商（provider）路由下成功执行；(3) 五类故障均存在可复现的修复路径，其中最具代表性的是 **NAS 侧由模型路由隐式触发的 Codex 运行时插件崩溃死循环**，以及 **本地侧由操作系统权限模型导致的 peer-link 软链接限制**。本文提出的诊断思路与修复方案，可为同类自托管 AI 网关的版本迁移提供工程参考。

**关键词**：OpenClaw；网关升级；NAS；Windows；插件运行时；peer-link；配置迁移；根因分析

---

### 1. 引言

OpenClaw 是一类以"网关（gateway）+ 插件（plugin）"为核心架构的自托管 AI 代理运行时。其网关进程对外提供统一的模型推理与任务调度接口，而具体的大模型能力则通过内置 provider（如 OpenAI 兼容接口）与第三方插件（如 DeepSeek provider、QQ 机器人适配器）两类机制接入。随着版本演进，OpenClaw 在 2.0 大版本中引入了若干破坏性变更（breaking changes），包括配置 schema 重构、插件能力授权（capability consent）机制、以及将部分模型路由迁移至独立的运行时插件（runtime plugin）。

在真实的个人算力拓扑中，用户通常以"本地主机 + NAS"双端协同的方式部署：本地主机承担交互与调试，NAS 承担常驻服务与局域网共享。当两端需同步升级到同一目标版本时，操作系统差异（Windows 的权限模型 vs. Linux 的符号链接语义）、网络拓扑差异（反向代理、局域网绑定）、以及既有配置中"隐式模型路由"等因素，会共同放大升级的复杂度。

本文的目标并非给出一份操作手册，而是以实证研究的方法，记录一次真实升级中遇到的问题、定位过程与修复依据，提炼出可迁移的诊断框架。

---

### 2. 系统背景与升级目标

#### 2.1 部署架构

| 维度 | 本地主机（Host A） | NAS（Host B） |
|---|---|---|
| 操作系统 | Windows（非管理员账号） | Linux（systemd --user 托管） |
| 运行时 | Node.js 22.22.3（托管版） | Node.js 22.22.3（nvm 管理） |
| 网关端口 | `0.0.0.0:9090`（局域网绑定） | `0.0.0.0:9090`（局域网绑定） |
| 进程托管 | 桌面 `.bat` 启动器（前台/最小化） | `systemd --user` 服务 `openclaw-gateway.service` |
| 主要 provider | 内置 `gmini`（反代）、`nvidia`、`pplx`、`pokeapi`、`openrouter`、插件型 `deepseek`、`qqbot` | 内置 `gmini`（本地代理）、`nvidia`、`pplx`，插件型 `deepseek`、`qqbot` |
| npm 源 | 默认 | 国内镜像 |

> 脱敏说明：下文将本机局域网地址记为 `192.168.x.1`，NAS 地址记为 `192.168.x.123`，网关访问令牌记为 `<GATEWAY_TOKEN>`，NAS 登录口令记为 `<NAS_PASSWORD>`，NAS 系统账号记为 `nas-user`。

#### 2.2 版本差异与破坏性变更

目标版本 `2026.8.2`（属 2.0 系列）相对源版本 `2026.7.1-2` 的关键变更如下：

1. **配置 schema 重构**：移除 `meta.lastTouchedAt` 等冗余键；将顶层 `env.*` 密钥（如 `env.DEEPSEEK_API_KEY`）迁移至 `env.vars` 子对象；调整 `browser.*`、`commands.ownerDisplay`、`gateway.controlUi.allowInsecureAuth` 等结构。
2. **插件能力授权机制**：插件在加载前需通过显式 `consent`（capability consent）。未授权的插件在网关启动的校验阶段会被拒绝，并抛出 `"<plugin> requires capability consent"` 错误，网关拒绝进入就绪（ready）状态。
3. **模型路由迁移**：部分原本内置的模型路由（如 `codex/*`、`openai-codex/*`）被迁移至独立的 **Codex 运行时插件**（`@openclaw/codex`），由模型选择（model selection）阶段按需确保（ensure）其安装与授权。
4. **peer-link 依赖机制**：插件型 provider 在其工程目录的 `node_modules/` 下需存在一个指向宿主 OpenClaw 全局包的"对等链接"（peer-link，理论上为符号链接或 junction），否则在加载时无法解析宿主核心模块。

---

### 3. 研究方法

#### 3.1 升级流程（标准方法论）

两端统一遵循以下步骤：

1. **配置备份**：对 `~/.openclaw`（本地）与 `/home/nas-user/.openclaw`（NAS）执行整目录备份，保留为 `*.backup_pre820`，以防 SQLite 状态迁移不可逆导致回滚困难。
2. **包升级**：执行 `npm i -g openclaw@2026.8.2`（两端均经对应 Node 运行时）。
3. **配置迁移**：执行 `openclaw doctor --fix`，自动清理不识别的旧键并将密钥迁移至 `env.vars`。
4. **插件授权**：对需要 consent 的插件逐一执行 `openclaw plugins enable <id> --accept-capabilities`。
5. **服务验证**：重启网关进程，验证端口监听（`ss -ltnp` / `netstat`）与健康端点（`GET /health` → HTTP 200）。

#### 3.2 验证方法

采用最小化端到端任务进行验证：通过 `openclaw infer model run --gateway --model <provider>/<model> --prompt "..."` 派发一次推理请求，预期模型返回正确数值。该方法可同时验证"网关可达性 → 模型路由解析 → provider 鉴权 → 响应回传"的完整链路。

---

### 4. 实验结果

#### 4.1 健康检查

| 实例 | `/health` | 版本 | 端口监听 |
|---|---|---|---|
| 本地主机 | HTTP 200 | 2026.8.2 | `0.0.0.0:9090` |
| NAS | HTTP 200 | 2026.8.2 | `0.0.0.0:9090` |

#### 4.2 端到端任务验证

强制走网关（`--gateway`）派发最小推理任务，结果如下：

| 实例 | 模型 | 任务 | 返回 | 结论 |
|---|---|---|---|---|
| 本地 | `gmini/gemini-3.6-flash` | 7×6 | **42** | ✅ 全链路通 |
| NAS | `gmini/gemini-3.5-flash` | 7×6 | **42** | ✅ 全链路通 |
| NAS | `deepseek/deepseek-v4-flash` | 12+13 | **25** | ✅ 第二 provider 通 |
| 本地 | `deepseek/deepseek-v4-flash`（加载层） | — | — | ✅ `status=loaded`；live 推理未跑（用户要求不使用其 DeepSeek API） |

> 注：NAS 的模型白名单（`agents.defaults.modelPolicy.allow`）仅含 `gemini-3.5-flash` 等同族模型，故本地所用的 `3.6-flash` 在 NAS 侧需改用 `3.5-flash` 方可通过策略校验。

---

### 5. 问题分析与解决

本节按"现象 → 根因 → 修复 → 验证"的结构，逐一对五类故障进行复盘。

#### 5.1 NAS 的 Codex 运行时插件崩溃死循环（核心故障）

**现象**：包升级与 `doctor --fix` 均成功，但 `systemctl --user restart openclaw-gateway.service` 后网关进程立即退出，`0.0.0.0:9090` 始终无监听。手动前台运行网关亦无有效错误输出。日志停留在升级前的旧时间戳，说明网关从未成功进入就绪状态。

**根因定位**：通过对发行包 `dist/` 源码的静态分析，确认 `openai/gpt-oss-120b` 在 OpenClaw 2.0 中经由 `resolveOpenAIImplicitAgentRuntime` 被**隐式映射**到 `codex` 运行时。当配置中包含该模型时，网关启动的模型选择阶段会调用 `ensureCodexRuntimePluginForModelSelection`，进而：
1. 在插件注册表中查找 `codex` 运行时插件；
2. 发现其"已安装"记录存在，遂尝试 `repair` 并重建工程目录 `npm/projects/openclaw-codex-<hash>/`；
3. 重建后的插件需通过 capability 授权，但无授权记录；
4. 网关在插件校验阶段抛出 `"Plugin 'codex' requires capability consent"`，拒绝就绪。

由此形成**死循环**：删除 `npm/projects/openclaw-codex-<hash>/` → 网关重启时依据 SQLite 状态库（`state/openclaw.sqlite`）中的"已安装插件"记录再次重建该目录 → 再次因缺授权崩溃。这也是"删了又长、一直起不来"的直接原因。

**修复**：使用官方安装命令而非裸删目录——该命令会完成"安装 + 授权 + peer-link 链接"的完整流程：

```bash
# 停止网关
systemctl --user stop openclaw-gateway.service
# 删除被反复重建的坏工程
rm -rf /home/nas-user/.openclaw/npm/projects/openclaw-codex-<hash>*
# 正式安装并授权 Codex 运行时插件
openclaw plugins install @openclaw/codex --accept-capabilities --force
# 手动补建 peer-link（Linux 下符号链接无权限限制）
ln -sfn /home/nas-user/.nvm/versions/node/v22.22.3/lib/node_modules/openclaw \
       /home/nas-user/.openclaw/npm/projects/openclaw-codex-<hash>/node_modules/openclaw
# 重启
systemctl --user restart openclaw-gateway.service
```

**验证**：重启后新进程干净监听 `0.0.0.0:9090`，`/health` 返回 200；`openclaw plugins inspect codex` 显示 `status: loaded`、`enabled: true`、`version: 2026.8.2`。进一步执行**耐久测试**（再次重启），确认不再陷入"重建→崩溃"循环，codex 目录保持完好且仍 `loaded`。

**经验**：当网关因某个插件反复崩溃时，应优先确认该插件是否被"模型路由隐式触发"，而非仅从 `openclaw.json` 的 `plugins.entries` 配置去排查——隐式路由不会出现在显式配置中。

#### 5.2 本地 Windows 的 peer-link 软链接限制

**现象**：本地 `deepseek` 插件在升级后处于 `missing-openclaw-peer-link` 状态，`openclaw plugins update deepseek` 在"创建 `node_modules/openclaw` 链接"步骤失败；网关启动日志持续打印 `missing-openclaw-peer-link` 警告（非致命）。

**根因定位**：本地 Windows 账号为**非管理员**。Windows 安全模型规定，非管理员账号创建的符号链接（symlink）或 junction 会被标记为 **untrusted mount point**；其他进程（包括 Node.js）在遍历该重解析点时会收到 `Permission denied`。即便尝试以 `mklink /J` 建 junction，亦因相同限制而 `rc=1` 失败。该限制为操作系统级，在当前的非管理员会话内无法根治。

**修复（运行时兜底，免改系统）**：在本地网关启动脚本（`openclaw启动.bat`）中注入 `NODE_PATH`，使插件在无法穿越 peer-link 时，仍能经 `NODE_PATH` 兜底解析到全局 OpenClaw 包：

```bat
set NODE_PATH=C:\Users\<user>\AppData\Roaming\npm\node_modules
```

经实测，即便插件目录中残留指向 `/c/Users/...` 的坏软链接（由 Git Bash 以 Unix 风格路径创建，Windows 原生 Node 不识别），只要设置 `NODE_PATH`，`require('openclaw')` 即可成功解析至全局包。修复后一并删除该坏软链接。

**验证**：以带 `NODE_PATH` 的方式重启网关，`/health` → 200；`openclaw plugins inspect deepseek --runtime` 显示 `status: loaded`、`activated: true`、`providerIds: ["deepseek"]`。

**替代根治方案（需用户侧操作，二选一）**：
- 开启 Windows 开发人员模式（设置 → 系统 → 开发者选项），再执行 `openclaw plugins update --all`；
- 或以管理员身份执行 `openclaw plugins update deepseek`，再重启网关。

**影响评估**：该限制**仅**影响依赖 peer-link 的插件型 provider（`deepseek`、`qqbot`），内置 provider（如 `gmini`、`nvidia`、`pplx`）不受影响。日常以默认 `gmini` 模型运行无感知差异。

#### 5.3 `update repair` 命令的误报

**现象**：在执行 `openclaw update repair` 时，命令报错 `"The update parent owns Gateway activation"` 并拒绝执行修复，即便当时并无网关在运行、亦无孤儿锁文件。

**根因定位**：通过对 `dist/` 源码分析，`update repair` 在内部 spawn 一个 `doctor --repair` 子进程，并为其注入环境变量 `OPENCLAW_UPDATE_PARENT_ALLOWS_GATEWAY_ACTIVATION`。该标记使子进程误认为"存在上级更新进程持有网关激活权"，从而自我阻断。此属该命令在特定调用路径下的固有缺陷。

**修复**：改用非 `update repair` 路径完成等价修复：
- 插件重链：`openclaw plugins update --all`
- 插件授权：`openclaw plugins enable <id> --accept-capabilities`

**经验**：当 `update repair` 报"update parent"类错误时，不应反复重试该命令，而应以 `plugins update --all` / `plugins enable --accept-capabilities` 组合替代。

#### 5.4 NAS 模型白名单策略（`modelPolicy.allow`）

**现象**：在 NAS 侧以 `gmini/gemini-3.6-flash` 派发任务时，请求被拒绝，提示不在允许列表内。

**根因定位**：NAS 的 `agents.defaults.modelPolicy.allow` 显式列出了允许的模型标识，其中 Gemini 同族仅含 `gemini-3.5-flash`，不含 `3.6-flash`。这是**配置层面的策略约束**，而非升级引入的故障。

**修复**：在 NAS 侧改用白名单内的 `gmini/gemini-3.5-flash` 执行同一任务，验证通过（返回 42）。

**经验**：跨端验证时，不能假设两端模型标识完全一致；应先读取目标端的 `modelPolicy.allow` 与默认模型，再选择合规标识。

#### 5.5 浏览器 Control UI 的一次性设备配对

**现象**：浏览器首次连接网关 Control UI 时，提示需在网关主机执行一次性批准，给出待批准设备标识 `<DEVICE_UUID>` 与批准命令 `openclaw devices approve <DEVICE_UUID>`。

**根因定位**：Control UI 在首次从某设备接入时，需经网关的"设备配对（device pairing）"流程完成一次性授权。该批准与"使用何种模型"无关，属独立的访问控制环节。通过比对两端 `devices list`，确认该待批准设备归属于 **NAS 网关**（请求源自 `192.168.x.123`），本地网关无此待批准项。

**修复**：在 NAS 端执行批准命令：

```bash
openclaw devices approve <DEVICE_UUID>
```

**验证**：复查 `devices list`，该设备由 `Pending` 转入 `Paired`，角色为 `operator`，具备 admin/read/write/approvals/questions/pairing 等权限范围。浏览器重新连接即可正常使用 Control UI。

**经验**：Control UI 配对是独立权限环节，不应与模型/provider 可用性混淆；定位待批准设备时应先在双端 `devices list` 中比对设备标识，确认归属主机后再批准。

---

### 6. 结论

本文以一次真实升级为例，验证了 OpenClaw 网关在"本地 Windows 主机 + Linux NAS"双端拓扑下从 `2026.7.1-2` 平滑升级至 `2026.8.2` 的可行性，并提炼出以下工程结论：

1. **标准化升级流程有效**：备份—升级—迁移—授权—验证的五步法，可使双端核心服务均达到健康状态（HTTP 200）。
2. **隐式模型路由是升级的最大风险点**：NAS 侧因 `openai/gpt-oss-120b` 隐式触发 Codex 运行时插件而导致崩溃死循环，唯有通过官方 `plugins install @openclaw/codex --accept-capabilities` 完成"安装+授权+链接"闭环方能根治，裸删目录只会重启重建。
3. **操作系统权限模型决定修复路径**：Windows 非管理员账号的 peer-link 限制无法在当前会话根治，但通过 `NODE_PATH` 运行时兜底可无损恢复插件加载；彻底消除警告仍需用户侧开启开发人员模式或提权操作。
4. **命令缺陷需有替代路径**：`update repair` 的"update parent"误报应以 `plugins update --all` / `plugins enable` 组合规避。
5. **配置策略需逐端核对**：模型白名单与设备配对均为端级独立配置，跨端验证前应先读取目标端策略。

综上，本次双端升级在达成"服务可用、链路贯通"目标的同时，也为同类自托管 AI 网关的版本迁移积累了可复用的诊断框架与修复清单。

---

### 参考文献与资料

1. OpenClaw 官方项目文档（配置迁移、插件能力授权、运行时插件机制）。
2. OpenClaw 发行包 `dist/` 静态分析（`openai-routing-*.js`、`doctor-*.js`、`update-phase-*.js`、`doctor-plugin-host-links-*.js`）。
3. Windows 文档：非管理员账号的符号链接与 untrusted mount point 限制；开发人员模式对符号链接权限的影响。
4. systemd 用户服务（`systemd --user`）托管常驻进程的标准实践。
5. Node.js 模块解析机制：`NODE_PATH` 对环境变量解析顺序的影响。

---

### 附录 A：关键命令清单（脱敏）

```bash
# —— 通用升级 ——
npm i -g openclaw@2026.8.2
openclaw doctor --fix
openclaw plugins enable <id> --accept-capabilities
openclaw plugins update --all

# —— NAS：Codex 运行时插件死循环修复 ——
systemctl --user stop  openclaw-gateway.service
rm -rf /home/nas-user/.openclaw/npm/projects/openclaw-codex-<hash>*
openclaw plugins install @openclaw/codex --accept-capabilities --force
ln -sfn <global-openclaw> <project>/node_modules/openclaw
systemctl --user restart openclaw-gateway.service

# —— 本地：peer-link 限制兜底 ——
# 在 openclaw启动.bat 注入：
set NODE_PATH=C:\Users\<user>\AppData\Roaming\npm\node_modules

# —— 验证 ——
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9090/health
openclaw infer model run --gateway --model <provider>/<model> --prompt "..."

# —— 设备配对 ——
openclaw devices list
openclaw devices approve <DEVICE_UUID>
```

### 附录 B：脱敏映射表

| 真实信息类别 | 文档中占位符 |
|---|---|
| 本机局域网地址 | `192.168.x.1` |
| NAS 局域网地址 | `192.168.x.123` |
| 网关访问域名 | `your-domain.example` |
| 网关访问令牌 | `<GATEWAY_TOKEN>` |
| NAS 系统账号 | `nas-user` |
| NAS 登录口令 | `<NAS_PASSWORD>` |
| 待批准设备 UUID | `<DEVICE_UUID>` |
| 插件工程构建哈希 | `<hash>` |
| 各供应商 API Key | `<API_KEY>` |

---

*本报告基于 2026 年 9 月 3 日的真实升级操作整理，所有敏感字段已脱敏，仅供技术复盘与同行参考。*
