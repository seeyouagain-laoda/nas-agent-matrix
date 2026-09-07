# 基于 NAS 的 ASTRBOT 扮演 Deepseek 鲸鱼娘的实战，接入 OpenClaw执行任务

> **声明：此文章和任务由 AI 生成，仅供参考。**
> 部署涉及你的 NAS / QQ 账号 / API Key，实操前请自行确认风险；文中密钥与 Token 均已脱敏为占位符，真实值见你本地配置文件。

## 〇、TL;DR

- 用 **AstrBot + NapCat** 在 NAS 上跑起一个 QQ 机器人「鲸鱼娘」（云端大模型当大脑）。
- 再加一个极薄的 **relay 桥**，让鲸鱼娘在 QQ 里一句话（`/任务 <活>`）就把任务转交给 **OpenClaw** 真执行（含 exec 工具），结果回传 QQ。
- 为什么还要 relay？因为 OpenClaw **已有原生 QQ Bot**（`openclaw-qqbot` 插件，状态 enabled 且已 connected），但那是 OpenClaw 自己当 QQ 机器人（OpenClaw 是大脑）；我们要的是让「鲸鱼娘」(AstrBot 人格 bot，独立大脑) 去**调度** OpenClaw。两者是两个不同的 QQ 号、两套大脑。relay 是鲸鱼娘 → OpenClaw 的桥，与原生 QQ bot 并存。
- 全文含**软件版本号**、**踩坑全记录（现象 → 根因 → 解决）**、端到端验收。

## 一、目标与背景

用户想在 QQ 里直接指挥家里的「数字雇员」OpenClaw 干真活（查容器、跑命令、读文件等），而不用自己开终端或另开网页。

链路上有两个角色：
- **鲸鱼娘（AstrBot + NapCat）**：负责在 QQ 里陪聊、收指令。大脑是可换的云端大模型（设计稿用白山 DeepSeek-V4-Flash，本机实测默认走 Gemini 3.7 Flash 反代）。
- **OpenClaw**：个人自主 Agent 执行器，能真正调用 exec / 文件 / 网络工具干重活。

本文聚焦把这两者用最低成本桥起来：**QQ 一句话 → OpenClaw 真执行 → 结果回 QQ**。

## 二、整体架构

```
QQ App
   │  (NTQQ 协议)
   ▼
NapCat  (Docker, OneBot v11)
   │  WebSocket
   ▼
AstrBot  (Docker, 鲸鱼娘人格 + 云端LLM大脑)
   │  /任务 指令 → aiohttp POST（带 X-Relay-Token）
   ▼
openclaw_relay  (:8910, 绑主机 LAN IP 192.168.31.123)
   │  openclaw agent --agent main -m "<task>" --json
   ▼  WebSocket
OpenClaw Gateway  (:9090)  ──  真执行（exec 等工具）
   │
   └─ 结果原路回传  ──>  QQ
```

> 注：OpenClaw 本身也有一个**原生 QQ Bot**（`openclaw-qqbot` 插件，状态 enabled 且已 connected），那是 OpenClaw 自己直接当 QQ 机器人（OpenClaw 是大脑）。上图是「鲸鱼娘 → OpenClaw」这条**调度链**；原生 bot 与上图是**两个独立的 QQ 号**，互不冲突，可并存。要让鲸鱼娘（AstrBot 人格 bot）去调度 OpenClaw，才需要上图的 relay 桥。

## 三、需要的软件与版本号

| 组件 | 版本 | 说明 |
|---|---|---|
| 飞牛 fnOS（NAS 系统） | v0.18.0（基于 Debian 12 bookworm） | 宿主机 OS |
| Docker | 28.5.2，build ecc6942 | 跑 NapCat / AstrBot / 各反代 |
| AstrBot | 4.27.5（镜像 `soulter/astrbot:latest`） | QQ 机器人框架 + 插件系统 |
| NapCat | `mlikiowa/napcat-docker:latest`（OneBot v11） | QQ 协议适配器，扫码登录 |
| OpenClaw | 2026.8.2（commit 0965053） | Agent 执行后端（WebSocket Gateway :9090） |
| Node.js | v22.22.3（nvm 管理） | OpenClaw CLI 运行环境 |
| Python | 3.11.2（主机） | relay 服务 `openclaw_relay.py` |
| Gemini 反代 `gemini-web2api-go` | `:3.7`（Go 实现） | 鲸鱼娘默认大脑（实测 Gemini 3.7 Flash） |
| 鲸鱼娘大脑（可选） | 白山 `DeepSeek-V4-Flash` | 设计稿指定云端模型，可替换 |
| nginx | 反代 / DDNS `246519.xyz` | 远程管理 WebUI（非本链路必需） |

> 注：鲸鱼娘的「大脑」是可换的云端大模型。设计稿用白山 DeepSeek-V4-Flash，本机实测默认走 Gemini 3.7 Flash 反代；本文聚焦 **QQ 前端（AstrBot）→ OpenClaw 执行后端** 这一层，LLM 后端不影响该链路。

## 四、实施步骤（摘要）

### 4.1 主机 relay 服务
文件 `/home/半夏/openclaw_relay.py` + systemd `/etc/systemd/system/openclaw-relay.service`（`Restart=always`）。
- 监听 `192.168.31.123:8910`（**主机 LAN IP**，不是 127.0.0.1）。
- `POST /run` 收 `{"task": "..."}` + Header `X-Relay-Token`，校验后调用：
  `openclaw agent --agent main --session-id relay-<pid> -m "<task>" --json`
- 解析 stdout JSON，返回 `{"ok","text","calls","error"}`；单任务超时 280s。
- Token 与插件共用（本地真实值见 `openclaw_relay.py` / 插件 `main.py`）。

### 4.2 AstrBot 插件
目录 `/vol4/qq-whale/astrbot_data/plugins/openclaw_controller/{main.py, metadata.yaml}`。
- `main.py`：`@register(name, author, desc, version)` + `@filter.command("任务")`，处理器用 `aiohttp` POST 到 relay，结果 `yield event.plain_result(...)` 回 QQ。
- `metadata.yaml`：`name / author / desc / version`（desc 必须与 `@register` 同步，见坑 6）。

### 4.3 网络
astrbot 容器在自定义网络 `qq-whale_astrbot_network`，实测可直连 `192.168.31.123:8910`（relay）与 `:9090`（OpenClaw）——插件链路通畅。

## 五、踩坑全记录（重点）

### 坑 1（更正）：曾误判 OpenClaw 不支持 QQ，实则原生已接入
- **现象（最初误判）**：想让 OpenClaw 直接当 QQ bot 时，以为它不支持 QQ，于是打算让 AstrBot 扮 QQ 前端 + relay 桥到 OpenClaw。
- **根因（误判来源）**：只查了 `openclaw agent --channel` 的**内置**渠道列表（只有 telegram / discord / feishu / …），又用 `napcat|onebot|cqhttp` 当 grep 关键词——而 OpenClaw 的 QQ 走腾讯官方 **`qqbot`** 协议（插件提供，不叫那几个名），所以漏判。
- **实测纠正**：`openclaw plugins list` 显示 `OpenClaw QQ Bot / openclaw-qqbot / enabled / v2.0.3`；`openclaw channels status` 显示 `QQ Bot default: enabled, configured, running, connected`；`openclaw.json` 已配置 `qqbot` 渠道。**OpenClaw 原生就支持且已接入 QQ。**
- **最终方案**：OpenClaw 原生 QQ bot 保留（直接在 QQ 里跟 OpenClaw 说话、它自己干活用它）；但鲸鱼娘（AstrBot）与 OpenClaw 原生 bot 是**两个独立 QQ 机器人**，要让鲸鱼娘调度 OpenClaw 仍需 relay 桥。故**两个都留**：原生 bot 管「直接对话 OpenClaw」，relay 管「鲸鱼娘 → OpenClaw 调度」。

### 坑 2：逆向 OpenClaw WebSocket 握手失败
- **现象**：试让插件直连 Gateway WS（`OPENCLAW_GATEWAY_URL=ws://...`），抓包得到 `gateway rejected websocket upgrade (HTTP 401): Unauthorized`；且覆盖该变量还需显式 `OPENCLAW_GATEWAY_TOKEN`。
- **根因**：WS 握手鉴权不是简单 Bearer，协议细节未公开，逆向脆弱、易随版本崩。
- **解决**：不逆向 WS，直接复用官方 `openclaw agent` CLI（CLI 内部完成 WS 握手），relay 只封装这一行命令。

### 坑 3：AstrBot 插件 `@register` 四个参数全必填
- **现象**：`register_star() missing 3 required positional arguments: 'author', 'desc', 'version'`，补齐后又 `missing 1 required positional argument: 'name'`。
- **根因**：AstrBot 4.27.5 的 `@register` 装饰器 `name / author / desc / version` **全部必填**（旧版可省略）。
- **解决**：严格照内置 `builtin_stars/builtin_commands/main.py` 范本补齐四个参数，缺一不可。

### 坑 4：容器内连不到主机的 127.0.0.1
- **现象**：插件 `POST 127.0.0.1:8910` 超时 / 连接拒绝。
- **根因**：插件跑在 astrbot 容器内，容器的 `127.0.0.1` 是**容器自己**，不是主机；自定义 docker 网络下容器有独立 IP。
- **解决**：relay 绑主机 LAN IP `192.168.31.123`，插件用同一 IP POST；`docker exec astrbot curl http://192.168.31.123:8910/health` 验证返回 200。

### 坑 5：relay 调 openclaw 报 command not found
- **现象**：relay 的 `subprocess` 起 `openclaw` 报找不到命令 / node 找不到。
- **根因**：relay 以 systemd `半夏` 用户跑，`PATH` 不含 nvm 的 node bin，`HOME` 未设导致 nvm 配置不加载。
- **解决**：`env` 显式设 `HOME=/home/半夏` + `PATH=/home/半夏/.nvm/versions/node/v22.22.3/bin:$PATH`。

### 坑 6：改完指令，启动日志还显示旧描述（误判「没生效」）
- **现象**：`docker restart astrbot` 后日志仍显示旧 `/oc` 描述，即使 `main.py` 已改 `/任务`、编译后的 `.pyc` 也含新指令。
- **根因**：AstrBot 加载日志的 desc 取自插件目录的 **`metadata.yaml`**（不是 `@register` 的 desc）。只改 main.py 不改 metadata.yaml，会导致日志显示旧值，极易误判。
- **解决**：改指令 / 描述时**同步改** `main.py`（`@filter.command` / `@register desc` / 用法提示）与 `metadata.yaml`(`desc`)；重启后 `docker logs astrbot | grep openclaw_controller` 确认 desc 已更新。（删 `__pycache__` 非必须，重启会重编。）

### 坑 7：QQ 鲸鱼娘自身的历史故障（前置，已修）
- **现象**：早期鲸鱼娘空回复 / 回复慢 / 模型旧。
- **根因链**：fake-ip DNS（`extra_hosts` 写死域名）→ 空输出（fallback 模型误触发）→ 回复慢（`retries` 配置）→ 模型停留在旧版。
- **解决**：修正 DNS / fallback / retries，并切到 Gemini 3.7 Flash 反代。详细见你本地「重要AI配置文档 / 07_IM集成」下的鲸鱼娘运维报告。

### 坑 8：SSH 内联命令引号陷阱
- **现象**：bash `-c` 内混用单双引号报 `unexpected EOF while looking for matching`；`$PATH` 被本地 shell 展开破坏远程命令。
- **根因**：Windows Git Bash → paramiko 远程执行时引号 / 变量展开行为不一致。
- **解决**：把探针写成 `.sh` 脚本文件，upload 到 NAS 后 `bash` 执行，杜绝内联引号。

## 六、端到端验收

经 relay（即插件实际路径）触发 OpenClaw 跑真实任务：
```
任务：列出 NAS 上正在运行的 docker 容器并汇报数量
返回：gemini-web2api-go / astrbot / napcat / tdai-memory-hub /
      pplx-proxy-nas / pplx-proxy-pplx-proxy-1 / tdai-proxy / tdai-memory-core
      共 8 个容器正在运行。   (calls=1 → OpenClaw 用 exec 工具真执行了 docker ps)
```
→ 鲸鱼娘 → OpenClaw 控制链真实可用，且 OpenClaw 真的动手干了活。

## 七、使用方式

```
/任务 <任务描述>
例：/任务 帮我查一下 NAS 磁盘剩余空间并简要汇报
例：/任务 用 exec 工具执行 uptime，告诉我 NAS 已运行多久
```
机器人先回「🐳 执行中…」，完成后回 OpenClaw 结果（附调用工具次数）。

## 八、文件清单与运维

| 文件 | 位置 | 说明 |
|---|---|---|
| relay 服务 | `/home/半夏/openclaw_relay.py` | OpenClaw 触发中继（systemd `openclaw-relay`） |
| 服务单元 | `/etc/systemd/system/openclaw-relay.service` | `Restart=always` |
| 插件 | `/vol4/qq-whale/astrbot_data/plugins/openclaw_controller/` | AstrBot `/任务` 指令 |
| 日志 | `/home/半夏/.openclaw_relay.log` | relay 运行日志 |

```bash
systemctl status openclaw-relay --no-pager          # 看 relay 状态
curl -s -X POST http://192.168.31.123:8910/run \
  -H 'X-Relay-Token: <你的REL-API-TOKEN>' -d '{"task":"echo hello"}'   # 手动测 relay（等价于 /任务）
docker restart astrbot                               # 插件改完重启机器人
```

## 九、结论

- 鲸鱼娘现已具备「QQ 一句话 → OpenClaw 真执行 → 结果回 QQ」能力。
- 新增常驻服务仅 `openclaw-relay`（已设自启）；如需彻底内网隔离可改绑 `127.0.0.1` + 容器走 `host.docker.internal` / docker0 网关。
- relay 模式可复制：任何「聊天机器人触发 Agent 执行」场景都能套用。

## 十、生图扩展（2026-09-05）：鲸鱼娘会画画了

在「调度 OpenClaw」之外，鲸鱼娘又多了**生图能力**，全部跑在 NAS 本地，不依赖外部生图 API 配额：

| 指令 | 后端 | 说明 |
|------|------|------|
| `/生成 <提示>` | NAS 浏览器 Gemini（CDP 驱动 gemini.google.com） | 附图即参考图；失败自动兜底 PokeAPI（gpt-image-2） |
| `/生成参考 <描述>` | NAS 浏览器 Gemini + 用户单独发参考图 | 参考图以 base64 绕过容器只读挂载直传 relay |
| `/梗图 [标签]` | whale-chan 935 张表情包（CDN 热链 / 本地） | 按标签随机发图；CDN 远程图用 `Image.fromURL` 直接发图 |

**端到端时延实测**（AstrBot 日志 + relay 日志交叉核对）：纯 bot 管线 **40–55s**，其中 **~99% 花在 Gemini 浏览器生图本身**（35–50s 区间，均值 ~43s）；插件/relay 转发 <1s，NapCat 投递 ~4s。结论：时延瓶颈 100% 在生图后端，代码无优化空间，要提速只能换更快后端或预生成。

**本轮修平的五个体验坑**（详见 `生图可行性教程_20260905/REPORT.md`）：

1. 回的是「浏览器截图」而非成图 → `findGenImg` 作用域 bug + CDP `clip.scale:1` 修复（v4）。
2. 生成失败静默卡死 → 插件 v1.4.7 对内容拦截/超时/对话式拒绝做早退并告知用户。
3. Gemini 对话式拒绝不告知 → JS 提取 Gemini 最后助手文本，v1.4.8 转述原文并跳过兜底。
4. 参考图上传不等就发 → v7→v11 三重修复：排除「更多选项」误匹配、`Runtime.evaluate` 两层返回取值、composer 预等待 + 每 2s 轮询（按钮 disabled/busy 消失且 ≥5s 才发）。
5. 梗图发成「链接」而非图 → `_emit_meme` 的 URL 分支误用 `event.image_result(url)`（本地文件语义），改为 `Image.fromURL(val)`（v1.4.9）。

> 新增常驻组件仅 Gemini 浏览器（fygo，CDP `127.0.0.1:16002`）+ `gemini_gen_nas.js`；relay 新增 `/image-gemini` 端点。

## 十一、本次交付文件

| 路径 | 说明 |
|------|------|
| `生成参考修复_20260904/` | 09-04 参考图生图修复专报 + 代码（插件 v1.4.4 / relay / 脚本） |
| `生图可行性教程_20260905/` | **09-05 生图扩展**：可行性教程报告 + 插件 v1.4.9 + Gemini 脚本 v11 + 占位符表 |
| `知识库RAG落地_20260906/` | **09-06 知识库 RAG**：把「重要 AI 配置文档」喂进 AstrBot 知识库（NIM embedding + FAISS + BM25），含 5 大踩坑全记录（两份配置文件 / 随机初始密码 / `/api/v1` 前缀 / provider 热加载 / 自动注入污染对话）+ 端到端验证 + 脱敏脚本 |

---

**你还有什么要问的吗？**
