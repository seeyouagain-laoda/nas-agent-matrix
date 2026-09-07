import paramiko, time
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,22,USER,PW,timeout=15)
sftp=ssh.open_sftp()
local="c:/Users/user/WorkBuddy/20260407224338/_gemini_gen_nas.js"
remote="/home/<NAS_SSH_USER>/gemini_gen_nas.js"
sftp.put(local, remote)
sftp.close()
print("uploaded", remote)
# launch test in background, capture log
ts="test_gemini_1"
cmd=(f"export GEMINI_DEBUG_PORT=16002; "
     f"cd /home/<NAS_SSH_USER> && nohup /home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin/node "
     f"/home/<NAS_SSH_USER>/gemini_gen_nas.js "
     f"--prompt \"一只蓝色鲸鱼娘，戴眼镜，可爱卡通风格，白色背景\" "
     f"--out <NAS_DATA_DIR>/memes/generated/{ts}.png "
     f"--no-launch --no-fresh > /tmp/gemini_test.log 2>&1 & echo PID=$!")
stdin,so,se=ssh.exec_command(cmd)
print(so.read().decode())
print("ERR", se.read().decode())
ssh.close()
print("launched")
