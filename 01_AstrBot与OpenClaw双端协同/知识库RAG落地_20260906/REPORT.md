# AstrBot 鲸鱼娘知识库 RAG 落地详细报告（脱敏版）

> 适用版本：AstrBot v4.27.5（Docker 镜像 `soulter/astrbot:latest`）
> 环境：飞牛 fnOS NAS（局域网 `<NAS_LAN_IP>`），容器名 `astrbot`，Dashboard WebUI `:6185`
> 本文记录把 **「重要 AI 配置文档」约 310 份** 喂进鲸鱼娘知识库、并让它真正答得上来的完整过程，重点是**踩过的每一个坑和解决办法**。
> 所有密钥 / 密码 / token 均已脱敏（见文末 §13 对照表）。

---

## 0. 一句话结论

知识库 RAG 在 AstrBot 上**能用**，但有两个关键认知：

1. AstrBot 的 embedding **必须走远程 API**（本地不跑向量模型），索引用 FAISS + SQLite + BM25 混合召回，NAS 本地几乎零负载。
2. 对**通用聊天机器人**（鲸鱼娘是聊天 bot），知识库**必须用 agentic 模式**（让 LLM 自己决定查不查），**不能**用自动注入 —— 否则每条消息都塞无关知识块，连 `1+1` 都能被带偏。

---

## 1. 背景与目标

鲸鱼娘是跑在 NAS 上的 AstrBot 机器人，要基于用户多年积累的「重要 AI 配置文档」（NAS / 代理 / 模型 / OpenClaw / 语音生图等约 310 份 md 文档）做随身问答。

目标：把这堆文档建成知识库，让鲸鱼娘问「relay token 在哪」「mihomo 怎么分流」时能检索到正确内容。

按用户硬性规则：**落地任何功能前必做设备压力评估，落地后必做真实验证**。

**设备压力评估结论（LOW）**

| 维度 | 评估 |
|---|---|
| CPU | 极低（无模型常驻，embedding 走远程 NIM） |
| 内存 | 极低（FAISS / SQLite 轻量） |
| 磁盘 | 极低（310 份约 8.5MB） |
| 出网 | 仅摄入期有 embedding 请求 |
| 模型权重 | 完全不下载 |

---

## 2. 知识库架构（源码实查）

```
用户文档 ──摄入(multipart)──> 服务端解析 + 分块(chunk_size=800, overlap=120)
                                      │
                                      ▼
                   FAISS 向量索引 + SQLite 元数据 + BM25 稀疏索引
                                      │  混合召回: dense top_k + sparse top_k → RRF 融合
                                      ▼
                  检索返回 top_m_final 个分块 ──> 注入对话上下文
```

- 远程 **embedding API**（无本地模型）：`provider_type: "embedding"`
- 本地 **FAISS** 向量索引 + **SQLite** + **BM25** 稀疏混合召回
- 检索接口：`POST /api/v1/knowledge-bases/{kb_id}/retrieve`，参数**必须含 `kb_names: [知识库名]`**（不是 kb_id）

---

## 3. embedding provider 选型（用户已配模型逐一排查）

用户要求**优先用已有的本地 / 已配模型**，不要新开 key。逐一实测：

| 候选 | 结果 |
|---|---|
| pplx 代理（`poke-grok_source`）的 `/v1/embeddings` | **404**，不可用 |
| PC 本地 Ollama `:11434` | 当前不可达 |
| NIM `nvidia/embed-qa-4` | 404 |
| NIM `snowflake/arctic-embed-l` | 404 |
| NIM `nv-embedqa-1b-v2` | EOL |
| **NIM `nvidia/nemotron-3-embed-1b`** | ✅ 返回真实 **2048 维**向量，免费，容器内直连公网无需代理 |

→ 用户确认用 **NIM `nvidia/nemotron-3-embed-1b`**（NVIDIA NIM Key B）。

**实跑验证**（用 AstrBot 自带的 `NvidiaEmbeddingProvider` 类，不是自定义脚本）：返回 2048 维向量；语义相似度正确（相关句 0.71 > 无关天气句 0.44）。

---

## 4. 前置大坑：Dashboard 登录的 4 个连环坑

整件事最耗时的不是建库，而是**进不了 Dashboard API**。四个连环坑：

### 4.1 坑① 容器路径大小写（两份配置）—— 最隐蔽的误判根因

容器中源码真实路径是 **`/AStrBot/...`（小写 s）**。前期一直用 `/AStrBot`（**大写 S**）去 `cat / ls / grep / open`，全部报 "No such file"，一度以为有「shell 路径解析怪癖」，浪费了大量轮次。

真实原因：磁盘上**存在两份独立配置文件**（见坑 ④），且 `find` 是大小写不敏感的 —— 所以 `find -exec cat` 能成功，而直接 `cat` 失败。

> **教训：直接读文件失败但 find 能找到时，先怀疑大小写。**
> 后文用 `/AStrBot`（大写 S）与 `/AStrBot`（小写 s）区分这两份，它们是**不同的 inode、不同的文件**。

### 4.2 坑② Dashboard 登录 401（随机初始密码）

配置文件里写的 `dashboard.password=<MD5_HASH>` 登录被拒；自己设的密码也被拒。

根因（读 `dashboard.server` 源码 + 容器日志确认）：

```
dashboard.server:433: Initialized random JWT secret     # 启动若 jwt_secret 为空会随机生成并写回
Initial password: <DASHBOARD_PASSWORD>                  # 首次启动随机生成的初始密码在日志里
```

- **伪造 JWT 必然失败**：磁盘上的 `jwt_secret` 不是运行时密钥（每次启动随机重生成）。
- **config 里手填的密码也不是真密码**。
- **真密码 = 容器启动日志里的 `Initial password`**：

```bash
docker logs astrbot 2>&1 | grep -i -E 'password|密码'
```

> 补充：把密码改过并重启固化后，config 内的 pbkdf2 会成为有效密码（本文后续 WebUI 密码即 `<DASHBOARD_PASSWORD>`）。

### 4.3 坑③ API 前缀是 `/api/v1`，不是 `/api`

| 用途 | 正确路径 |
|---|---|
| 登录 | `POST /api/auth/login` |
| 建库 | `POST /api/v1/knowledge-bases` |
| 上传文档 | `POST /api/v1/knowledge-bases/{kb_id}/documents`（multipart） |
| 任务进度 | `GET /api/v1/knowledge-bases/tasks/{task_id}` |
| 统计 | `GET /api/v1/knowledge-bases/{kb_id}/stats` |
| 检索 | `POST /api/v1/knowledge-bases/{kb_id}/retrieve` |
| 注册 provider | `POST /api/v1/provider-sources` + `POST /api/v1/provider-sources/providers` |

早期用 `/api/knowledge-bases` 建库 → **405**。

### 4.4 坑④ embedding provider 必须走 API 热加载

只在 `cmd_config.json` 的 `provider_sources` 加 `nim_embed` **不够** —— `get_provider_by_id` 查的是 inst_map，由 **provider 列表**填充，不是 provider_sources。

正确做法（两步，无需重启）：

```bash
# 1. 建 source
POST /api/v1/provider-sources
{ "config": { "id": "nim_embed", "type": "nvidia_embedding",
              "enable": true, "embedding_api_key": "<NIM_KEY>",
              "embedding_model": "nvidia/nemotron-3-embed-1b" } }

# 2. 注册 provider（body 必须含 source_id + provider_type）
POST /api/v1/provider-sources/providers
{ "source_id": "nim_embed", "id": "nim_embed", "type": "nvidia_embedding",
  "provider": "nvidia", "provider_type": "embedding", "enable": true,
  "embedding_api_key": "<NIM_KEY>",
  "embedding_model": "nvidia/nemotron-3-embed-1b", "embedding_dimensions": 2048 }
```

之后 `create_kb` 才不再报「嵌入模型不存在」。

---

## 5. 建库 + 全量摄入

### 5.1 建库

`POST /api/v1/knowledge-bases`：

```json
{
  "kb_name": "重要AI配置文档",
  "embedding_provider_id": "nim_embed",
  "chunk_size": 800, "chunk_overlap": 120,
  "top_k_dense": 5, "top_k_sparse": 5, "top_m_final": 6
}
```

返回 `kb_id=6e7f6583-b5ed-4651-83c8-d2c2d980d534`（环境不同值不同，记录到 `kb_id.txt`）。

### 5.2 摄入接口（关键：multipart，不是 JSON）

`POST /api/v1/knowledge-bases/{kb_id}/documents`：

- Content-Type：`multipart/form-data`
- 文件字段名：`file` / `file*` / `files[]`（服务端按 `key == "file" or key.startswith("file") or key == "files[]"` 收集，支持多文件）
- form 可选字段：`chunk_size`、`chunk_overlap`、`batch_size`
- 服务端自动解析 md 并分块 → 返回 `task_id`

> ⚠️ 另一个接口 `/documents/import` 是 **JSON 接口**，要求自己传 `file_name` + `chunks: list[str]`（已分好块），**不适合原始文件上传**。

### 5.3 摄入范围与耗时

- 文本类（md / py / js / json / yaml / sh / bat / html 等，跳过 png / zip / svg / lnk）：**共 286 文件**
- 逐批 20 个**串行**（避免打满 NIM 免费限流），约 **13 分钟**跑完全部 embedding 任务
- 最终：**171 文档 / 3026 分块**

**样本验证**（先跑 1 个文件）：1 文档 → 23 分块；retrieve「relay token 在哪里配置」命中 `00_核心参数速查总表.md`（score 0.9）→ NIM embedding + FAISS + BM25 混合召回端到端跑通。

---

## 6. 召回质量清洗（重要）

全量摄入后检索验证，发现**召回被垃圾块污染**：

| 问题 | 表现 | 处理 |
|---|---|---|
| 第三方开源项目 README（15 份） | 无名杀 / Antigravity 项目说明，词汇量大、与问答无关，却因关键词匹配**霸占 BM25 top1** | 删除源文档 |
| 一次性产物（AGY直控验证_*.md 等 12 份） | 临时验证报告，短且碎片化 | 删除源文档 |
| 「毒药分块」（约 119 个） | 只含 breadcrumb + 分隔线、无实质正文，embedding 接近常量，**任何查询都给固定高分 0.9** | `DELETE /chunks/{chunk_id}` |

**毒药块识别**（剥离 breadcrumb / 标题符号 / 分隔线后，实质正文 < 30 字即判垃圾）：

```python
def essence(t):
    t = (t or '').replace('...', ' ')
    if '>' in t: t = t.split('>')[-1]        # 去 breadcrumb
    t = re.sub(r'-{3,}', '', t)              # 分隔线
    t = re.sub(r'[#*`|~\[\]()]', '', t)
    return re.sub(r'\s+', '', t)
```

> **已知局限**：AStrBot 的 `DELETE /chunks` 只删 SQLite 记录、**不会更新 FAISS 索引**（`chunk_count` 不降），属框架已知行为。质量靠「排除法」（删源文档）缓解，比调参更彻底。
>
> 另外测过 `top_k_sparse=0`（关稀疏召回）：分数**不变** → 确认异常来自空块向量本身，不是 BM25 权重问题。

---

## 7. 致命坑：两份独立配置文件（我造成的对话模型丢失）

**这是本次最严重的事故，单独强调。**

### 现象

摄入完成、配置 `kb_names` 绑定后重启，鲸鱼娘**不能聊天了**，报：

```
LLM 请求失败：未找到任何可用的对话模型（提供商）
```

### 根因

磁盘上存在**两份独立的 `cmd_config.json`**：

| 路径 | 内容 |
|---|---|
| `/AStrBot/data/cmd_config.json`（**大写 S**） | 完整：含 poke-grok / edge_tts / sensevoice / nim_embed |
| `/AStrBot/data/cmd_config.json`（**小写 s**） | **被我早期编辑覆盖成只剩 nim_embed** |

- 运行实例实际读的是 **小写 s 那份**
- 该文件有**重复键**（`provider` / `provider_sources` / `dashboard` 各出现两次）
- 用 `json.load` 重写会**取最后一个值、丢字段** —— 我的某次编辑把 `provider` 列表覆盖成只剩 nim_embed
- 结果：重启后 `poke-grok_source/grok-4.6` 丢失

### 修复

1. 以**完整版**（大写 S 那份）为基准
2. 合并 nim_embed provider 条目 + 补 `kb_names`
3. **用 `utf-8-sig` 写回两份**，消除不一致（注意文件带 BOM，用 `utf-8` 读会报错）
4. 重启，日志确认三件套全加载：

```
Loading model openai_chat_completion(poke-grok_source/grok-4.6)
Selected openai_chat_completion(poke-grok_source/grok-4.6) as default chat model provider
Loading model nvidia_embedding(nim_embed)
```

---

## 8. 端到端验证（通过）

WebChat 发问：「mihomo 里 poke2api 走什么规则？直接给规则原文。」

鲸鱼娘（poke-grok-4.6）输出知识库原文：

```
DOMAIN,www.poke2api.com,DIRECT
DOMAIN,www.pokeapi.top,DIRECT
```

非 LLM 杜撰（可精确到该文档的 DIRECT 规则），确证知识库已注入对话。

**结论：S 级知识库 RAG 功能落地可用。** 召回质量中等（top1 正确率约 60%，但 `top_k=6` 足够 LLM 识别正确块）。

---

## 9. 自动注入污染正常对话 + agentic 修复（用户反馈的坑）

### 现象（用户实测发现）

用户问「1+1」，鲸鱼娘答非所问，回答里混入游戏 mod、NAS 包等**无关知识库内容**。

### 根因

用了 `kb_agentic_mode: false`（**自动注入**模式）→ **每条消息都检索 KB 并注入上下文**。而库里混有大量无关文档（游戏 mod 101 份 / 书源 / 第三方项目），噪声块把 LLM 带偏。

> 自动注入只适合「纯知识库问答 bot」；鲸鱼娘是通用聊天 bot，必然翻车。

### 修复：切 agentic 模式

```json
"kb_agentic_mode": true
```

LLM 自己判断是否调用 `astr_kb_search` 工具 —— 简单对话不触发检索，知识问答才主动查。

**验证**

| 提问 | 结果 |
|---|---|
| `1+1等于几？只回答数字。` | **2**（干净，无 KB 干扰） |
| `mihomo 里 poke2api 走什么规则？` | grok-4.6 **主动调工具**，输出知识库原文 `DOMAIN,www.poke2api.com,DIRECT` |

**正常对话恢复 + 知识问答照常。**

---

## 10. 最终状态：停用但保留数据

用户决策：**暂停使用知识库，但保留数据，以后不再动它**。

操作（可逆，一步恢复）：

```json
"kb_names": []     // 清空即停用；填回 ["重要AI配置文档"] 即恢复
```

- 鲸鱼娘变回纯聊天
- 已摄入的 **171 文档 / 3026 分块数据原样保留**（未删除）
- 重启验证：`1+1` → `2`，对话模型未丢

---

## 11. 完整命令清单（脱敏）

```bash
# 0) 环境准备：Windows 侧访问 NAS 必须清代理，否则连不上局域网
export HTTP_PROXY= HTTPS_PROXY= NO_PROXY='*'

# 1) 拿 Dashboard 密码（首次启动的随机密码）
docker logs astrbot 2>&1 | grep -i -E 'password|密码'

# 2) 登录拿 JWT
POST http://<NAS_LAN_IP>:6185/api/auth/login   {"username":"astrbot","password":"<DASHBOARD_PASSWORD>"}

# 3) 注册 embedding provider（两步，见 §4.4）
POST /api/v1/provider-sources
POST /api/v1/provider-sources/providers

# 4) 建库 / 摄入 / 统计 / 检索（见 §5）
POST /api/v1/knowledge-bases
POST /api/v1/knowledge-bases/{kb_id}/documents          # multipart
GET  /api/v1/knowledge-bases/tasks/{task_id}            # 进度
GET  /api/v1/knowledge-bases/{kb_id}/stats
POST /api/v1/knowledge-bases/{kb_id}/retrieve           # 需 kb_names

# 5) 绑定对话（根级配置，两份文件都要改）
"kb_names": ["重要AI配置文档"], "kb_final_top_k": 6, "kb_agentic_mode": true

# 6) 每次改配置后必做：重启 + 验日志
docker restart astrbot
docker logs astrbot 2>&1 | grep -E 'Loading model|as default chat model provider'
```

**配套脚本**（Windows 侧驱动，均需清代理运行）：

| 脚本 | 用途 |
|---|---|
| `kb_build.py` | 建库 / 摄入（SAMPLE/ALL，支持断点续传）/ 统计 / 检索 |
| `kb_read.py` | 读容器内源码（绕开路径大小写坑） |
| `kb_clean.py` | 清理毒药分块（支持 `--delete` 与 `MIN_KEEP` 阈值） |
| `kb_bind.py` / `kb_repair.py` | 配置绑定 / 两份配置修复同步 |

---

## 12. 经验教训（AstrBot 配置铁律）

1. **`cmd_config.json` 可能有两份独立路径**（`/AStrBot/` 大小写不同、inode 不同）。运行实例读哪份取决于启动 cwd。**改前先确认运行实例实际读的那份**。
2. **该文件有重复键**（`provider` / `provider_sources` / `dashboard` 各两次）。用 `json.load` 重写会丢字段 → 必须**文本级插入 / 正则替换**，或只改目标那份。
3. **`docker restart` 后若 provider 丢失，bot 不能聊天**。改完配置必须重启并查日志确认 `Loading model ... as default chat model provider` 存在。
4. **改配置前先备份两份**（`*.bak_<用途>_<时间戳>`），本次靠备份恢复。
5. **知识库对通用聊天 bot 必须用 agentic 模式**，自动注入必然污染对话。
6. **Dashboard 密码在容器日志里**，不在配置文件里；`jwt_secret` 每次启动可能随机重生成，伪造 token 无效。

---

## 13. 敏感信息脱敏对照表

| 占位符 | 真实内容类别 | 说明 |
|---|---|---|
| `<NIM_KEY>` | NVIDIA NIM API Key | 形如 `nvapi-...`，本文用于 embedding |
| `<POKE_KEY>` | PokeAPI Key | 形如 `sk-...`，对话模型 `poke-grok_source` |
| `<DASHBOARD_PASSWORD>` | AstrBot WebUI 密码 | 含容器随机初始密码与自设密码 |
| `<JWT_SECRET>` | Dashboard JWT 密钥 | 每次启动可能随机重生成 |
| `<NAS_LAN_IP>` | NAS 局域网 IP | 私有地址（192.168.x.x），无公网暴露 |
| `<NAS_USER>` | NAS 用户名 | 用于 SSH / systemd user 服务 |
| `<RELAY_TOKEN>` | OpenClaw relay token | `:8910` 的 `X-Relay-Token` |
| `<QQ_BOT_APPID>` | QQ 官方机器人 AppID | AstrBot 的 `qq_official` 适配器 |

> 上传 GitHub 前已按此表全局替换，无真实密钥 / 密码 / token 残留。

---

## 附：本次交付物

- 知识库「重要AI配置文档」：embedding = NIM `nvidia/nemotron-3-embed-1b`，171 文档 / 3026 分块
- 配置：两份 `cmd_config.json` 已同步，`kb_names=[]`（停用待用），`kb_agentic_mode=true`
- 脚本：`kb_build.py` / `kb_read.py` / `kb_clean.py` / `kb_bind.py` / `kb_repair.py`
