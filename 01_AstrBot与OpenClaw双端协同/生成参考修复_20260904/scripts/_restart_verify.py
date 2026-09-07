import paramiko, time
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
def run(cmd):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=90)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")
print(run("rm -rf <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/__pycache__ && echo CACHE_CLEARED"))
print("== restart =="); print(run("docker restart astrbot"))
time.sleep(25)
print("== FULL plugin load lines ==")
print(run("docker logs astrbot 2>&1 | grep -i 'openclaw_controller' | head -20"))
print("== any traceback/error since start ==")
print(run("docker logs astrbot 2>&1 | grep -iE 'traceback|error|exception' | grep -vi 'no error' | head -20"))
print("== version confirm via metadata =="); print(run("grep version <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/metadata.yaml"))
c.close()
