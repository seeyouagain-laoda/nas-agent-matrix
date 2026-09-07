# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

print('=== docker inspect mounts ===')
o,e=run('echo %s | sudo -S docker inspect astrbot --format "{{json .Mounts}}"' % PW)
print(o)
print('=== find openclaw_controller NOW ===')
o,e=run('echo %s | sudo -S docker exec astrbot find / -path "*openclaw_controller*" 2>/dev/null' % PW)
print(o or '(none)')
print('=== ls /AStrBot/data ===')
o,e=run('echo %s | sudo -S docker exec astrbot ls -la /AStrBot/data 2>/dev/null' % PW)
print(o)
print('=== host /tmp contents ===')
o,e=run('ls -la /tmp/oc_main_new.py /tmp/relay_new.py 2>/dev/null; echo "---home---"; ls -la /home/%s/oc_main_new.py 2>/dev/null' % USER)
print(o or '(tmp files gone)')
ssh.close()
print('DONE')
