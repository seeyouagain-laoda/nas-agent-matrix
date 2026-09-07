# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()
o,e=run('echo %s | sudo -S docker exec astrbot sh -c "find / -path \\*openclaw_controller/main.py 2>/dev/null"' % PW)
print('PLUGIN PATH IN CONTAINER:\n', o or '(none)', '| ERR:', e)
o,e=run('echo %s | sudo -S docker exec astrbot sh -c "ls -la /AStrBot/data/plugins 2>/dev/null; echo ===; mount | grep -E \\"AStrBot/data|memes\\""' % PW)
print('--- data/plugins + mounts ---\n', o)
o,e=run('echo %s | sudo -S docker exec astrbot sh -c "grep -n version= /AStrBot/data/plugins/openclaw_controller/main.py 2>/dev/null | head -1"' % PW)
print('CONTAINER plugin version line:', o or '(not found at that path)')
ssh.close()
print('DONE')
