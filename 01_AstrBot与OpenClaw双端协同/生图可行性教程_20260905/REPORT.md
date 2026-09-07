# 鲸鱼娘（QQ）生图机器人 —— 可行性教程报告（2026-09-04 ~ 09-05 合并版）

> 环境：飞牛 fnOS NAS（局域网）、AstrBot 4.27.5（Docker）、OpenClaw relay（systemd）、NAS 浏览器 Gemini（fygo CDP）。
> 结论先行：**方案完全可行，端到端回图 40–55 秒，其中 95%+ 时间花在 Gemini 浏览器生图本身；插件 + relay 转发开销 < 1 秒，NapCat 投递 ≈ 4 秒。** 今天把“回的是浏览器截图而非成图 / 失败静默卡死 / Gemini 对话式拒绝不告知 / 参考图上传不等就发 / 梗图发成链接”五个体验坑全部修平，现已“非常完美”。

---

## 0. 可行性结论（TL;DR）

| 维度 | 结论 |
|------|------|
| 功能可行性 | ✅ 已跑通：`/任务`、`/梗图`、`/生成`、`/生成参考` 四条指令全部可用 |
| 端到端时延 | ⏱ 40–55s（纯 bot 管线），用户感知≈1 分钟 |
| 时延主因 | Gemini 浏览器（CDP 驱动网页）生图本身，非代码瓶颈 |
| 稳定性 | Gemini 网页偶发不稳（裁切兜底/发送超时），已加失败兜底 + PokeAPI 双生图后端 |
| 最大坑 | ① 截图冒充成图 ② 失败静默卡死 ③ 梗图 CDN 图发成链接 —— 均已修复 |

---

## 1. 整体架构

```
QQ 用户
  │ (NapCat / OneBot)
  ▼
AstrBot 容器 (Docker)  ── 插件 openclaw_controller (main.py)
  │  /生成 → POST http://<NAS_LAN_IP>:8910/image-gemini
  │  /任务 → POST http://<NAS_LAN_IP>:8910/run
  ▼
OpenClaw relay (systemd, host)  ── openclaw_relay.py
  │  /image-gemini → 拉起 node gemini_gen_nas.js
  ▼
Chrome (fygo, CDP 127.0.0.1:16002)  ── 驱动 gemini.google.com 生图
  │  裁切成品 <img> → 截图保存
  ▼
/vol4/qq-whale/memes/generated/*.png  ── AstrBot 用 Image.fromFileSystem 回图
```

三条生图链路：

| 指令 | 后端 | 兜底 |
|------|------|------|
| `/生成 <提示>` | NAS 浏览器 Gemini（带附图即参考图） | 失败自动切 PokeAPI（gpt-image-2） |
| `/生成参考 <描述>` | NAS 浏览器 Gemini（用户单独发参考图，base64 绕过只读挂载） | 同上 |
| `/梗图 [标签]` | whale-chan 935 张表情包（CDN 热链 / 本地） | 索引缺失回退本地图库 |

---

## 2. 端到端耗时实测（2026-09-05 01:41 那一发“非常完美”样例）

日志来源：AstrBot 容器日志（QQ 到达 + 回图）+ relay 日志（Gemini 起止）。

| 阶段 | 时间戳 | 本段耗时 | 说明 |
|------|--------|----------|------|
| QQ 收到文字指令 `/生成参考 ...` | 01:41:55.713 | — | 用户发第一条 |
| QQ 收到参考图 `[图片]` | 01:42:04.486 | 8.8s | **用户侧发图延迟**（非 bot 责任） |
| relay 解码参考图 + 启动 Gemini | 01:42:05.046 | 0.6s | 插件→relay 转发 + base64 解码 |
| Gemini 浏览器生成 | 01:42:05.046 → 01:42:48.139 | **43.1s** | 占绝对主导 |
| AstrBot 回图（Prepare to send） | 01:42:48.145 | ~0s | 图片已在本地，瞬间发出 |
| NapCat 投递到 QQ | 01:42:51.925 | 3.8s | QQ 上传/投递耗时 |

**汇总**

- 纯 bot 管线（从参考图到手 → 回图）：**≈ 43.7s**
- 含用户发图思考时间（首条指令 → 回图）：**≈ 56.2s**
- Gemini 生成占总 bot 时间：**≈ 99%**

**多个 `/生成`（无参考图）样例，仅 relay 侧生成耗时：**

| 起 | 止 | 生成耗时 |
|----|----|----------|
| 00:30:14 | 00:31:02 | 48.5s |
| 00:41:22 | 00:42:04 | 41.7s |
| 00:44:15 | 00:44:50 | 34.7s |
| 01:09:30 | 01:10:09 | 39.0s |
| 01:13:00 | 01:13:47 | 47.0s |

→ **平均约 43s，区间 35–50s**，与参考图样例一致。结论：**时延瓶颈 100% 在 Gemini 网页生图，代码优化空间几乎为零；要提速只能换更快的生图后端或并发预生成。**

---

## 3. 今天修复的五个体验坑（根因 + 解法）

### 坑 1：回的是“浏览器截图”而不是生成的图

**现象**：`/生成` 返回的是带 Gemini 网页 UI 整页截图，不是干净成图。
**根因**：`gemini_gen_nas.js` 里 `findGenImg()` 把 `const src = im.src` 写在 `for` 块作用域内，却在块外 `return {... src}` —— 每次都 `ReferenceError`，主路径永远返回 null → 退化到“整页截图兜底”。
**修复（v4）**：重写作用域 + “取面积最大的 `<img>` 成品图”；CDP 截图补 `clip.scale:1`（否则 `Failed to deserialize params.clip.scale` 报错）。
**验证**：自测返回 `1024x1024 RGBA` 纯图（蓝发鲸鱼娘），无 UI。

### 坑 2：图片生成失败时静默卡死

**现象**：Gemini 内容拦截/超时后，bot 一直在转圈不回复。
**根因**：插件没有对 relay 返回的 `error` 字段做早退。
**修复（插件 v1.4.7）**：`_do_gemini_gen` 增加早退分支——
- 命中 `内容安全/拦截/blocked/policy/safety` → “鲸鱼娘画不出这张图：Gemini 拒绝了这条提示（原因）”
- 命中 `timeout/timed out` → “Gemini 浏览器超时，稍后重试”
- 命中 `Gemini 说：` → “Gemini 没明白这条提示，原话如下：… 你可以换种说法再试”
均 `return`，不再静默。

### 坑 3：Gemini 对话式拒绝（没懂意思）不告诉用户

**现象**：Gemini 没生图，而是回了句“图中女子头上没顶盆…”，bot 却当失败或卡住。
**根因**：之前的脚本只抓成图，不抓 Gemini 的对话文本；用户收到的是空或非图。
**修复（JS v5/v6 + 插件 v1.4.8）**：
- JS 新增 `findAssistantText()`（选择器覆盖 `model-response` / `message-content` / `markdown-main-panel` / `conversation-turn`），把 Gemini 最后一段助手文本挂到 `detail` 上：`… ｜ Gemini 说：「<文本>」`。
- 插件检测 `"Gemini 说："` 直接把原文转述给用户，并跳过 PokeAPI 兜底（避免把“对话回复”误当失败去兜底生图）。
**验证**：发“1+1=几（不要生图）” → 正确回“Gemini 说 1 + 1 等于 2”。

### 坑 4：参考图上传不等就发，导致生图不带参考

**现象**：带参考图时，Gemini 经常没用到参考图（或发送失败）。
**三重根因（v7→v11 逐层修）**：
1. 标签数组 `"添加"` 误匹配历史消息里的“更多选项”按钮 → 用 `EXCLUDE_RE` 排除 `…的更多选项/more options/more_vert`。
2. `fileInputs()` 判断 `typeof n === 'number'`，但 `Runtime.evaluate` 返回是两层 `{result:{value:N}}` → 用 `vget()` 正确取值。
3. 合成器（composer）未就绪就操作 → 加 20×1s 预等待 `(hasBtn||hasFile)&&hasBox`。

**最终（v11）**：上传前每 2s 轮询——检测发送按钮 `disabled`、上传忙（`busy`/进度条/预览 blob 数），至少等 **5s** 且 `busy=false` 才点发送；实测 `waited=6s`，成图真实带参考。

### 坑 5：梗图发的是“链接”而不是图

**现象**：`/梗图` 命中 CDN 远程图时，QQ 收到的是一条文本链接，不是图片。
**根因**：`_emit_meme()` 的 URL 分支误用 `event.image_result(url)`（**本地文件语义**）——把远程 URL 当本地路径读，读不到 → 框架退化成发文本链接。
**修复（插件 v1.4.9）**：URL 分支改用 `event.chain_result([Image.fromURL(val)])`，与 `/任务` 的 URL 图渲染路径完全一致（NapCat 下载 CDN 图后发图）。CDN `ai-meme.cdqyfdbymn.me` 经 NAS 实测 `HTTP 200`，NapCat 可正常拉取。
**验证**：已部署并确认加载 `(1.4.9)`，`grep` 确认 `Image.fromURL(val)` 上线。

---

## 4. 部署 SOP（每次改插件/JS 必做）

### 4.1 插件（AstrBot）

> ⚠ AstrBot 插件版本号取自 `metadata.yaml`，不是 `main.py` 的 `@register`。**两处版本都改**。

```bash
# 1) host 绑定源（绑定生效时用）
scp main.py  <USER>@<NAS_LAN_IP>:/vol4/qq-whale/astrbot_data/plugins/openclaw_controller/main.py
scp metadata.yaml <USER>@<NAS_LAN_IP>:/vol4/qq-whale/astrbot_data/plugins/openclaw_controller/metadata.yaml

# 2) 容器 overlay（绑定飘移失效时也生效，两份部署）
docker cp main.py astrbot:/tmp/main.py
docker exec astrbot cp /tmp/main.py /AStrBot/data/plugins/openclaw_controller/main.py
docker restart astrbot
# 验证：
docker logs --since 30s astrbot | grep "openclaw_controller"   # 应出现 (1.4.9)
```

### 4.2 生图脚本（NAS 浏览器 Gemini）

```bash
# gemini_gen_nas.js 是烤进 CDP 驱动的关键脚本，改完需同步到 NAS并重启 relay
scp gemini_gen_nas.js <USER>@<NAS_LAN_IP>:/home/<USER>/gemini_gen_nas.js
# relay 通过 subprocess 调起该 js；改完重启 relay 生效
sudo systemctl restart openclaw-relay
```

### 4.3 关键配置

| 项 | 值 |
|----|----|
| relay 地址（插件里必须用 **LAN IP**） | `http://<NAS_LAN_IP>:8910` |
| Gemini CDP 调试端口 | `127.0.0.1:16002`（fygo 浏览器） |
| relay 日志（看耗时/错误） | `/home/<USER>/.openclaw_relay.log`（不是 journald） |
| 成图落盘 | `/vol4/qq-whale/memes/generated/` |
| 容器挂载 | host `/vol4/qq-whale/astrbot_data` → 容器 `/AStrBot/data`（**运行时可能 BIND_INACTIVE，务必两份部署**） |

---

## 5. QQ 端到端验收清单

- [ ] `/生成 一只二次元蓝发鲸鱼娘在喝奶茶` → 约 40s 后收到**干净成图**（无浏览器 UI）
- [ ] `/生成参考 把这张图改成二次元风格` → 先回“参考图片呢” → 单独发图 → 收到带参考的成图
- [ ] 发违规提示（如辱骂词）→ 立即回“Gemini 拒绝了这条提示”，不卡死
- [ ] 发“1+1=几（不要生图）” → 回“Gemini 说 1+1 等于 2”，不生图也不兜底
- [ ] `/梗图 生气` → 收到**图片**（不是链接）；`/梗图` 随机也收图
- [ ] `/任务 查一下 NAS 正在运行的 docker 容器` → 回文本 + 可选图

---

## 6. 可复用经验（给以后维护的人）

1. **AstrBot 版本看 `metadata.yaml`**：改版本两处都改。
2. **docker 绑定挂载会飘移**：`docker inspect` 显示挂载 ≠ 运行时真挂载，`grep <挂载点> /proc/mounts` 验证；关键文件**两份部署**。
3. **容器只读挂载想落盘 → base64 绕过**：二进制编码进请求体，服务端解码到自己的可写目录。
4. **CDP 截图必须 `clip.scale:1`**，否则 `Failed to deserialize params.clip.scale`。
5. **`Runtime.evaluate` 是两层返回** `r.result.result.value`，别直接当数字用。
6. **pkill 自杀陷阱**：`pkill -f "gemini_gen_nas.js"` 会杀掉执行它的 shell，用 `pkill -f "[g]emini_gen_nas.js"`。
7. **远程图用 `Image.fromURL`，本地图用 `Image.fromFileSystem` / `event.image_result(本地路径)`**；别把 URL 塞进 `event.image_result()`，否则退化成链接。
8. **参考图上传要轮询等就绪**（按钮 disabled + busy 消失 + ≥5s），不能发完就立刻点发送。
9. **失败必须早退并告知用户**，不要依赖“等超时”来暴露问题。

---

## 7. 交付文件清单（随仓库）

| 路径 | 说明 |
|------|------|
| `openclaw_controller/main.py` | 插件 v1.4.9（含五个坑修复，已脱敏 IP/Token） |
| `openclaw_controller/metadata.yaml` | 插件元数据 v1.4.9 |
| `gemini/gemini_gen_nas.js` | CDP 生图脚本 v11（纯图 + 上传等待 + Gemini 文本提取） |
| `relay/openclaw_relay.py` | relay 服务（含 `reference_image_b64` 解码、`/image-gemini`） |
| `docs/鲸鱼娘_生成参考修复报告_20260904.md` | 09-04 参考图修复专报 |
| `docs/鲸鱼娘生图可行性教程报告_20260905.md` | 本报告（合并版） |
| `CONFIG_PLACEHOLDERS.md` | 占位符对照表 |

占位符：`<NAS_LAN_IP>` / `<NAS_SSH_USER>` / `<NAS_SSH_PASSWORD>` / `<RELAY_TOKEN>` / `<NAS_DATA_DIR>` / `<GEN_DIR>`。

---

*本报告由 WorkBuddy 整理，所有敏感信息已脱敏，可安全上传至公开仓库。*
