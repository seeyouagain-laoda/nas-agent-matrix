import paramiko, sys
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
def run(cmd):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=40)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")
cmds=[
 "echo '== fygo CDP 16002 =='; curl -s --noproxy '*' http://127.0.0.1:16002/json/version 2>&1 | head -c 300; echo",
 "echo '== gemini_gen_nas.js reference =='; grep -n 'reference' /home/<NAS_SSH_USER>/gemini_gen_nas.js 2>&1 | head; echo '== head =='; head -8 /home/<NAS_SSH_USER>/gemini_gen_nas.js 2>&1",
 "echo '== relay reference =='; grep -n 'reference_image\\|image-gemini\\|def gen_image_gemini\\|GEMINI_SCRIPT' /home/<NAS_SSH_USER>/openclaw_relay.py 2>&1 | head",
 "echo '== plugin state =='; grep -n '生成参考\\|reference_image\\|Image\\|message_obj\\|filter.command' <NAS_DATA_DIR>/astrbot_data/plugins/openclaw_controller/main.py 2>&1 | head -30",
 "echo '== relay service =='; systemctl is-active openclaw-relay 2>&1; (ss -ltnp 2>/dev/null | grep 8910 || netstat -ltnp 2>/dev/null | grep 8910); echo",
 "echo '== memes dir =='; ls -la <NAS_DATA_DIR>/memes/ 2>&1 | head",
 "echo '== astrbot pkg =='; python3 -c \"import astrbot,os;print(os.path.dirname(astrbot.__file__))\" 2>&1",
 "echo '== astrbot version =='; pip show astrbot 2>/dev/null | grep -i version; cat <NAS_DATA_DIR>/astrbot_data/../astrbot_data/astrbot_config.yaml 2>/dev/null | head -2",
]
for cmd in cmds:
    print("############")
    print(run(cmd))
c.close()
