# -*- coding: utf-8 -*-
import paramiko, urllib.request, json

HOST = '<NAS_LAN_IP>'; USER = '<NAS_SSH_USER>'; PW = '<NAS_SSH_PASSWORD>'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=30)

def run(c):
    stdin, stdout, stderr = ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

# AstrBot 插件加载日志（看 openclaw_controller / 报错）
print('=== astrbot plugin load logs ===')
o, e = run('echo %s | sudo -S docker logs astrbot --tail 60 2>&1 | grep -iE "openclaw_controller|1.4.4|traceback|error|exception" | tail -20' % PW)
print(o or '(no matching lines)')

# relay 健康检查（从本机经 LAN，绕过代理）
ssh.close()
print('=== relay /health ===')
try:
    req = urllib.request.Request('http://%s:8910/health' % HOST)
    with urllib.request.urlopen(req, timeout=10) as r:
        print('HTTP', r.status, r.read().decode('utf-8','replace'))
except Exception as ex:
    print('health err:', ex)
print('DONE')
