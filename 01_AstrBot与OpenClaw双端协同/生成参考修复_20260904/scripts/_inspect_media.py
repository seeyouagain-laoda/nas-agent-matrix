import paramiko
host, user, pw = '<NAS_LAN_IP>', '<NAS_SSH_USER>', '<NAS_SSH_PASSWORD>'
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username=user, password=pw, port=22, timeout=20)

def run(cmd):
    _, o, e = c.exec_command(cmd)
    print("===", cmd)
    print(o.read().decode(errors='replace').strip()[:4000])
    err = e.read().decode(errors='replace').strip()
    if err: print("ERR:", err)

run(r"""docker exec astrbot sed -n '580,820p' /AstrBot/astrbot/core/utils/media_utils.py""")
run(r"""docker exec astrbot grep -rn 'get_image\|file_image\|image' /AstrBot/astrbot/core/platform/aiocqhttp/aiocqhttp_platform_adapter.py 2>/dev/null | head -20""")
c.close()
print("DONE")
