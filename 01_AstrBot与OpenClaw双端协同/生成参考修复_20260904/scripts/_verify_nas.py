import paramiko
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
def run(cmd):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=60)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")
print("== metadata.yaml on disk =="); print(run("cat <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/metadata.yaml"))
print("== main.py @register version =="); print(run("grep -n 'version=' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py | head"))
print("== plugin dir listing =="); print(run("ls -la <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/"))
print("== any other openclaw_controller copies =="); print(run("find <NAS_DATA_DIR> -name 'metadata.yaml' -path '*openclaw_controller*' 2>/dev/null; find <NAS_DATA_DIR> -type d -name 'openclaw_controller' 2>/dev/null"))
print("== astrbot plugin cache? =="); print(run("ls -la <NAS_DATA_DIR>/astrbot_data/plugins/ 2>/dev/null | head; find <NAS_DATA_DIR>/astrbot_data -maxdepth 2 -name '__pycache__' -type d 2>/dev/null"))
c.close()
