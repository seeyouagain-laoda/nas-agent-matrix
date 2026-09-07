import paramiko, time

host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)

stamp = time.strftime('%Y%m%d_%H%M%S')
base = "<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/"
for fn in ('main.py', 'metadata.yaml'):
    cmd = f"cp {base}{fn} {base}{fn}.bak_{stamp}"
    c.exec_command(cmd)
    print("BACKUP:", cmd)

sftp = c.open_sftp()
local = r"c:/Users/user/WorkBuddy/20260407224338/"
sftp.put(local + "_new_main.py", base + "main.py")
sftp.put(local + "_new_meta.yaml", base + "metadata.yaml")
sftp.close()
print("UPLOADED main.py + metadata.yaml")

# 确认落盘版本号
_, o, _ = c.exec_command("grep -n 'version=' " + base + "metadata.yaml")
print("DISK metadata version:", o.read().decode(errors='replace').strip())

# 重启
c.exec_command("docker restart astrbot")
print("RESTART issued, waiting for load...")
time.sleep(15)

_, o, e = c.exec_command("docker logs --tail 50 astrbot 2>&1")
log = o.read().decode(errors='replace')
print("==== LOG TAIL ====")
print(log)
print("==== CHECK ====")
print("has (1.4.3):", "(1.4.3)" in log)
print("has traceback:", "Traceback" in log)
print("has Error:", "Error" in log)
c.close()
print("DONE")
