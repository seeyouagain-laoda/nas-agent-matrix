# -*- coding: utf-8 -*-
import paramiko

HOST = '<NAS_LAN_IP>'
USER = '<NAS_SSH_USER>'
PW = '<NAS_SSH_PASSWORD>'
LOCAL_PLUGIN = r'c:\Users\user\WorkBuddy\20260407224338\_new_main.py'
LOCAL_RELAY = r'c:\Users\user\WorkBuddy\20260407224338\_relay_current.py'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=30)
sftp = ssh.open_sftp()
print('SFTP put plugin -> /tmp/oc_main_new.py')
sftp.put(LOCAL_PLUGIN, '/tmp/oc_main_new.py')
print('SFTP put relay  -> /tmp/relay_new.py')
sftp.put(LOCAL_RELAY, '/tmp/relay_new.py')
sftp.close()

cmds = [
    'echo %s | sudo -S mv -f /tmp/oc_main_new.py <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py' % PW,
    'echo %s | sudo -S mv -f /tmp/relay_new.py /home/%s/openclaw_relay.py' % (PW, USER),
    'echo %s | sudo -S chown %s:%s /home/%s/openclaw_relay.py' % (PW, USER, USER, USER),
    'echo %s | sudo -S systemctl restart openclaw-relay' % PW,
    'echo %s | sudo -S docker restart astrbot' % PW,
]
for c in cmds:
    print('=== RUN:', c[:55], '...')
    stdin, stdout, stderr = ssh.exec_command(c)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    if out.strip():
        print('OUT:', out.strip())
    if err.strip():
        print('ERR:', err.strip())
ssh.close()
print('DEPLOY DONE')
