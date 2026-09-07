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

run(r"""docker logs astrbot 2>&1 | grep -i 'REFDIAG' | tail -30""")
# 顺便看 reference 目录权限与已落盘情况
run(r"""docker exec astrbot ls -la /AStrBot/data/memes/ 2>&1; echo '---reference---'; docker exec astrbot ls -la /AStrBot/data/memes/reference/ 2>&1; echo '---generated sample---'; docker exec astrbot ls -la /AStrBot/data/memes/generated/ 2>&1 | head -5""")
c.close()
print("DONE")
