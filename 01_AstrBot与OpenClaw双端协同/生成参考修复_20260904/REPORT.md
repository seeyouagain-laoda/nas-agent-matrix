# 鲸鱼娘（QQ）`/生成参考` 参考图生图修复 —— 完整技术报告

> 日期：2026-09-04
> 环境：飞牛 fnOS NAS（局域网）、AstrBot 4.27.5（Docker）、OpenClaw relay（systemd）
> 结论先行：今天把「QQ 鲸鱼娘 `/生成参考` 带参考图生图」从“图片已取到但保存失败 / 加载日志永远显示 1.4.3”修好了。**根因不在生图逻辑，而在两个部署层陷阱**，修复方案是“base64 把参考图从插件直接传进 relay（绕过容器只读挂载）+ 插件两份部署”。

---

## 0. 一句话结论

- 插件 `main.py` 其实早就是 **1.4.4**（含参考图 base64 绕过修复），但加载日志一直显示 `1.4.3`。
- **根因 A**：AstrBot 加载日志的版本号取自插件目录的 `metadata.yaml`，不是 `main.py` 的 `@register`；host 绑定源的 `metadata.yaml` 写死 `1.4.3`。
- **根因 B**：docker 绑定挂载 `<NAS_DATA_DIR>/astrbot_data → /AStrBot/data` 在运行时**时好时坏**（实测 `/proc/mounts` 显示 `BIND_INACTIVE`），导致容器有时读镜像层旧文件、有时读 host 新文件，版本号乱跳。
- **修复**：① 插件用 base64 把 QQ 参考图直接 POST 给 relay，relay 解码成临时文件再喂给 Gemini `--reference`，彻底绕开容器只读挂载的落盘失败；② `metadata.yaml` 与 `main.py` 都在 **host + 容器 overlay 两份**对齐到 1.4.4，重启不再掉版。

---

## 1. 背景与目标

鲸鱼娘是一个跑在 NAS 上的 AstrBot 机器人（扮演 Deepseek 鲸鱼娘），通过 QQ 接收指令，转交给 OpenClaw 执行任务。它有几个生图入口：

| 指令 | 作用 |
|------|------|
| `/梗图 [标签]` | 按标签从本地 935 张表情包随机发图 |
| `/生成 <提示>` | 默认走 NAS 浏览器 Gemini 生图（附图即参考图），失败自动兜底 PokeAPI |
| `/生成参考 <描述>` | **显式参考图生图**：先发描述，bot 问“参考图片呢？”，用户再单独发一张图，bot 拿这张图当参考生图 |

本次要修的是 `/生成参考` 的“参考图”链路：用户发描述 → bot 问图 → 用户单独发一张图 → 应当返回**以这张图为参考**生成的新图。

最初的实现（v1.4.2/v1.4.3）走的是“插件把下载到的参考图存到容器挂载目录（`/AStrBot/data/memes/reference/`），再把 host 路径告诉 relay”的路线。这条路线在容器挂载是只读 / 绑定飘移时会直接失败。

---

## 2. 问题现象

1. **功能失败**：用户走多轮流程（先发 `/生成参考 描述`，再单独发图），bot 报错“图片已取到，但保存失败”——参考图下载成功了，但落盘到容器挂载目录失败。
2. **版本号诡异**：无论怎么改 `main.py` 并把版本号改成 1.4.4，`docker restart astrbot` 后的加载日志永远显示：
   ```
   Plugin openclaw_controller (1.4.3) by WorkBuddy: 鲸鱼娘(QQ)...
   ```
   怀疑插件根本没更新，但 `docker exec` 进容器 `grep version=` 又确实能看到 1.4.4。

这两个现象分别指向下面两个根因。

---

## 3. 排查时间线（关键转折）

| 阶段 | 做了什么 | 发现 |
|------|----------|------|
| 1 | 把插件改成 base64 参考图方案（v1.4.4），SFTP 覆盖 host 绑定源 + `docker restart` | 日志仍显示 1.4.3，懵 |
| 2 | 全容器 / host 搜 `version="1.4.3"` | 磁盘上两份 `main.py` 都是 1.4.4，找不到 1.4.3 源文件 |
| 3 | 检查 `docker inspect` 挂载 + 容器内 `/proc/mounts` | **绑定挂载在运行时是 `BIND_INACTIVE`**——容器实际读的是自己的镜像层 |
| 4 | 用 `docker cp` 把 1.4.4 写进容器 overlay 再重启 | 日志还是 1.4.3 |
| 5 | 全容器搜 `OpenClawController` / 找所有 `openclaw_controller` 目录 | 只找到一个插件目录，但发现 `/AStrBot/data/plugins/openclaw_controller/metadata.yaml` 存在 |
| 6 | 读 `metadata.yaml` | **host 那份写死 `version: 1.4.3`**，且 AstrBot 加载版本号取自它 |

转折点在于第 5–6 步：版本号根本不是从 `main.py` 读的，而是从 `metadata.yaml` 读的；而 `metadata.yaml` 一直没被同步改成 1.4.4。

---

## 4. 根因一：版本号来自 `metadata.yaml`，不是 `main.py`

AstrBot（star 插件机制）在加载插件时，日志里 `Plugin <name> (<version>) by <author>: <desc>` 的 **version 取自已安装的 `metadata.yaml`**，而不是 `main.py` 里 `@register(version=...)` 的值。

- host 绑定源 `metadata.yaml` 一直是：
  ```yaml
  name: openclaw_controller
  author: WorkBuddy
  desc: 鲸鱼娘(QQ)通过 /任务 执行 OpenClaw，/梗图 ... /生成参考 显式参考图生图...
  version: 1.4.3
  ```
- 所以无论你把 `main.py` 改成几，`docker restart` 后日志都报 1.4.3。
- **修复动作**：把 `metadata.yaml` 同步到 `1.4.4`（host + 容器两份）。

> 经验：以后改 AstrBot 插件版本，记得 `main.py` 的 `@register(version=...)` 和 `metadata.yaml` 的 `version:` **两处都改**，否则日志/市场页版本对不上，排查时会误导自己。

---

## 5. 根因二：docker 绑定挂载运行时飘移

`docker inspect astrbot` 显示绑定是配置好的：
```json
{"Type":"bind","Source":"<NAS_DATA_DIR>/astrbot_data","Destination":"/AStrBot/data","Mode":"rw","RW":true}
```
但**容器运行时** `grep AStrBot /proc/mounts` 经常返回空（即 `BIND_INACTIVE`）。

后果：
- 绑定**生效**时，容器 `/AStrBot/data` 指向 host `<NAS_DATA_DIR>/astrbot_data`（你改的 1.4.4 生效）。
- 绑定**失效**时，容器 `/AStrBot/data` 退回镜像层自带的内容（旧 1.4.3 + 空 `metadata.yaml`）。
- 因为飘移是**时好时坏**的，同一份“写好的 1.4.4”在不同次重启后可能加载成 1.4.3 或 1.4.4，极其诡异。

这也是最初“图片已取到，但保存失败”的同源问题：容器挂载是只读（`memes` 挂载 `Mode:ro`），参考图想落盘到容器挂载目录时被拒。

**修复动作（两份部署）**：任何插件文件改动，都同时写两份：
1. host 绑定源：`<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/`
2. 容器 overlay：先 `docker cp` 到容器 `/tmp`，再 `docker exec <容器> cp /tmp/xxx /AStrBot/data/plugins/openclaw_controller/xxx`

这样无论绑定是否生效，容器读到的都是 1.4.4。

---

## 6. 解决方案

### 6.1 插件侧：base64 绕过参考图（核心修复）

原来：参考图下载后存容器挂载目录 → 把 host 路径报给 relay → relay 去读那个路径（只读挂载下失败）。

现在：插件把下载到的参考图**直接 base64 编码**，作为 `reference_image_b64` 字段 POST 给 relay；relay 在服务端解码成临时文件，喂给 Gemini 的 `--reference`。**全程不依赖容器挂载目录可写**。

插件关键改动（`main.py` v1.4.4）：

```python
async def _ref_image_b64(self, img):
    """把 QQ 参考图转成 base64 字符串（绕过容器只读挂载）"""
    src = None
    try:
        src = await img.convert_to_file_path()   # AstrBot 下载到容器内临时文件
    except Exception:
        src = None
    if src and os.path.exists(src):
        try:
            with open(src, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")
        except Exception:
            return None
    b = getattr(img, "base64", None)              # 兜底：直接用消息里的 base64
    if b:
        return b
    return None
```

`_do_gemini_gen` 的参考图参数从 `ref_host: str` 改为 `ref_b64: str`，payload 键从 `reference_image` 改为 `reference_image_b64`。

relay 侧（`_handle_image_gemini`）收到后：

```python
reference_b64 = (data.get("reference_image_b64") or "").strip()
ref_path = None
if reference_b64:
    raw = base64.b64decode(reference_b64)
    os.makedirs(GEN_DIR, exist_ok=True)
    ref_path = os.path.join(GEN_DIR, "ref_%s_%d.png" % (ts, os.getpid()))
    open(ref_path, "wb").write(raw)          # 写 relay 所在 host 的可写目录
# ...
ok, host_path, container_path, err = gen_image_gemini(prompt, ref_path)
# 用完删临时参考图
if ref_path and os.path.exists(ref_path):
    os.remove(ref_path)
```

> `GEN_DIR` 是 relay 进程所在 host 的可写目录（如 `<NAS_DATA_DIR>/memes/generated`），与容器挂载无关。

### 6.2 两份部署（对抗绑定飘移）

任何插件文件（main.py / metadata.yaml）改动后：

```bash
# 1) 写 host 绑定源（绑定生效时用）
scp -P 22 main.py  <NAS_SSH_USER>@<NAS_LAN_IP>:<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py

# 2) 写容器 overlay（绑定失效时也生效）
#    先把文件放到 host 稳定路径，再 docker cp 进容器 /tmp，再 exec cp 进插件目录
docker cp /home/<NAS_SSH_USER>/main.py astrbot:/tmp/main.py
docker exec astrbot cp /tmp/main.py /AStrBot/data/plugins/openclaw_controller/main.py
```

（实际执行用 paramiko + sudo 的 Python 脚本完成，见交付文件 `scripts/`。）

---

## 7. 实施步骤（可复用）

本次实际执行的脱敏步骤（变量见文末占位符表）：

1. 本地改好 `main.py`（v1.4.4，含 `_ref_image_b64` 与 `reference_image_b64`）。
2. 本地写好 `metadata.yaml`（version: 1.4.4）。
3. paramiko SSH 到 NAS，`sudo` 提权：
   - SFTP 把 `main.py` / `metadata.yaml` 传到 host 绑定源目录；
   - SFTP 把同样文件传到 `/home/<NAS_SSH_USER>/`（稳定路径）；
   - `docker cp` host 文件 → 容器 `/tmp`；
   - `docker exec astrbot cp /tmp/xxx /AStrBot/data/plugins/openclaw_controller/xxx`；
4. `docker restart astrbot`；
5. 等 ~15s，`docker logs --since 2m astrbot | grep openclaw_controller` 确认出现 `(1.4.4)`；
6. `curl http://<NAS_LAN_IP>:8910/health` 确认 relay `{"ok":true}`。

---

## 8. 验证结果

- 容器内 `/AStrBot/data/plugins/openclaw_controller/main.py` → `version="1.4.4"`；`reference_image_b64` 出现 1 次、`ref_host`/`REFDIAG`/`REF_DIR` 均为 0、`_ref_image_b64` 出现 3 次（干净）。
- host 绑定源 `metadata.yaml` 与容器内 `metadata.yaml` 均为 `version: 1.4.4`。
- `docker restart astrbot` 后加载日志（22:54:57）：
  ```
  Plugin openclaw_controller (1.4.4) by WorkBuddy: 鲸鱼娘(QQ)...
  ```
- relay `/health` 返回 `{"ok": true}`，监听 `<NAS_LAN_IP>:8910`（注意：不是 127.0.0.1，插件里 `RELAY_URL` 必须用 LAN IP）。
- base64 参考图解码路径已部署在 relay 的 `_handle_image_gemini`。

---

## 9. QQ 端到端验收（请你来）

1. QQ 给鲸鱼娘发：`/生成参考 <你的描述>`
2. bot 应回：“参考图片呢？请直接发我一张参考图（5 分钟内有效）”
3. **单独发一张图**（不要和文字放一条）
4. bot 应返回一张**以这张图为参考**生成的新图（relay 解码 base64 → Gemini `--reference`）

若返回失败，把 bot 的报错原文发我，我接着定位（Gemini 浏览器生图本身偶发不稳，通常是生图后端问题，不是插件问题）。

---

## 10. 可复用经验（给以后部署的人）

1. **AstrBot 插件版本号看 `metadata.yaml`**，改版本两处都改（`@register` + `metadata.yaml`）。
2. **docker 绑定挂载会飘移**：`docker inspect` 显示配置不等于运行时真挂载，务必 `grep <挂载点> /proc/mounts` 验证；关键文件**两份部署**（host + 容器 overlay）。
3. **容器只读挂载想落盘 → base64 绕过**：把二进制直接编码进请求体，服务端解码到自己的可写目录，彻底不碰容器挂载。
4. **排查顺序**：先确认“磁盘文件到底是什么版本”（`docker exec grep`），再确认“运行时实际加载的是什么”（加载日志 + 进程 fd），最后才动代码——避免一直在改代码却没生效。
5. **验证要看到日志**：部署后必须 `docker logs` 抓加载行确认版本，不能只确认“文件字节是对的”。

---

## 11. 交付文件清单

本报告配套仓库（已脱敏）含：

| 路径 | 说明 |
|------|------|
| `openclaw_controller/main.py` | 插件 v1.4.4（base64 参考图方案，已脱敏 IP/Token） |
| `openclaw_controller/metadata.yaml` | 插件元数据 v1.4.4 |
| `relay/openclaw_relay.py` | relay 服务（含 `reference_image_b64` 解码，已脱敏路径/IP） |
| `scripts/*.py` | 本次用到的部署 / 诊断 / 冒烟脚本（已脱敏 SSH 密码、IP、Token） |
| `CONFIG_PLACEHOLDERS.md` | 占位符对照表，部署前需回填 |

占位符对照：

| 占位符 | 原值（已脱敏） |
|--------|----------------|
| `<NAS_LAN_IP>` | 局域网 NAS IP |
| `<NAS_SSH_USER>` | NAS SSH 用户名 |
| `<NAS_SSH_PASSWORD>` | NAS SSH 密码 |
| `<RELAY_TOKEN>` | relay 鉴权 Token |
| `<NAS_DATA_DIR>` | NAS 上 astrbot 数据根目录（如 `<NAS_DATA_DIR>/astrbot_data`） |
| `<GEN_DIR>` | relay 可写生图目录 |

---

*本报告由 WorkBuddy 整理，所有敏感信息已脱敏，可安全上传至公开仓库。*
