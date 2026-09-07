import paramiko

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"

SCRIPT = r'''echo "=== container /proc/mounts for AStrBot ==="
docker exec astrbot sh -c "grep AStrBot /proc/mounts"
echo "=== container __pycache__ for openclaw_controller ==="
docker exec astrbot sh -c "find /AStrBot/data/plugins/openclaw_controller -name '*.pyc' 2>/dev/null; ls -la /AStrBot/data/plugins/openclaw_controller/ 2>/dev/null"
echo "=== astrbot PID and its open fds for openclaw/main ==="
docker exec astrbot sh -c "PID=$(pgrep -f 'python.*astrbot' | head -1); echo PID=$PID; ls -l /proc/$PID/fd 2>/dev/null | grep -iE 'openclaw|main.py|pyc'"
echo "=== post-restart plugin load lines (last 2 min) ==="
docker logs --since 2m astrbot 2>&1 | grep -iE 'openclaw_controller|Loading plugin|plugin' | head -40
echo "=== raw tail 60 of astrbot logs ==="
docker logs --tail 60 astrbot 2>&1 | tail -60
'''

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag10.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag10.sh" % PW, timeout=120)
out = stdout.read().decode("utf-8","replace")
err = stderr.read().decode("utf-8","replace")
print("=== STDOUT ===")
print(out)
print("=== STDERR (first 600) ===")
print(err[:600])
ssh.close()
