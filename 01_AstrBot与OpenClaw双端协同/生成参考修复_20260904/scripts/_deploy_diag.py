import paramiko, time, subprocess
r = subprocess.run([r"C:/Users/user/.workbuddy/binaries/python/envs/default/Scripts/python.exe", "-m", "py_compile", r"c:/Users/user/WorkBuddy/20260407224338/_new_main.py"])
print("PY_COMPILE:", "OK" if r.returncode == 0 else "FAIL")
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)
base = "<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/"
sftp = c.open_sftp()
sftp.put(r"c:/Users/user/WorkBuddy/20260407224338/_new_main.py", base + "main.py")
sftp.close()
print("UPLOADED main.py")
_, o, e = c.exec_command("docker restart astrbot")
print("restart:", o.read().decode(errors='replace').strip())
time.sleep(18)
_, o, e = c.exec_command("docker logs astrbot 2>&1 | grep -i 'openclaw_controller (1' | tail -1")
print("LOAD:", o.read().decode(errors='replace').strip())
c.close()
print("DONE")
