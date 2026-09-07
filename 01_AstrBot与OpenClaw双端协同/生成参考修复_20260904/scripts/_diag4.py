# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

print('=== __pycache__ in container ===')
o,e=run('echo %s | sudo -S docker exec astrbot ls -la /AStrBot/data/plugins/openclaw_controller/__pycache__/ 2>&1' % PW)
print(o or '(none)')
print('=== metadata.yaml version (container) ===')
o,e=run('echo %s | sudo -S docker exec astrbot grep -n "version" /AStrBot/data/plugins/openclaw_controller/metadata.yaml 2>/dev/null | head -3' % PW)
print(o or '(none)')
print('=== full astrbot logs tail 80 ===')
o,e=run('echo %s | sudo -S docker logs astrbot --tail 80 2>&1' % PW)
print(o)
ssh.close()
print('DONE')
