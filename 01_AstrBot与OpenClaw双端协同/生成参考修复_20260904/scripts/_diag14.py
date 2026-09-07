import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
SCRIPT = """echo "=== ALL dirs named openclaw_controller in container ==="
docker exec astrbot sh -c "find / -type d -name 'openclaw_controller' 2>/dev/null | grep -v '/proc/'"
echo "=== astrbot config: data_dir / plugin settings ==="
docker exec astrbot sh -c "cat /AStrBot/data/config.yaml 2>/dev/null | grep -iE 'data_dir|plugin_dir|dir|path' "
echo "=== astrbot cmdline + cwd ==="
docker exec astrbot sh -c "PID=\$(pgrep -f 'python.*astrbot' | head -1); echo PID=\$PID; tr '\\0' ' ' < /proc/\$PID/cmdline 2>/dev/null; echo; echo CWD=; ls -l /proc/\$PID/cwd 2>/dev/null"
echo "=== list data/plugins/openclaw_controller fully ==="
docker exec astrbot sh -c "ls -la /AStrBot/data/plugins/openclaw_controller/ 2>/dev/null"
echo "=== metadata.yaml anywhere in container ==="
docker exec astrbot sh -c "find / -name 'metadata.yaml' 2>/dev/null | grep -v '/proc/' | head"
"""
ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=20)
sftp = ssh.open_sftp()
with sftp.open("/tmp/diag14.sh","wb") as f:
    f.write(SCRIPT.encode("utf-8"))
sftp.close()
stdin, stdout, stderr = ssh.exec_command("echo %s | sudo -S bash /tmp/diag14.sh" % PW, timeout=120)
print(stdout.read().decode("utf-8","replace"))
print("=== STDERR(200) ==="); print(stderr.read().decode("utf-8","replace")[:200])
ssh.close()
