import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
TOKEN="<RELAY_TOKEN>"
# 1x1 PNG
PNG_B64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
SCRIPT = """TOKEN='%s'
PNG_B64='%s'
curl -s -m 8 -X POST http://127.0.0.1:8910/image-gemini \
  -H "Content-Type: application/json" \
  -H "X-Relay-Token: $TOKEN" \
  -d "{\\"prompt\\":\\"smoke test reference decode\\",\\"reference_image_b64\\":\\"$PNG_B64\\"}" ; echo
echo "=== relay log last 30s ==="
journalctl -u openclaw-relay --since 30s 2>/dev/null | grep -iE 'gemini ref decoded|reference_image_b64|reference|error|traceback' | tail -20
""" % (TOKEN, PNG_B64)
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/smoke.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/smoke.sh" % PW, timeout=60)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(300) ==="); print(stderr.read().decode("utf-8","replace")[:300])
ssh.close()
