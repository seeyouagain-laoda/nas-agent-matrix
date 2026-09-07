import paramiko
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)

# 抓最近包含 _on_any_message 或 NoneType 的日志段（带上下文）
_, o, e = c.exec_command("docker logs astrbot 2>&1 | grep -n -B2 -A25 'on_any_message\\|NoneType' | tail -80")
print(o.read().decode(errors='replace').strip())
print("----ERR----", e.read().decode(errors='replace').strip())

# 也抓最近的完整 Traceback
_, o2, _ = c.exec_command("docker logs astrbot 2>&1 | grep -n -A30 'Traceback (most recent call last)' | tail -60")
print("==== RECENT TRACEBACK ====")
print(o2.read().decode(errors='replace').strip())
c.close()
print("DONE")
