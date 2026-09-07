# -*- coding: utf-8 -*-
import paramiko, time
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

# 1) 主机绑定源端：确保 plugins 目录存在并写入 1.4.4（覆盖 bind 生效时）
o,e=run('echo %s | sudo -S mkdir -p <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller' % PW)
print('mkdir host:', o or '(ok)', '| err:', e or '(none)')
o,e=run('echo %s | sudo -S cp -f /home/%s/oc_main_new.py <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py' % (PW, USER))
print('cp host:', o or '(ok)', '| err:', e or '(none)')

# 2) docker cp 进容器可写层（覆盖 bind 未生效时，容器读自身层）
o,e=run('echo %s | sudo -S docker cp /home/%s/oc_main_new.py astrbot:/AStrBot/data/plugins/openclaw_controller/main.py' % (PW, USER))
print('docker cp:', o or '(ok)', '| err:', e or '(none)')

# 3) 清旧 pyc
o,e=run('echo %s | sudo -S docker exec astrbot rm -rf /AStrBot/data/plugins/openclaw_controller/__pycache__' % PW)
print('rm pyc:', o or '(ok)', '| err:', e or '(none)')

# 4) 校验：容器视图 + 主机视图版本
o,e=run('echo %s | sudo -S docker exec astrbot grep -n "version=" /AStrBot/data/plugins/openclaw_controller/main.py 2>/dev/null | head -1' % PW)
print('container view version:', o or '(none)')
o,e=run('grep -n "version=" <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py | head -1')
print('host bind source version:', o or '(none)')

# 5) 重启
o,e=run('echo %s | sudo -S docker restart astrbot' % PW)
print('restart:', o)
time.sleep(9)
o,e=run('echo %s | sudo -S docker logs astrbot --tail 40 2>&1 | grep -iE "openclaw_controller" | tail -3' % PW)
print('LOAD LOG:', o or '(none)')
ssh.close()
print('DONE')
