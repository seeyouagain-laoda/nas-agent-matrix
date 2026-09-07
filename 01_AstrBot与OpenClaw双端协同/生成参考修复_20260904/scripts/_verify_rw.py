import paramiko
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)

def run(cmd):
    _, o, e = c.exec_command(cmd)
    print("===", cmd)
    print(o.read().decode(errors='replace').strip())
    err = e.read().decode(errors='replace').strip()
    if err: print("ERR:", err)

# 1. 容器 /AStrBot/data 是否可写
run(r"""docker exec astrbot sh -c 'touch /AStrBot/data/_wt_test 2>&1 && echo CONTAINER_WRITE_OK && rm -f /AStrBot/data/_wt_test'""")
# 2. 主机对应路径是否存在（确认映射）
run(r"""ls -la <NAS_DATA_DIR>/astrbot_data/_wt_test 2>&1; echo '---'; ls -ld <NAS_DATA_DIR>/astrbot_data <NAS_DATA_DIR>/memes""")
# 3. 看 data 下现有内容
run(r"""docker exec astrbot sh -c 'ls -la /AStrBot/data/ | head -20'""")
c.close()
print("DONE")
