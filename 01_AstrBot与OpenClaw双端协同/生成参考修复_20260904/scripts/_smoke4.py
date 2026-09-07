import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== listening 8910 ==="
ss -ltnp 2>/dev/null | grep 8910 || netstat -ltnp 2>/dev/null | grep 8910
echo "=== health on LAN IP (5s) ==="
curl -s -m 5 -w ' HTTP=%%{http_code}\\n' http://<NAS_LAN_IP>:8910/health; echo
echo "=== relay recent journal (decode handler present?) ==="
journalctl -u openclaw-relay -n 5 --no-pager 2>&1 | tail -5
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/smoke4.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/smoke4.sh" % PW, timeout=40)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(200) ==="); print(stderr.read().decode("utf-8","replace")[:200])
ssh.close()
