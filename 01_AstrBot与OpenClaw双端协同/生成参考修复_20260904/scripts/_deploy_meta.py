import paramiko

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)

SCRIPT = """set -e
echo "=== bind state ==="
docker exec astrbot sh -c "grep AStrBot /proc/mounts || echo BIND_INACTIVE"
echo "=== docker cp host meta into container /tmp ==="
docker cp /home/<NAS_SSH_USER>/oc_meta_deploy.yaml astrbot:/tmp/oc_meta_deploy.yaml
echo "=== write into container overlay plugin dir ==="
docker exec astrbot cp /tmp/oc_meta_deploy.yaml /AStrBot/data/plugins/openclaw_controller/metadata.yaml
echo "=== verify host metadata version ==="
grep -n 'version=' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/metadata.yaml
echo "=== verify container metadata version ==="
docker exec astrbot sh -c "grep -n 'version=' /AStrBot/data/plugins/openclaw_controller/metadata.yaml"
echo "=== verify container main.py version ==="
docker exec astrbot sh -c "grep -n 'version=' /AStrBot/data/plugins/openclaw_controller/main.py"
echo "=== restart astrbot ==="
docker restart astrbot
echo "=== wait 15s ==="
sleep 15
echo "=== load log (last 2 min) ==="
docker logs --since 2m astrbot 2>&1 | grep -iE 'openclaw_controller'
"""

# upload local metadata.yaml to host bind source (direct) and to a stable host path
meta = open(r"C:\Users\user\WorkBuddy\20260407224338\_meta144.yaml","rb").read()
sftp = ssh.open_sftp()
with sftp.open("<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/metadata.yaml","wb") as f:
    f.write(meta)
with sftp.open("/home/<NAS_SSH_USER>/oc_meta_deploy.yaml","wb") as f:
    f.write(meta)
with sftp.open("/tmp/deploy_meta.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
print("[ok] metadata.yaml -> host bind source + /home/<NAS_SSH_USER>/oc_meta_deploy.yaml (%d bytes); script uploaded" % len(meta))

stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/deploy_meta.sh" % PW, timeout=150)
out = stdout.read().decode("utf-8","replace")
err = stderr.read().decode("utf-8","replace")
print(out)
print("=== STDERR(400) ==="); print(err[:400])
ssh.close()
