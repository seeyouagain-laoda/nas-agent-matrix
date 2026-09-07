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

run(r"""docker exec astrbot python -c "import inspect; from astrbot.api.event import AstrMessageEvent; [print(n, type(getattr(AstrMessageEvent,n,'MISSING')), callable(getattr(AstrMessageEvent,n,None))) for n in ['stop_event','get_session_id','message_str','plain_result','chain_result']]" """)

run(r"""docker exec astrbot grep -rn 'stop_event' /AstrBot/astrbot/api/event/ 2>/dev/null | head -20""")
run(r"""docker exec astrbot grep -rn 'def message_str\|message_str' /AstrBot/astrbot/api/event/ 2>/dev/null | head -10""")
c.close()
print("DONE")
