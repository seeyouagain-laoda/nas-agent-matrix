import paramiko, sys

HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,22,USER,PW,timeout=15)
def run(cmd):
    stdin,so,se=ssh.exec_command(cmd)
    return so.read().decode("utf-8","replace"), se.read().decode("utf-8","replace")
cmds=[
 "echo '== whale-chan count =='; ls <NAS_DATA_DIR>/memes/whale-chan/ 2>/dev/null | wc -l",
 "echo '== dl process =='; ps aux | grep -E 'dl_whalechan|whalechan' | grep -v grep | head -3",
 "echo '== node version =='; /home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin/node -v",
 "echo '== CDP 16002 tabs =='; curl -s --noproxy '*' http://127.0.0.1:16002/json 2>/dev/null | python3 -c \"import sys,json;\\n d=json.load(sys.stdin);\\n print('\\n'.join(t.get('url','') for t in d if t.get('type')=='page'))\" 2>/dev/null | head -20",
 "echo '== generated dir =='; ls -la <NAS_DATA_DIR>/memes/generated/ 2>/dev/null | head",
]
for c in cmds:
    o,e=run(c)
    print(o)
    if e.strip(): print("ERR:",e)
ssh.close()
