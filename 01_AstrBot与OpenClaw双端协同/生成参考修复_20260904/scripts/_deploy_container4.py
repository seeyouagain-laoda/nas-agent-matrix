# -*- coding: utf-8 -*-
import paramiko, time, base64
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
LOCAL=r'c:\Users\user\WorkBuddy\20260407224338\_new_main.py'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

data=open(LOCAL,'rb').read()
b64=base64.b64encode(data).decode('ascii')
print('local plugin bytes:', len(data), 'b64 len:', len(b64))

# 1) 容器里确保插件目录存在（镜像层，bind 不生效时也会用到）
o,e=run('echo %s | sudo -S docker exec astrbot mkdir -p /AStrBot/data/plugins/openclaw_controller' % PW)
print('mkdir:', o or '(ok)', '| err:', e or '(none)')

# 2) 直写容器文件系统（base64 经 argv，避免与 sudo 密码 stdin 冲突）
cmd=("echo %s | sudo -S docker exec astrbot sh -c 'echo %s | base64 -d > /AStrBot/data/plugins/openclaw_controller/main.py'"
     % (PW, b64))
o,e=run(cmd)
print('write via base64:', o or '(ok)', '| err:', e or '(none)')

# 3) 清 pyc
o,e=run('echo %s | sudo -S docker exec astrbot rm -rf /AStrBot/data/plugins/openclaw_controller/__pycache__' % PW)
print('rm pyc:', o or '(ok)', '| err:', e or '(none)')

# 4) 校验容器视图版本
o,e=run('echo %s | sudo -S docker exec astrbot grep -n "version=" /AStrBot/data/plugins/openclaw_controller/main.py 2>/dev/null | head -1' % PW)
print('container view version:', o or '(none)')

# 5) 重启
o,e=run('echo %s | sudo -S docker restart astrbot' % PW)
print('restart:', o)
time.sleep(9)
o,e=run('echo %s | sudo -S docker logs astrbot --tail 40 2>&1 | grep -iE "openclaw_controller" | tail -3' % PW)
print('LOAD LOG:', o or '(none)')
ssh.close()
print('DONE')
