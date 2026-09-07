import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,22,USER,PW,timeout=15)
def run(c):
    i,o,e=ssh.exec_command(c); return o.read().decode("utf-8","replace")
print("=== log ===")
print(run("cat /tmp/gemini_test.log 2>/dev/null"))
print("=== png ===")
print(run("ls -la <NAS_DATA_DIR>/memes/generated/test_gemini_1.png 2>/dev/null || echo NO_PNG"))
print("=== proc ===")
print(run("ps aux | grep gemini_gen_nas | grep -v grep | head -2 || echo NO_PROC"))
ssh.close()
