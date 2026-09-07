import paramiko, time
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,22,USER,PW,timeout=15)
def run(c):
    i,o,e=ssh.exec_command(c); return o.read().decode("utf-8","replace"), e.read().decode("utf-8","replace")
sftp=ssh.open_sftp()

# 1. backup + put relay
o,_ = run("cp -f /home/<NAS_SSH_USER>/openclaw_relay.py /home/<NAS_SSH_USER>/openclaw_relay.py.bak_$(date +%Y%m%d_%H%M%S) 2>/dev/null; ls /home/<NAS_SSH_USER>/openclaw_relay.py.bak_* | tail -1")
print("relay backup:", o.strip())
sftp.put("c:/Users/user/WorkBuddy/20260407224338/_new_relay.py", "/home/<NAS_SSH_USER>/openclaw_relay.py")

# 2. backup + put plugin
PLUG="<NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller"
o,_ = run("cp -f " + PLUG + "/main.py " + PLUG + "/main.py.bak_$(date +%Y%m%d_%H%M%S) 2>/dev/null; cp -f " + PLUG + "/metadata.yaml " + PLUG + "/metadata.yaml.bak_$(date +%Y%m%d_%H%M%S) 2>/dev/null; ls " + PLUG + "/*.bak_* | tail")
print("plugin backup:", o.strip())
sftp.put("c:/Users/user/WorkBuddy/20260407224338/_new_main.py", PLUG + "/main.py")
sftp.put("c:/Users/user/WorkBuddy/20260407224338/_new_meta.yaml", PLUG + "/metadata.yaml")
sftp.close()

# 3. restart relay
run("systemctl restart openclaw-relay")
time.sleep(2)
o,_ = run("systemctl is-active openclaw-relay; echo '---'; curl -s --noproxy '*' http://127.0.0.1:8910/health")
print("relay status:", o.strip())

# 4. restart astrbot
run("docker restart astrbot")
print("astrbot restarting")
ssh.close()