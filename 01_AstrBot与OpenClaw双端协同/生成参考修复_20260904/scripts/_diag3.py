# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

print('=== ALL openclaw_controller dirs in container ===')
o,e=run('echo %s | sudo -S docker exec astrbot find / -type d -name openclaw_controller 2>/dev/null' % PW)
print(o or '(none)')
print('=== ALL main.py under openclaw_controller ===')
o,e=run('echo %s | sudo -S docker exec astrbot find / -path "*openclaw_controller/main.py" 2>/dev/null' % PW)
print(o or '(none)')
print('=== grep version= in each found main.py ===')
for path in o.split('\n'):
    path=path.strip()
    if path:
        v,ee=run('echo %s | sudo -S docker exec astrbot grep -n "version=" %s 2>/dev/null | head -1' % (PW, path))
        print(path, '->', v or '(none)')
print('=== astrbot config.yaml plugin_dir ===')
o,e=run('echo %s | sudo -S docker exec astrbot sh -c "grep -rni plugin_dir /AStrBot/data/config.yaml 2>/dev/null; echo ==; ls /AStrBot/data/config.yaml 2>/dev/null"' % PW)
print(o or '(none)')
print('=== env plugin ===')
o,e=run('echo %s | sudo -S docker exec astrbot sh -c "env | grep -i plugin" 2>/dev/null' % PW)
print(o or '(none)')
ssh.close()
print('DONE')
