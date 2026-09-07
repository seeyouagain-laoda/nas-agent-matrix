import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== container-wide: any file with OpenClawController ==="
docker exec astrbot sh -c "grep -rl --exclude-dir=proc --exclude-dir=sys --exclude-dir=dev 'OpenClawController' / 2>/dev/null | head -30"
echo "=== container-wide: any file with version=1.4.3 ==="
docker exec astrbot sh -c "grep -rl --exclude-dir=proc --exclude-dir=sys --exclude-dir=dev 'version=\\\"1.4.3\\\"' / 2>/dev/null | head -30"
echo "=== astrbot actual data_dir / plugin config ==="
docker exec astrbot sh -c "cat /AStrBot/data/config.yaml 2>/dev/null | grep -iE 'dir|plugin|path' "
echo "=== astrbot process cwd and args ==="
docker exec astrbot sh -c "PID=\$(pgrep -f 'python.*astrbot' | head -1); echo PID=\$PID; tr '\\0' ' ' < /proc/\$PID/cmdline 2>/dev/null; echo; ls -l /proc/\$PID/cwd 2>/dev/null"
echo "=== any .pyc with openclaw_controller anywhere ==="
docker exec astrbot sh -c "find / -name '*.pyc' 2>/dev/null | xargs grep -l 'OpenClawController' 2>/dev/null | head"
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag13.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag13.sh" % PW, timeout=150)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(200) ==="); print(stderr.read().decode("utf-8","replace")[:200])
ssh.close()
