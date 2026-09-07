import paramiko

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"

SCRIPT = r'''echo "=== docker ps ==="
docker ps --format '{{.Names}}|{{.Image}}'
echo "=== astrbot mounts ==="
docker inspect astrbot --format '{{json .Mounts}}'
echo "=== container: version 1.4.3 in /AStrBot ==="
docker exec astrbot sh -c "grep -rl 'version=\"1.4.3\"' /AStrBot 2>/dev/null | head -50"
echo "=== container: OpenClawController main.py in /AStrBot ==="
docker exec astrbot sh -c "find /AStrBot -name main.py 2>/dev/null | xargs grep -l 'OpenClawController' 2>/dev/null | head -50"
echo "=== container: /AStrBot/data/plugins listing ==="
docker exec astrbot sh -c "ls -la /AStrBot/data/plugins/ 2>/dev/null"
echo "=== host: version 1.4.3 in <NAS_DATA_DIR> ==="
grep -rl 'version="1.4.3"' <NAS_DATA_DIR> 2>/dev/null | head -50
echo "=== host: OpenClawController main.py in <NAS_DATA_DIR> ==="
find <NAS_DATA_DIR> -name main.py 2>/dev/null | xargs grep -l 'OpenClawController' 2>/dev/null | head -50
echo "=== host: OpenClawController main.py in /home/<NAS_SSH_USER> ==="
find /home/<NAS_SSH_USER> -name '*.py' 2>/dev/null | xargs grep -l 'OpenClawController' 2>/dev/null | head -50
'''

ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag9.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()

stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag9.sh" % PW, timeout=150)
out = stdout.read().decode("utf-8","replace")
err = stderr.read().decode("utf-8","replace")
print("=== STDOUT ===")
print(out)
print("=== STDERR (first 800) ===")
print(err[:800])
ssh.close()
