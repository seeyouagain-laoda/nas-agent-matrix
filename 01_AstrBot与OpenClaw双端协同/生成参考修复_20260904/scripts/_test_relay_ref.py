import paramiko, time
HOST="<NAS_LAN_IP>"; PORT=22; USER="<NAS_SSH_USER>"; PW="<NAS_SSH_PASSWORD>"
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST,PORT,USER,PW,timeout=15)
def run(cmd, t=120):
    stdin,stdout,stderr=c.exec_command(cmd,timeout=t)
    return stdout.read().decode("utf-8","replace")+stderr.read().decode("utf-8","replace")
# 复刻插件对 relay 的调用：POST /image-gemini {prompt, reference_image}
curl = ("curl -s --noproxy '*' -X POST http://<NAS_LAN_IP>:8910/image-gemini "
        "-H 'X-Relay-Token: <RELAY_TOKEN>' "
        "-H 'Content-Type: application/json' "
        "-d '{\"prompt\":\"参考这张图，生成一个同风格的蓝色鲸鱼娘猫咪\",\"reference_image\":\"<NAS_DATA_DIR>/memes/whale_meme_example.png\"}'")
print("== relay /image-gemini (reference_image) ==")
print(run(curl, t=260))
c.close()
