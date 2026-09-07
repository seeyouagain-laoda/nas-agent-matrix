# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()
o,e=run('echo %s | sudo -S docker logs astrbot --tail 25 2>&1' % PW)
print(o)
print('=== uptime / restart count ===')
o,e=run('echo %s | sudo -S docker inspect astrbot --format "{{.State.StartedAt}} {{.RestartCount}}"' % PW)
print('StartedAt/RestartCount:', o)
ssh.close()
print('DONE')
