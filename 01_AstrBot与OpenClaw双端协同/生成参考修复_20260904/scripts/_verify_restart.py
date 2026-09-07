import paramiko, time

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"

SCRIPT = r'''echo "=== host bind source main.py version ==="
grep -n 'version=' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py
echo "=== host bind source markers ==="
echo "ref_b64 count: $(grep -c 'reference_image_b64' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py)"
echo "ref_host count: $(grep -c 'ref_host' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py)"
echo "REFDIAG count: $(grep -c 'REFDIAG' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py)"
echo "REF_DIR count: $(grep -c 'REF_DIR' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py)"
echo "_ref_image_b64 count: $(grep -c '_ref_image_b64' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py)"
echo "=== /home/<NAS_SSH_USER>/oc_main_new.py version ==="
grep -n 'version=' /home/<NAS_SSH_USER>/oc_main_new.py
echo "=== restart astrbot ==="
docker restart astrbot
echo "=== waiting 12s for load ==="
sleep 12
echo "=== load log tail ==="
docker logs --tail 30 astrbot 2>&1 | grep -i 'openclaw_controller'
echo "=== any 1.4.4 ? ==="
docker logs --tail 200 astrbot 2>&1 | grep -i 'openclaw_controller (1.4.4)'
'''

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/vr.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/vr.sh" % PW, timeout=120)
out = stdout.read().decode("utf-8","replace")
err = stderr.read().decode("utf-8","replace")
print("=== STDOUT ===")
print(out)
print("=== STDERR (first 600) ===")
print(err[:600])
ssh.close()
