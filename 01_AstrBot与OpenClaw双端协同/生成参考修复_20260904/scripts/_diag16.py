import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== astrbot up? ==="
docker ps --filter name=astrbot --format '{{.Names}} {{.Status}}'
echo "=== load log last 4 min ==="
docker logs --since 4m astrbot 2>&1 | grep -iE 'openclaw_controller|Loading plugin|Plugin .* by' | head -20
echo "=== raw tail 25 ==="
docker logs --tail 25 astrbot 2>&1 | tail -25
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag16.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag16.sh" % PW, timeout=120)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(200) ==="); print(stderr.read().decode("utf-8","replace")[:200])
ssh.close()
