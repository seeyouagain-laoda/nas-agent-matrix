import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,22,USER,PW,timeout=15)
def run(cmd):
    stdin,so,se=ssh.exec_command(cmd)
    return so.read().decode("utf-8","replace"), se.read().decode("utf-8","replace")
for c in [
 "echo '== fygo proc =='; ps aux | grep -iE 'fygo|chrome|chromium' | grep -v grep | head -5",
 "echo '== port 16002 listen =='; (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E '16002|9222|9101' ",
 "echo '== /json/version raw =='; curl -s --noproxy '*' -m 5 http://127.0.0.1:16002/json/version; echo",
 "echo '== /json raw (first 800) =='; curl -s --noproxy '*' -m 5 http://127.0.0.1:16002/json | head -c 800; echo",
]:
    o,e=run(c)
    print(o)
    if e.strip(): print("ERR:",e)
ssh.close()
