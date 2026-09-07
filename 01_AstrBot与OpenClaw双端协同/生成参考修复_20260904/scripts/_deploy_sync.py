# -*- coding: utf-8 -*-
import paramiko, time, base64
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
LOCAL=r'c:\Users\user\WorkBuddy\20260407224338\_new_main.py'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

data=open(LOCAL,'rb').read(); b64=base64.b64encode(data).decode('ascii')

# 主机绑定源版本
o,e=run('grep -n "version=" <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py 2>/dev/null | head -1')
print('HOST bind source version:', o or '(MISSING)')
if '1.4.4' not in o:
    o,e=run('echo %s | sudo -S cp -f /home/%s/oc_main_new.py <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py' % (PW, USER))
    print('cp host:', o or '(ok)', '| err:', e or '(none)')
    o,e=run('grep -n "version=" <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py 2>/dev/null | head -1')
    print('HOST now:', o)

# 镜像层（容器自身 /AStrBot/data）
o,e=run('echo %s | sudo -S docker exec astrbot mkdir -p /AStrBot/data/plugins/openclaw_controller' % PW)
cmd=("echo %s | sudo -S docker exec astrbot sh -c 'echo %s | base64 -d > /AStrBot/data/plugins/openclaw_controller/main.py'" % (PW, b64))
o,e=run(cmd)
print('write image layer:', o or '(ok)', '| err:', e or '(none)')
o,e=run('echo %s | sudo -S docker exec astrbot grep -n "version=" /AStrBot/data/plugins/openclaw_controller/main.py 2>/dev/null | head -1' % PW)
print('IMAGE layer version:', o)

# 重启并验证加载版本
o,e=run('echo %s | sudo -S docker restart astrbot' % PW)
print('restart:', o)
time.sleep(10)
o,e=run('echo %s | sudo -S docker logs astrbot --tail 30 2>&1 | grep -iE "openclaw_controller" | tail -2' % PW)
print('LOAD LOG:', o or '(none)')
ssh.close()
print('DONE')
