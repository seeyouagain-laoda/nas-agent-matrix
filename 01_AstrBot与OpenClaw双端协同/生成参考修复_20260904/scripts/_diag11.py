import paramiko

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== host deploy file ==="
ls -la /home/<NAS_SSH_USER>/oc_main_deploy.py 2>&1
echo "=== container /tmp/oc_main_deploy.py ==="
docker exec astrbot ls -la /tmp/oc_main_deploy.py 2>&1
echo "=== container plugin dir listing ==="
docker exec astrbot sh -c "ls -la /AStrBot/data/plugins/ 2>&1; echo '---'; ls -la /AStrBot/data/plugins/openclaw_controller/ 2>&1"
echo "=== container main.py version if exists ==="
docker exec astrbot sh -c "grep -n 'version=' /AStrBot/data/plugins/openclaw_controller/main.py 2>&1"
echo "=== astrbot container running? ==="
docker ps --filter name=astrbot --format '{{.Names}} {{.Status}}'
echo "=== recent load logs (3 min) ==="
docker logs --since 3m astrbot 2>&1 | grep -iE 'openclaw_controller|error|traceback' | head -30
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag11.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag11.sh" % PW, timeout=120)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(300) ==="); print(stderr.read().decode("utf-8","replace")[:300])
ssh.close()
