# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

print('=== cmd_config.json plugin_dir (host) ===')
o,e=run('grep -in "plugin" <NAS_DATA_DIR>/astrbot_data/cmd_config.json 2>/dev/null | head -10')
print(o or '(none)')
print('=== container: _ref_image_b64 present in plugin dir? ===')
o,e=run('echo %s | sudo -S docker exec astrbot grep -c "_ref_image_b64" /AStrBot/data/plugins/openclaw_controller/main.py 2>/dev/null' % PW)
print('count:', o or '(none)')
print('=== container: REFDIAG present? ===')
o,e=run('echo %s | sudo -S docker exec astrbot grep -c "REFDIAG" /AStrBot/data/plugins/openclaw_controller/main.py 2>/dev/null' % PW)
print('count:', o or '(none)')
print('=== container: head of main.py ===')
o,e=run('echo %s | sudo -S docker exec astrbot head -40 /AStrBot/data/plugins/openclaw_controller/main.py 2>/dev/null' % PW)
print(o)
print('=== container: is /AStrBot/data/plugins a symlink? ===')
o,e=run('echo %s | sudo -S docker exec astrbot sh -c "ls -ld /AStrBot/data/plugins; readlink -f /AStrBot/data/plugins"' % PW)
print(o)
ssh.close()
print('DONE')
