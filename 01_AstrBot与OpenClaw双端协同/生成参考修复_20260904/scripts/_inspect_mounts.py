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

run(r"""docker inspect astrbot --format '{{range .Mounts}}{{.Type}} SRC={{.Source}} DST={{.Destination}} MODE={{.Mode}}{{"\n"}}{{end}}'""")
run(r"""docker exec astrbot sh -c 'ls -la /AStrBot/ 2>&1; echo "---data---"; ls -la /AStrBot/data 2>&1; echo "---temp---"; ls -la /AStrBot/data/temp 2>&1 | head'""")
c.close()
print("DONE")
