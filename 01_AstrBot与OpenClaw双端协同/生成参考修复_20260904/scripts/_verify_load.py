import paramiko
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)

def run(cmd):
    _, o, e = c.exec_command(cmd)
    print("===", cmd)
    print(o.read().decode(errors='replace').strip())
    err = e.read().decode(errors='replace').strip()
    if err: print("ERR:", err)

run("docker logs astrbot 2>&1 | grep -i 'openclaw_controller'")
run("docker logs astrbot 2>&1 | grep -i -E 'Traceback|Error|异常' | head -20")
run("docker logs astrbot 2>&1 | grep -i 'aiocqhttp' | tail -3")
c.close()
print("DONE")
