import paramiko, time
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
LOCAL=r"C:\Users\user\WorkBuddy\20260407224338\_gemini_gen_nas.js"
REMOTE="/home/<NAS_SSH_USER>/gemini_gen_nas.js"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
sftp=c.open_sftp(); print("== SFTP gemini_gen_nas.js =="); sftp.put(LOCAL, REMOTE); sftp.close()
def run(cmd, t=30):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")

launch = ("setsid env GEMINI_DEBUG_PORT=16002 "
          "/home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin/node "
          "/home/<NAS_SSH_USER>/gemini_gen_nas.js "
          "--prompt '参考这张图的画风，画一只同风格的蓝色鲸鱼娘在星空下' "
          "--reference <NAS_DATA_DIR>/memes/whale_meme_example.png "
          "--out <NAS_DATA_DIR>/memes/generated/test_ref2.png "
          "--no-launch > /tmp/ref_test2.log 2>&1 < /dev/null & echo LAUNCHED")
print("== launch =="); print(run(launch, t=15))
time.sleep(8)
print("== early log =="); print(run("cat /tmp/ref_test2.log 2>/dev/null | tail -15", t=15))
for i in range(22):
    log = run("cat /tmp/ref_test2.log 2>/dev/null", t=15)
    if "RESULT_JSON" in log:
        print("== DONE at poll %d ==" % i)
        for line in log.splitlines():
            if "REF_UPLOAD" in line or "RESULT_JSON" in line or "视口截图" in line or "saved" in line.lower():
                print(line)
        break
    if i % 3 == 0:
        print("[poll %d] waiting... last: %s" % (i, log.strip().splitlines()[-1] if log.strip() else "(empty)"))
    time.sleep(10)
else:
    print("== TIMEOUT =="); print(run("cat /tmp/ref_test2.log 2>/dev/null | tail -25", t=15))
print("== output file =="); print(run("ls -la <NAS_DATA_DIR>/memes/generated/test_ref2.png 2>/dev/null", t=15))
c.close()
