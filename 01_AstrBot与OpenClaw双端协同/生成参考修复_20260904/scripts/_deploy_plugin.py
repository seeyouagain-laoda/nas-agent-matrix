import paramiko, time
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
LOCAL_MAIN=r"C:\Users\user\WorkBuddy\20260407224338\_new_main.py"
LOCAL_META=r"C:\Users\user\WorkBuddy\20260407224338\_new_meta.yaml"
REMOTE_MAIN="<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py"
REMOTE_META="<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/metadata.yaml"

c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
sftp=c.open_sftp()
print("== SFTP main.py =="); sftp.put(LOCAL_MAIN, REMOTE_MAIN)
print("== SFTP metadata.yaml =="); sftp.put(LOCAL_META, REMOTE_META)
sftp.close()
def run(cmd):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=60)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")
print(run("mkdir -p <NAS_DATA_DIR>/astrbot_data/memes/reference && echo MKDIR_OK"))
print("== docker restart astrbot =="); print(run("docker restart astrbot"))
time.sleep(12)
print("== plugin load log ==")
print(run("docker logs astrbot --tail 50 2>&1 | grep -i 'openclaw_controller\\|traceback\\|error' | head -30"))
c.close()
print("DEPLOY_DONE")
