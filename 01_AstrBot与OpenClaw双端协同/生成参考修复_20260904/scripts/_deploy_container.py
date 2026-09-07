# -*- coding: utf-8 -*-
import paramiko, time
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

# 先确认容器内当前版本
o,e=run('echo %s | sudo -S docker exec astrbot grep -n "version=" /AStrBot/data/plugins/openclaw_controller/main.py | head -1' % PW)
print('BEFORE container version:', o or '(none)', '| ERR:', e)

# docker cp 推送 1.4.4 进容器
o,e=run('echo %s | sudo -S docker cp /tmp/oc_main_new.py astrbot:/AStrBot/data/plugins/openclaw_controller/main.py' % PW)
print('docker cp out:', o or '(ok)', '| err:', e or '(none)')

# 校验容器内已更新
o,e=run('echo %s | sudo -S docker exec astrbot grep -n "version=" /AStrBot/data/plugins/openclaw_controller/main.py | head -1' % PW)
print('AFTER container version:', o or '(none)', '| ERR:', e)

# 重启 astrbot 让插件重新加载
o,e=run('echo %s | sudo -S docker restart astrbot' % PW)
print('restart:', o)
time.sleep(8)
# 确认加载的版本
o,e=run('echo %s | sudo -S docker logs astrbot --tail 40 2>&1 | grep -iE "openclaw_controller" | tail -3' % PW)
print('LOAD LOG:', o or '(none)')
ssh.close()
print('DONE')
