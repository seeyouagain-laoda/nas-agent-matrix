# -*- coding: utf-8 -*-
import paramiko

HOST = '<NAS_LAN_IP>'; USER = '<NAS_SSH_USER>'; PW = '<NAS_SSH_PASSWORD>'
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, password=PW, timeout=30)

def run(c):
    stdin, stdout, stderr = ssh.exec_command(c)
    out = stdout.read().decode('utf-8', 'replace').strip()
    err = stderr.read().decode('utf-8', 'replace').strip()
    return out, err

# 修正 relay 属主（仅 owner，group 沿用原值）
print('--- chown relay owner ---')
o, e = run('echo %s | sudo -S chown <NAS_SSH_USER> /home/%s/openclaw_relay.py' % (PW, USER))
print('OUT:', o, '| ERR:', e)

# 确认 plugin 版本
print('--- plugin version on NAS ---')
o, e = run("grep -n 'version=' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py | head -1")
print('plugin:', o)

# 确认 relay 含 reference_image_b64
print('--- relay has reference_image_b64 ---')
o, e = run("grep -c 'reference_image_b64' /home/%s/openclaw_relay.py" % USER)
print('relay ref_b64 count:', o)

# 服务状态
print('--- service status ---')
o, e = run('echo %s | sudo -S systemctl is-active openclaw-relay' % PW)
print('openclaw-relay:', o)
o, e = run('echo %s | sudo -S docker ps --filter name=astrbot --format "{{.Names}} {{.Status}}"' % PW)
print('astrbot:', o)

# relay 日志尾巴
print('--- relay log tail ---')
o, e = run('tail -n 8 /home/%s/.openclaw_relay.log' % USER)
print(o)
ssh.close()
print('VERIFY DONE')
