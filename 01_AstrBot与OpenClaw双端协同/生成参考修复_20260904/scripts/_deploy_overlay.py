import paramiko

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"

SCRIPT = """set -e
echo "=== bind state check ==="
docker exec astrbot sh -c "grep AStrBot /proc/mounts || echo BIND_INACTIVE"
echo "=== docker cp host file into container /tmp ==="
docker cp /home/<NAS_SSH_USER>/oc_main_deploy.py astrbot:/tmp/oc_main_deploy.py
echo "=== copy into plugin dir (overlay) ==="
docker exec astrbot cp /tmp/oc_main_deploy.py /AStrBot/data/plugins/openclaw_controller/main.py
echo "=== verify container copy version+markers ==="
docker exec astrbot sh -c "grep -n 'version=' /AStrBot/data/plugins/openclaw_controller/main.py"
docker exec astrbot sh -c "echo ref_b64=$(grep -c 'reference_image_b64' /AStrBot/data/plugins/openclaw_controller/main.py) ref_host=$(grep -c 'ref_host' /AStrBot/data/plugins/openclaw_controller/main.py) REFDIAG=$(grep -c 'REFDIAG' /AStrBot/data/plugins/openclaw_controller/main.py) REF_DIR=$(grep -c 'REF_DIR' /AStrBot/data/plugins/openclaw_controller/main.py)"
echo "=== restart astrbot ==="
docker restart astrbot
echo "=== wait 14s ==="
sleep 14
echo "=== load log for openclaw_controller ==="
docker logs --since 1m astrbot 2>&1 | grep -iE 'openclaw_controller'
"""

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)

# upload local patched file to stable host path
local = open(r"C:\Users\user\WorkBuddy\20260407224338\_new_main.py","rb").read()
sftp = ssh.open_sftp()
with sftp.open("/home/<NAS_SSH_USER>/oc_main_deploy.py","wb") as f:
    f.write(local)
with sftp.open("/tmp/deploy_overlay.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
print("[ok] SFTPed main.py (%d bytes) and script" % len(local))

stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/deploy_overlay.sh" % PW, timeout=120)
out = stdout.read().decode("utf-8","replace")
err = stderr.read().decode("utf-8","replace")
print(out)
print("=== STDERR (first 600) ===")
print(err[:600])
ssh.close()
