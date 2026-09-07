# 配置占位符说明（CONFIG_PLACEHOLDERS）

本目录下的报告与脚本均已脱敏。运行前把占位符替换为你的真实值（**真实值只在你本地，不要提交回仓库**）。

| 占位符 | 含义 | 去哪找真实值 |
|---|---|---|
| `<NAS_LAN_IP>` | NAS 局域网 IP（如 `192.168.x.x`） | 路由器 / NAS 网络设置；本文 WebUI 端口 `:6185` |
| `<DASHBOARD_PASSWORD>` | AstrBot Dashboard WebUI 密码 | **容器日志里的 `Initial password`**：`docker logs astrbot 2>&1 \| grep -i 密码`；改过并重启固化后即为 config 内 pbkdf2 对应密码 |
| `<NIM_KEY>` | NVIDIA NIM API Key | NVIDIA NIM 控制台，形如 `nvapi-...` |
| `<POKE_KEY>` | PokeAPI Key | 对话模型 `poke-grok_source` 的 key，形如 `sk-...` |
| `<JWT_SECRET>` | Dashboard JWT 密钥 | `cmd_config.json` 的 `dashboard.jwt_secret`（**每次启动可能随机重生成，不要依赖它伪造 token**） |
| `<NAS_USER>` | NAS 登录用户名 | 用于 SSH / systemd user 服务 |
| `<WIN_DOC_DIR>` | Windows 侧待摄入文档目录 | 例如 `C:\Users\<你>\Desktop\重要ai配置文档` |
| `<SCRIPT_DIR>` | 本脚本所在目录 | 例如 `C:\Users\<你>\.workbuddy\nas_test` |
| `<MD5_HASH>` | 旧的 md5 形式 dashboard 密码 | 仅作对照，v4.27 已改用 pbkdf2 |

## 运行前置

```bash
# Windows 侧访问 NAS 局域网必须清代理，否则连不上
export HTTP_PROXY= HTTPS_PROXY= NO_PROXY='*'
```

## 脚本依赖

`kb_build.py` / `kb_bind.py` / `kb_repair.py` 通过 `nas_ssh.py` 连 NAS 执行容器内命令。
`nas_ssh.py` **未包含在本仓库**（内含真实 NAS SSH 凭据），请自行准备一个提供 `run_cmd(cmd, sudo=False, timeout=120)` 的模块。

| 脚本 | 用途 |
|---|---|
| `kb_build.py` | 建库 / 摄入（`SAMPLE` / `ALL`，支持断点续传）/ 统计 / 检索 |
| `kb_read.py` | 读容器内源码（绕开路径大小写坑） |
| `kb_clean.py` | 清理「毒药分块」（`--delete` 执行，`MIN_KEEP` 调阈值） |
| `kb_bind.py` | 根级写入 `kb_names` 绑定知识库 |
| `kb_repair.py` | 修复「两份配置文件不一致」导致 provider 丢失 |
