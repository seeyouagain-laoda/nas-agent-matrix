import paramiko
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)

def run(cmd):
    _, o, e = c.exec_command(cmd)
    print(o.read().decode(errors='replace').strip())
    err = e.read().decode(errors='replace').strip()
    if err: print("ERR:", err)

# 找到 relay 文件位置
run(r"""find /home/<NAS_SSH_USER> -maxdepth 2 -name 'openclaw_relay.py' 2>/dev/null; echo '---also---'; find / -maxdepth 4 -name 'openclaw_relay.py' 2>/dev/null | head""")
c.close()
print("DONE")
