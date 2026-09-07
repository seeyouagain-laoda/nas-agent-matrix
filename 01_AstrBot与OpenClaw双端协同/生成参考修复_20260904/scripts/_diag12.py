import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== full astrbot startup logs since 5m (filtered) ==="
docker logs --since 5m astrbot 2>&1 | grep -iE 'openclaw_controller|Loading plugin|Plugin .* by|star_manager' | head -40
echo "=== container /AStrBot main.py version (live file) ==="
docker exec astrbot sh -c "grep -n 'version=' /AStrBot/data/plugins/openclaw_controller/main.py 2>&1"
echo "=== bind state ==="
docker exec astrbot sh -c "grep AStrBot /proc/mounts || echo BIND_INACTIVE"
echo "=== host bind source version ==="
grep -n 'version=' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py 2>&1
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag12.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag12.sh" % PW, timeout=120)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(200) ==="); print(stderr.read().decode("utf-8","replace")[:200])
ssh.close()
