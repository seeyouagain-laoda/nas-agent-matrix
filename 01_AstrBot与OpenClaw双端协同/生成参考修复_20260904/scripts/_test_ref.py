import paramiko, time
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
def run(cmd, t=30):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")

# 直接用 node 脚本跑参考图生图（detach + 轮询日志）
launch = ("setsid env GEMINI_DEBUG_PORT=16002 "
          "/home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin/node "
          "/home/<NAS_SSH_USER>/gemini_gen_nas.js "
          "--prompt '参考这张图的画风，画一只同风格的蓝色鲸鱼娘在星空下' "
          "--reference <NAS_DATA_DIR>/memes/whale_meme_example.png "
          "--out <NAS_DATA_DIR>/memes/generated/test_ref.png "
          "--no-launch > /tmp/ref_test.log 2>&1 < /dev/null & echo LAUNCHED")
print("== launch =="); print(run(launch, t=15))
time.sleep(8)
print("== early log =="); print(run("cat /tmp/ref_test.log 2>/dev/null | tail -20", t=15))
# 轮询等待 RESULT_JSON（最多 ~200s）
for i in range(22):
    log = run("cat /tmp/ref_test.log 2>/dev/null", t=15)
    if "RESULT_JSON" in log:
        print("== DONE at poll %d ==" % i)
        # 打印 REF_UPLOAD 与 RESULT_JSON 行
        for line in log.splitlines():
            if "REF_UPLOAD" in line or "RESULT_JSON" in line or "ref_image" in line or "saved" in line.lower():
                print(line)
        break
    if i % 3 == 0:
        print("[poll %d] waiting... last line: %s" % (i, log.strip().splitlines()[-1] if log.strip() else "(empty)"))
    time.sleep(10)
else:
    print("== TIMEOUT, full log =="); print(run("cat /tmp/ref_test.log 2>/dev/null | tail -30", t=15))
# 确认产物
print("== output file =="); print(run("ls -la <NAS_DATA_DIR>/memes/generated/test_ref.png 2>/dev/null", t=15))
c.close()
