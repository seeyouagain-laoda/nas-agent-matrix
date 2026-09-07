import os, glob, re

WS = r"C:\Users\user\WorkBuddy\20260407224338"
STAGE = r"C:\Users\user\Desktop\astrbot-openclaw-whale-guide-upload\生成参考修复_20260904"

# 脱敏替换（顺序：先精确，后正则）
REPL = [
    ("<NAS_LAN_IP>", "<NAS_LAN_IP>"),
    (r"192\.168\.\d{1,3}\.\d{1,3}", "<NAS_LAN_IP>"),
    ("<NAS_SSH_PASSWORD>", "<NAS_SSH_PASSWORD>"),
    ("<NAS_SSH_USER>", "<NAS_SSH_USER>"),
    ("<RELAY_TOKEN>", "<RELAY_TOKEN>"),
    ("<NAS_DATA_DIR>", "<NAS_DATA_DIR>"),
]
def sanitize(text):
    for a, b in REPL:
        if a.startswith(r"192\."):
            text = re.sub(a, b, text)
        else:
            text = text.replace(a, b)
    return text

os.makedirs(STAGE, exist_ok=True)
os.makedirs(os.path.join(STAGE, "scripts"), exist_ok=True)
os.makedirs(os.path.join(STAGE, "openclaw_controller"), exist_ok=True)
os.makedirs(os.path.join(STAGE, "relay"), exist_ok=True)

TEXT_EXT = (".py", ".js", ".yaml", ".yml", ".md", ".txt", ".json", ".sh", ".html", ".bat", ".cfg", ".ini")
count = 0
for path in sorted(glob.glob(os.path.join(WS, "_*"))):
    if not os.path.isfile(path):
        continue
    ext = os.path.splitext(path)[1].lower()
    if ext not in TEXT_EXT:
        continue
    name = os.path.basename(path)
    try:
        raw = open(path, "r", encoding="utf-8", errors="replace").read()
    except Exception as e:
        print("SKIP", name, e); continue
    clean = sanitize(raw)
    with open(os.path.join(STAGE, "scripts", name), "w", encoding="utf-8") as f:
        f.write(clean)
    count += 1
print("staged scripts:", count)

# 精选交付：插件 / relay / metadata
def stage_curated(src_name, dst_rel):
    src = os.path.join(WS, src_name)
    if not os.path.isfile(src):
        print("MISSING", src_name); return
    raw = open(src, "r", encoding="utf-8", errors="replace").read()
    clean = sanitize(raw)
    dst = os.path.join(STAGE, dst_rel)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(clean)
    print("curated:", dst_rel)

stage_curated("_new_main.py", "openclaw_controller/main.py")
stage_curated("_relay_current.py", "relay/openclaw_relay.py")
stage_curated("_meta144.yaml", "openclaw_controller/metadata.yaml")

# 报告也放进仓库
report_src = r"C:\Users\user\Desktop\鲸鱼娘_生成参考修复报告_20260904.md"
if os.path.isfile(report_src):
    raw = open(report_src, "r", encoding="utf-8", errors="replace").read()
    with open(os.path.join(STAGE, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write(raw)
    print("curated: REPORT.md")

# 占位符说明
PH = """# 占位符对照表（部署前需回填）

本仓库所有敏感信息已脱敏为以下占位符。实际部署时请替换：

| 占位符 | 含义 | 示例 |
|--------|------|------|
| `<NAS_LAN_IP>` | NAS 局域网 IP | `<NAS_LAN_IP>` |
| `<NAS_SSH_USER>` | NAS SSH 用户名 | `<NAS_SSH_USER>` |
| `<NAS_SSH_PASSWORD>` | NAS SSH 密码 | — |
| `<RELAY_TOKEN>` | AstrBot↔relay 鉴权 Token（`X-Relay-Token`） | — |
| `<NAS_DATA_DIR>` | NAS 上 astrbot 数据根目录 | `<NAS_DATA_DIR>/astrbot_data` |
| `<GEN_DIR>` | relay 可写生图目录（host 侧） | `<NAS_DATA_DIR>/memes/generated` |

## 回填位置提醒
- 插件 `openclaw_controller/main.py`：`RELAY_URL` / `IMAGE_URL` / `IMAGE_GEMINI_URL` 里的 `<NAS_LAN_IP>`；`RELAY_TOKEN`。
- relay `relay/openclaw_relay.py`：`GEN_DIR` 里的 `<NAS_DATA_DIR>`；监听地址里的 `<NAS_LAN_IP>`。
- 部署脚本 `scripts/*.py`：SSH `HOST` / `USER` / `PW` 字段。

## 两份部署要点（详见 REPORT.md §5/§6）
docker 绑定 `<NAS_DATA_DIR>/astrbot_data -> /AStrBot/data` 运行时可能飘移，插件文件须同时写：
1. host 绑定源 `<NAS_DATA_DIR>/plugins/openclaw_controller/`
2. 容器 overlay（docker cp 进 /tmp 再 docker exec cp 进插件目录）
`metadata.yaml` 的 `version:` 与 `main.py` 的 `@register(version=...)` 须保持一致。
"""
with open(os.path.join(STAGE, "CONFIG_PLACEHOLDERS.md"), "w", encoding="utf-8") as f:
    f.write(PH)
print("curated: CONFIG_PLACEHOLDERS.md")

print("STAGE DIR:", STAGE)
