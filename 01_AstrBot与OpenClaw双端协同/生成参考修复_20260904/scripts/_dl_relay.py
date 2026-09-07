import paramiko
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)
sftp = c.open_sftp()
sftp.get('/home/<NAS_SSH_USER>/openclaw_relay.py', r'c:/Users/user/WorkBuddy/20260407224338/_relay_current.py')
sftp.close()
c.close()
print("DOWNLOADED")
