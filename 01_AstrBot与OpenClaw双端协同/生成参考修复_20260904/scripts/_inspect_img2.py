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

# MediaResolver 源码与所在模块
run(r"""docker exec astrbot python -c "import inspect,astrbot.api.message_components as m; from astrbot.api.message_components import Image; src=inspect.getsource(Image.convert_to_file_path); print(src); import importlib; print('MediaResolver module:', [n for n in dir(m) if 'Media' in n or 'Resolver' in n])" """)
# 找 MediaResolver 定义
run(r"""docker exec astrbot grep -rn 'class MediaResolver\|def to_path\|def download\|gchat\|qpic\|referer\|headers' /AstrBot/astrbot/ 2>/dev/null | grep -i 'media\|resolver\|qpic\|gchat' | head -20""")
# aiocqhttp 取图接口
run(r"""docker exec astrbot grep -rn 'def get_image\|get_image\|/get_image\|file_image\|image' /AstrBot/astrbot/core/platform/aiocqhttp/aiocqhttp_platform_adapter.py 2>/dev/null | head -20""")
c.close()
print("DONE")
