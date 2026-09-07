import paramiko
HOST="<NAS_LAN_IP>"; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
ssh=paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST,22,USER,PW,timeout=15)
sftp=ssh.open_sftp()
sftp.get("<NAS_DATA_DIR>/memes/generated/test_gemini_1.png",
         "c:/Users/user/WorkBuddy/20260407224338/test_gemini_1.png")
sftp.close(); ssh.close()
print("pulled")
