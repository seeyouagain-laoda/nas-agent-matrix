import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== container metadata.yaml ==="
docker exec astrbot sh -c "cat /AStrBot/data/plugins/openclaw_controller/metadata.yaml 2>/dev/null"
echo "=== host bind-source metadata.yaml ==="
cat <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/metadata.yaml 2>/dev/null
echo "=== host bind-source main.py version ==="
grep -n 'version=' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py 2>/dev/null
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag15.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag15.sh" % PW, timeout=120)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(200) ==="); print(stderr.read().decode("utf-8","replace")[:200])
ssh.close()
