import paramiko, datetime, time, json
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
TS=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,PORT,USER,PW,timeout=20)
sftp=ssh.open_sftp()
for src,dst in [
  (r"c:\Users\user\WorkBuddy\20260407224338\_gemini_gen_nas.js", "/home/<NAS_SSH_USER>/gemini_gen_nas.js"),
  (r"c:\Users\user\WorkBuddy\20260407224338\_new_relay.py", "/home/<NAS_SSH_USER>/openclaw_relay.py"),
]:
    bk=dst+".bak_"+TS
    ssh.exec_command("cp %s %s" % (dst, bk))
    sftp.put(src, dst)
    print("DEPLOYED", dst, "backup", bk)
sftp.close()
# sudo restart relay + PID diff
def run(c):
    o=ssh.exec_command(c); return o[1].read().decode().strip(), o[2].read().decode().strip()
before, _ = run("systemctl show openclaw-relay --property=MainPID")
run("echo '%s' | sudo -S systemctl restart openclaw-relay" % PW)
time.sleep(3)
after, _ = run("systemctl show openclaw-relay --property=MainPID")
print("RELAY_PID before=%s after=%s DIFF=%s" % (before, after, before!=after))
# health
h,_ = run("curl -s --noproxy '*' -m 5 http://<NAS_LAN_IP>:8910/health")
print("HEALTH", h)
ssh.close()
