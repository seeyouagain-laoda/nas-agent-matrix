# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

print('=== container metadata.yaml ===')
o,e=run('echo %s | sudo -S docker exec astrbot cat /AStrBot/data/plugins/openclaw_controller/metadata.yaml 2>&1' % PW)
print(o or '(none)')
print('=== does astrbot cache plugin code in data_v4.db? (search tables/text cols for openclaw) ===')
script = (
"import sqlite3\n"
"c=sqlite3.connect('/AStrBot/data/data_v4.db')\n"
"tabs=[r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")]\n"
"print('TABLES:', tabs)\n"
"for t in tabs:\n"
"    try:\n"
"        cols=[d[1] for d in c.execute('PRAGMA table_info(%s)'%t)]\n"
"    except Exception:\n"
"        continue\n"
"    for col in cols:\n"
"        if col.lower() in ('code','content','source','plugin','data','config'):\n"
"            try:\n"
"                for r in c.execute('SELECT %s FROM %s LIMIT 1'%(col,t)):\n"
"                    v=str(r[0])\n"
"                    if 'openclaw' in v.lower() or 'OpenClawController' in v:\n"
"                        print('FOUND in', t, col, 'len', len(v))\n"
"            except Exception as ex:\n"
"                pass\n"
)
b64 = __import__('base64').b64encode(script.encode()).decode()
o,e=run('echo %s | sudo -S docker exec astrbot sh -c "echo %s | base64 -d | python3"' % (PW, b64))
print(o or '(none)')
print('ERR:', e)
ssh.close()
print('DONE')
