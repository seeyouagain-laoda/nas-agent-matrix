import paramiko, time
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
def run(cmd):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=90)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")
print(run("docker restart astrbot"))
time.sleep(30)
print("== container startedAt =="); print(run("docker inspect -f '{{.State.StartedAt}}' astrbot"))
print("== TAIL 30 (freshest) =="); print(run("docker logs astrbot --tail 30 2>&1"))
print("== openclaw_controller load lines (freshest, tail) =="); print(run("docker logs astrbot --tail 200 2>&1 | grep -i 'openclaw_controller' | tail -5"))
c.close()
