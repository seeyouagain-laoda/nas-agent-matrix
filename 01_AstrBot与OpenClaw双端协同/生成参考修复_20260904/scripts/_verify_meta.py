import paramiko

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== host metadata version ==="
grep -n 'version' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/metadata.yaml
echo "=== container metadata version ==="
docker exec astrbot sh -c "grep -n 'version' /AStrBot/data/plugins/openclaw_controller/metadata.yaml"
echo "=== container main.py version ==="
docker exec astrbot sh -c "grep -n 'version' /AStrBot/data/plugins/openclaw_controller/main.py"
echo "=== restart astrbot ==="
docker restart astrbot
echo "restart done"
sleep 15
echo "=== load log (last 2 min) ==="
docker logs --since 2m astrbot 2>&1 | grep -iE 'openclaw_controller'
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/verify_meta.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/verify_meta.sh" % PW, timeout=150)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(400) ==="); print(stderr.read().decode("utf-8","replace")[:400])
ssh.close()
