# 占位符对照表（部署前需回填）

本仓库所有敏感信息已脱敏为以下占位符。实际部署时请替换：

| 占位符 | 含义 |
|--------|------|
| `<NAS_LAN_IP>` | NAS 局域网 IP（如 `192.168.x.x`） |
| `<NAS_SSH_USER>` | NAS SSH 用户名 |
| `<NAS_SSH_PASSWORD>` | NAS SSH 密码 |
| `<RELAY_TOKEN>` | AstrBot↔relay 鉴权 Token（`X-Relay-Token` 头） |
| `<NAS_DATA_DIR>` | NAS 上 astrbot 数据根目录（docker 绑定源，如 `/vol4/xxx/astrbot_data`） |
| `<GEN_DIR>` | relay 可写生图目录（host 侧，与容器挂载无关） |

## 回填位置提醒
- 插件 `openclaw_controller/main.py`：`RELAY_URL` / `IMAGE_URL` / `IMAGE_GEMINI_URL` 里的 `<NAS_LAN_IP>`；`RELAY_TOKEN`。
- relay `relay/openclaw_relay.py`：`GEN_DIR` 里的 `<NAS_DATA_DIR>`；监听地址里的 `<NAS_LAN_IP>`。
- 部署脚本 `scripts/*.py`：SSH `HOST` / `USER` / `PW` 字段。

## 两份部署要点（详见 REPORT.md §5/§6）
docker 绑定 `<NAS_DATA_DIR> -> /AStrBot/data` 运行时可能飘移，插件文件须同时写：
1. host 绑定源 `<NAS_DATA_DIR>/plugins/openclaw_controller/`
2. 容器 overlay（docker cp 进 /tmp 再 docker exec cp 进插件目录）
`metadata.yaml` 的 `version:` 与 `main.py` 的 `@register(version=...)` 须保持一致。
