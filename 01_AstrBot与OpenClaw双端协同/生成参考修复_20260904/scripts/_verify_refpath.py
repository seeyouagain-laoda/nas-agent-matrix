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

# 容器写入 -> 主机是否可见（验证映射）
run(r"""docker exec astrbot sh -c 'mkdir -p /AStrBot/data/ref_images && echo MAPPED_OK > /AStrBot/data/ref_images/_t.txt && echo WROTE_IN_CONTAINER'""")
run(r"""sleep 1; echo 'HOST side:'; cat <NAS_DATA_DIR>/astrbot_data/ref_images/_t.txt 2>&1; ls -la <NAS_DATA_DIR>/astrbot_data/ref_images/ 2>&1""")
# 反向：主机写 -> 容器是否可见
run(r"""echo HOST_OK > <NAS_DATA_DIR>/astrbot_data/ref_images/_h.txt""")
run(r"""docker exec astrbot sh -c 'cat /AStrBot/data/ref_images/_h.txt 2>&1; echo SEEN_IN_CONTAINER'""")
# 清理
run(r"""docker exec astrbot sh -c 'rm -f /AStrBot/data/ref_images/_t.txt /AStrBot/data/ref_images/_h.txt'; rm -f <NAS_DATA_DIR>/astrbot_data/ref_images/_t.txt <NAS_DATA_DIR>/astrbot_data/ref_images/_h.txt; rmdir <NAS_DATA_DIR>/astrbot_data/ref_images 2>/dev/null; echo CLEANED""")
c.close()
print("DONE")
