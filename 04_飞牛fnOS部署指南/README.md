# OpenClaw 在飞牛 fnOS 上的完整实践

> 在飞牛 fnOS（或其他 Linux NAS）上把 [OpenClaw](https://github.com/tailscale/tailscale)（开源自托管 AI Agent 框架）跑成家庭 AI 中枢：安装、每日健康报告、任务完成微信通知、浏览器 CDP 接入。
> 本文所有 `NAS-LAN-IP`、`TOKEN`、`PATH` 均为占位符，请按实际替换。

## 1. 安装与运行

OpenClaw 在 NAS 上以 **systemd 用户级** 服务运行（非 root），操作**不要套 sudo**，否则会遇到权限/目录错乱。

```bash
# 查看状态 / 修复
openclaw status
openclaw doctor --fix

# API 默认端口（示例）
#   http://<NAS-LAN-IP>:9090
# 配置目录（用户级，典型路径）
#   ~/.config/openclaw/   或   ~/openclaw/
```

关键经验：

- **绝不套 sudo**：NAS 上的 OpenClaw 是用户级 systemd，sudo 会写到 root 的目录，导致配置读不到。
- 端口冲突（如 `8443` 被占用）时，先 `openclaw doctor --fix` 再查监听；曾因 fnOS 自带 nginx 占用导致 8443 排障，需改 OpenClaw 监听端口或释放冲突端口。

## 2. 每日健康报告自动推送

目标：每天 07:00 让 OpenClaw 读昨日 SQLite 数据 → LLM 生成简报 → Server酱推微信。

```
cron(每天 07:00)
  └─ gen_daily_report.sh
       ├─ 读 SQLite 昨日数据
       ├─ openclaw agent 调 LLM 生成报告
       └─ Server酱 推微信
```

要点：

- 报告脚本读 OpenClaw 自己的 SQLite（对话/任务记录）。
- LLM 生成段建议用「结构化输出」并把 JSON 落库，便于次日对比。
- 完整触发链路见 [wechat-notify.md](wechat-notify.md)（Server酱接入）。

## 3. 任务完成 → 微信通知

用 `openclaw_run` 包装器 + `message:sent` 钩子，在任务跑完时自动推微信。踩过的 5 个坑：

1. 钩子不是 Claude Code 风格，`hooks` 配置字段不同，照搬会静默不触发。
2. 必须配置 `hooks.token`，否则钩子被拒。
3. CLI 默认**不**发 `message:sent` 事件，需在包装器里显式触发。
4. 用 `-m` 传参时注意引号/转义，参数错了任务照样"成功"但内容空。
5. 改了 `baseUrl` 要**备份回退**，否则远端连不上时无法恢复。

## 4. 浏览器画面 / 自动化接入（CDP）

想在 PC 上看到 NAS 里 OpenClaw 的浏览器画面、或做浏览器自动化：

- **当前推荐**：飞牛内置 `fygo` + Chromium CDP，端口 `16002`（示例 `<NAS-LAN-IP>:16002`）。
- **旧栈**：noVNC `6080` / CDP `9101` 已是历史方案，不要再按旧文档启用。
- PC 端看 noVNC 前**先关本机 Clash 等全局代理**，否则会假 502。

⚠️ **flaresolverr 教训**：曾为解 Cloudflare 挑战启用 `flaresolverr` 容器，结果与反代 `/health` 形成死循环、疯狂烧 CPU。该组件已停用，不要在 OpenClaw/反代方案里重新启用它。

## 5. 参考

- OpenClaw 官方发布（自托管 AI Agent 框架）
- 飞牛 fnOS：https://www.fnnas.com
- 微信通知方案见 [wechat-notify.md](wechat-notify.md)
- 反代方案见 [reverse-proxies.md](reverse-proxies.md)
