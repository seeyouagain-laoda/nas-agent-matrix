import paramiko, time

host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)
base = "<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/"

print("==== DISK FILE CHECK ====")
_, o, e = c.exec_command("grep -c '_on_any_message' " + base + "main.py; grep -c 'event_message_type' " + base + "main.py; grep 'version:' " + base + "metadata.yaml")
print(o.read().decode(errors='replace').strip())
print("ERR:", e.read().decode(errors='replace').strip())

print("==== DOCKER STATE ====")
_, o, e = c.exec_command("docker ps --format '{{.Names}} {{.Status}}' | grep -i astrbot")
print("ps:", o.read().decode(errors='replace').strip())

print("==== RESTART (capture stderr) ====")
_, o, e = c.exec_command("docker restart astrbot")
print("restart out:", o.read().decode(errors='replace').strip())
print("restart err:", e.read().decode(errors='replace').strip())

print("waiting 22s for load...")
time.sleep(22)

_, o, e = c.exec_command("docker inspect -f '{{.State.StartedAt}}' astrbot")
print("StartedAt:", o.read().decode(errors='replace').strip())

_, o, e = c.exec_command("docker logs --tail 12 astrbot 2>&1")
log = o.read().decode(errors='replace')
print("==== LOG TAIL ====")
print(log)
print("==== CHECK ====")
print("has (1.4.3):", "(1.4.3)" in log)
print("has traceback:", "Traceback" in log)
c.close()
print("DONE")
