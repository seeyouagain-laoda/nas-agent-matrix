import paramiko
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)

def run(cmd):
    _, o, e = c.exec_command(cmd)
    print("===", cmd)
    print(o.read().decode(errors='replace').strip())
    err = e.read().decode(errors='replace').strip()
    if err: print("ERR:", err)

run(r"""docker exec astrbot /bin/ls / 2>&1""")
run(r"""docker exec astrbot /bin/ls /AStrBot 2>&1""")
run(r"""docker exec astrbot /bin/ls /AStrBot/data 2>&1""")
run(r"""docker exec astrbot /bin/ls /AStrBot/data/temp 2>&1 | head""")
run(r"""docker exec astrbot sh -c 'cat /proc/mounts | grep -i astrbot' 2>&1""")
c.close()
print("DONE")
