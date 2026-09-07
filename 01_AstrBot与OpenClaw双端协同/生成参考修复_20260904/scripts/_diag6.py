# -*- coding: utf-8 -*-
import paramiko
HOST='<NAS_LAN_IP>'; USER='<NAS_SSH_USER>'; PW='<NAS_SSH_PASSWORD>'
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,username=USER,password=PW,timeout=30)
def run(c):
    stdin,stdout,stderr=ssh.exec_command(c)
    return stdout.read().decode('utf-8','replace').strip(), stderr.read().decode('utf-8','replace').strip()

print('=== ALL main.py in container ===')
o,e=run('echo %s | sudo -S docker exec astrbot find / -name "main.py" 2>/dev/null' % PW)
print(o or '(none)')
print('=== which main.py contains openclaw_controller class ===')
for p in o.split('\n'):
    p=p.strip()
    if not p: continue
    c,e=run('echo %s | sudo -S docker exec astrbot grep -l "OpenClawController" %s 2>/dev/null' % (PW, p))
    if c.strip():
        v,ee=run('echo %s | sudo -S docker exec astrbot grep -n "version=" %s 2>/dev/null | head -1' % (PW, p))
        print(p, '->', v or '(no ver)')
print('=== data_v4.db tables ===')
o,e=run('echo %s | sudo -S docker exec astrbot python3 -c "import sqlite3;c=sqlite3.connect(\'/AStrBot/data/data_v4.db\');print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type=\'table\'\")])" 2>&1' % PW)
print(o or '(none)')
print('=== search db for openclaw ===')
o,e=run('echo %s | sudo -S docker exec astrbot python3 -c "import sqlite3;c=sqlite3.connect(\'/AStrBot/data/data_v4.db\');[print(t, [r[0] for r in c.execute(\'SELECT DISTINCT substr(%s,1,40) FROM %s\'%(col,t))][:1]) for t in [x[0] for x in c.execute(\"SELECT name FROM sqlite_master WHERE type=\'table\'\")] for col in [d[1] for d in c.execute(\'PRAGMA table_info(%s)\'%t)] if \'text\' in str(col).lower() or col in (\'code\',\'content\',\'source\')]" 2>&1 | head -20' % PW)
print(o or '(none)')
ssh.close()
print('DONE')
