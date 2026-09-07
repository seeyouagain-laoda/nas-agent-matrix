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

# 1. Image.convert_to_file_path 源码
run(r"""docker exec astrbot python -c "import inspect; from astrbot.api.message_components import Image; print(inspect.getsource(Image.convert_to_file_path))" """)
# 2. Image 类属性
run(r"""docker exec astrbot python -c "from astrbot.api.message_components import Image; print([a for a in dir(Image) if not a.startswith('__')])" """)
# 3. aiocqhttp 是否有 Image 子类覆盖
run(r"""docker exec astrbot grep -rn 'convert_to_file_path\|class Image\|get_image\|/get_image' /AstrBot/astrbot/core/platform/aiocqhttp/ 2>/dev/null | head -30""")
c.close()
print("DONE")
