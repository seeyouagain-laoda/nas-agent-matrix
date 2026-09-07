# -*- coding: utf-8 -*-
import paramiko, time
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
LOCAL=r'c:\Users\user\WorkBuddy\20260407224338\_new_main.py'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
sftp=ssh.open_sftp()
print('SFTP -> /home/%s/oc_main_new.py (stable)' % USER)
sftp.put(LOCAL, '/home/%s/oc_main_new.py' % USER)
sftp.close()

def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

# docker cp 进容器数据层（bind 未生效，容器用自身层）
o,e=run('echo %s | sudo -S docker cp /home/%s/oc_main_new.py astrbot:/AStrBot/data/plugins/openclaw_controller/main.py' % (PW, USER))
print('docker cp:', o or '(ok)', '| err:', e or '(none)')

# 清掉旧 pyc 缓存，强制重新编译
o,e=run('echo %s | sudo -S docker exec astrbot rm -rf /AStrBot/data/plugins/openclaw_controller/__pycache__' % PW)
print('rm pyc:', o or '(ok)', '| err:', e or '(none)')

# 校验容器内版本
o,e=run('echo %s | sudo -S docker exec astrbot grep -n "version=" /AStrBot/data/plugins/openclaw_controller/main.py | head -1' % PW)
print('container version now:', o or '(none)')

# 重启
o,e=run('echo %s | sudo -S docker restart astrbot' % PW)
print('restart:', o)
time.sleep(9)
o,e=run('echo %s | sudo -S docker logs astrbot --tail 40 2>&1 | grep -iE "openclaw_controller" | tail -3' % PW)
print('LOAD LOG:', o or '(none)')
ssh.close()
print('DONE')
