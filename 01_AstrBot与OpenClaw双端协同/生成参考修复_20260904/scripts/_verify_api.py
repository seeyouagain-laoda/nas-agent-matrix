import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('<NAS_LAN_IP>', username='<NAS_SSH_USER>', password='<NAS_SSH_PASSWORD>', port=22, timeout=20)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    print("=== CMD:", cmd)
    print(out)
    if err.strip():
        print("--- ERR:", err)

run(r"""docker exec astrbot python -c "from astrbot.api.event import filter; print('event_message_type=', hasattr(filter,'event_message_type')); print('EventMessageType=', hasattr(filter,'EventMessageType')); print('ALL=', getattr(getattr(filter,'EventMessageType',None),'ALL',None)); print([x for x in dir(filter) if 'event' in x.lower()])" """)

run(r"""docker exec astrbot python -c "from astrbot.api.event import AstrMessageEvent; print([x for x in dir(AstrMessageEvent) if 'session' in x.lower() or 'sender' in x.lower() or 'message_str' in x.lower()])" """)

client.close()
print("DONE")
