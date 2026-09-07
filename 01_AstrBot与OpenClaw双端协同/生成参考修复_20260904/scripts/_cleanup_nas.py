import paramiko
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
def run(cmd, t=30):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")
print("== relay 生成的参考图(真实路径) =="); print(run("ls -la <NAS_DATA_DIR>/memes/generated/20260904_212242_g_92673.png 2>/dev/null"))
print("== 清理手动测试产物 test_ref*.png =="); print(run("rm -f <NAS_DATA_DIR>/memes/generated/test_ref.png <NAS_DATA_DIR>/memes/generated/test_ref2.png <NAS_DATA_DIR>/memes/generated/test_ref3.png && echo CLEANED"))
print("== reference 目录(插件落盘位) =="); print(run("ls -la <NAS_DATA_DIR>/astrbot_data/memes/reference/ 2>/dev/null"))
print("== generated 目录现状 =="); print(run("ls -la <NAS_DATA_DIR>/memes/generated/ 2>/dev/null | tail -8"))
c.close()
