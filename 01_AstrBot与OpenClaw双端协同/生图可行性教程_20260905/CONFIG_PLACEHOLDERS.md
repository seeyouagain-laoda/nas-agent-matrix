# 占位符对照表（部署前需回填）

> 本文档与代码中的 `<...>` 均为占位符，真实值见你本地配置文件（桌面「重要AI配置文档」）。

| 占位符 | 含义 | 示例/原值形态 |
|--------|------|----------------|
| `<NAS_LAN_IP>` | NAS 局域网 IP | `192.168.x.x` |
| `<NAS_SSH_USER>` | NAS SSH 用户名 | 如 `半夏` |
| `<NAS_SSH_PASSWORD>` | NAS SSH 密码 | 本地配置，勿提交 |
| `<RELAY_TOKEN>` | relay 鉴权 Token（插件与 relay 共用） | 长 hex 串 |
| `<NAS_DATA_DIR>` | NAS 上 astrbot 数据根目录 | `/vol4/qq-whale/astrbot_data` |
| `<GEN_DIR>` | relay 可写生图目录 | `/vol4/qq-whale/memes/generated` |
| `<MEME_DIR>` | 表情包/图库目录 | `/vol4/qq-whale/memes` |
| `<GEMINI_CDP_PORT>` | Gemini 浏览器 CDP 调试端口 | `127.0.0.1:16002`（本机回环，无需脱敏） |

## 代码内需要回填的位置

- `openclaw_controller/main.py`：`RELAY_URL` / `IMAGE_URL` / `IMAGE_GEMINI_URL` 里的 `<NAS_LAN_IP>`、`RELAY_TOKEN = "<RELAY_TOKEN>"`。
- `gemini/gemini_gen_nas.js`：环境变量 `GEMINI_SCREENSHOT_DIR`（默认 `<GEN_DIR>`）、CDP 地址（默认本机回环）。
- relay（`生成参考修复_20260904/relay/openclaw_relay.py`）：`<NAS_LAN_IP>`、`<RELAY_TOKEN>`、`<NAS_SSH_PASSWORD>` 等。
