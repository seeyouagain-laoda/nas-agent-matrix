import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
TOKEN="<RELAY_TOKEN>"
PNG_B64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
SCRIPT = """TOKEN='%s'
PNG_B64='%s'
echo "=== listening socket 8910 ==="
ss -ltnp 2>/dev/null | grep 8910 || netstat -ltnp 2>/dev/null | grep 8910
echo "=== health on LAN IP ==="
curl -s -m 5 -w ' HTTP=%%{http_code}\\n' http://<NAS_LAN_IP>:8910/health ; echo
echo "=== fire image-gemini with ref_b64 (120s) ==="
curl -s -m 120 -o /tmp/relay_resp.txt -w 'HTTP_STATUS=%%{http_code}\\n' -X POST http://<NAS_LAN_IP>:8910/image-gemini \
  -H "Content-Type: application/json" \
  -H "X-Relay-Token: $TOKEN" \
  -d "{\\"prompt\\":\\"smoke test reference decode\\",\\"reference_image_b64\\":\\"$PNG_B64\\"}"
echo "=== resp body first 400 ==="
head -c 400 /tmp/relay_resp.txt 2>/dev/null; echo
echo "=== relay journal after call ==="
journalctl -u openclaw-relay --since 2m --no-pager 2>&1 | grep -iE 'gemini ref decoded|reference|error|traceback|exception|ref_path' | tail -25
""" % (TOKEN, PNG_B64)
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/smoke3.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/smoke3.sh" % PW, timeout=180)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(300) ==="); print(stderr.read().decode("utf-8","replace")[:300])
ssh.close()
