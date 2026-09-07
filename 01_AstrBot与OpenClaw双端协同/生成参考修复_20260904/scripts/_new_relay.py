#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenClaw Relay —— 供 AstrBot 插件（鲸鱼娘）远程触发 OpenClaw 执行任务 / 生图。
- 监听 <NAS_LAN_IP>:8910（仅主机 LAN，容器经此 IP 可达）
- POST /run          {"task": "<任务描述>"}  + Header X-Relay-Token  -> OpenClaw 执行
- POST /image        {"prompt": "...", "model": "gpt-image-2", "size": "1024x1024"} + Header X-Relay-Token -> PokeAPI 生图并存本地
- POST /image-gemini {"prompt": "..."} + Header X-Relay-Token -> fygo CDP Gemini 生图并存本地
- 返回 {"ok":bool,"text":str,"calls":int,"images":[...],"error":str}  （/run）
- 返回 {"ok":bool,"path":<host路径>,"container_path":<容器内路径>,"error":str}  （/image, /image-gemini）
- GET  /health -> {"ok":true}
"""
import json
import os
import re
import time
import subprocess
import logging
import base64
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "<NAS_LAN_IP>"
PORT = 8910
TOKEN = "<RELAY_TOKEN>"
OPENCLAW = "/home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin/openclaw"
NVM_BIN = "/home/<NAS_SSH_USER>/.nvm/versions/node/v22.22.3/bin"
TIMEOUT = 280

# PokeAPI 生图（方法一）
POKE_KEY = os.environ.get("POKE_API_KEY", "")
POKE_IMG_URL = "https://www.poke2api.com/v1/images/generations"
POKE_PROXY = "http://127.0.0.1:7890"
GEN_DIR = "<NAS_DATA_DIR>/memes/generated"          # 主机路径（AstrBot ro 绑定源）
GEN_CONT = "/AstrBot/data/memes/generated"          # 容器内可见路径

# Gemini 浏览器生图（方法二，NAS fygo CDP 16002）
GEMINI_SCRIPT = "/home/<NAS_SSH_USER>/gemini_gen_nas.js"
NODE_BIN = NVM_BIN + "/node"

LOG = "/home/<NAS_SSH_USER>/.openclaw_relay.log"
logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("openclaw_relay")

OC_ENV = dict(os.environ)
OC_ENV.update({
    "HOME": "/home/<NAS_SSH_USER>",
    "PATH": NVM_BIN + ":/usr/bin:/bin:/usr/local/bin",
})

IMG_EXT = r"\.(?:jpg|jpeg|png|gif|webp|bmp)"
URL_RE = re.compile(r"https?://\S+?" + IMG_EXT, re.I)
FILE_RE = re.compile(r"(?!\w)(/\S+?" + IMG_EXT + ")", re.I)


def extract_images(text):
    imgs = []
    if not text:
        return imgs
    urls = URL_RE.findall(text)
    for u in urls:
        imgs.append({"type": "url", "value": u})
    stripped = URL_RE.sub("", text)
    for f in FILE_RE.findall(stripped):
        imgs.append({"type": "file", "value": f})
    return imgs


def run_openclaw(task: str):
    sid = "relay-%d" % os.getpid()
    cmd = [OPENCLAW, "agent", "--agent", "main",
           "--session-id", sid, "-m", task, "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=TIMEOUT, env=OC_ENV)
    except subprocess.TimeoutExpired:
        return "", 0, [], "timeout(%ds)" % TIMEOUT
    except Exception as e:
        return "", 0, [], "exec_error: %s" % e
    raw = proc.stdout.strip()
    if not raw:
        return "", 0, [], "empty_output (rc=%d, stderr=%s)" % (proc.returncode, proc.stderr[:300])
    try:
        d = json.loads(raw)
    except Exception:
        return raw[:4000], 0, [], "json_parse_fail"
    res = d.get("result") or {}
    payloads = res.get("payloads") or []
    text = "".join((p.get("text") or "") for p in payloads).strip()
    calls = 0
    try:
        calls = (res.get("meta") or {}).get("toolSummary", {}).get("calls", 0) or 0
    except Exception:
        calls = 0
    if not text:
        return raw[:4000], calls, [], "no_text_in_result(rc=%d)" % proc.returncode
    return text, calls, extract_images(text), ""


def gen_image(prompt: str, model: str = "gpt-image-2", size: str = "1024x1024"):
    """调用 PokeAPI 生图，解码后存本地，返回 (ok, host_path, container_path, error)。"""
    os.makedirs(GEN_DIR, exist_ok=True)
    payload = {"model": model, "prompt": prompt, "n": 1, "size": size}
    headers = {"Authorization": "Bearer " + POKE_KEY, "Content-Type": "application/json"}
    raw = None
    try:
        r = requests.post(POKE_IMG_URL, json=payload, headers=headers, timeout=120)
        raw = r
        if r.status_code == 200:
            data = r.json()
        else:
            return False, "", "", "poke_http_%d:%s" % (r.status_code, r.text[:200])
    except Exception as e:
        # 直连失败 -> 走 Mihomo HTTP 代理重试
        try:
            r = requests.post(POKE_IMG_URL, json=payload, headers=headers, timeout=120,
                              proxies={"http": POKE_PROXY, "https": POKE_PROXY})
            if r.status_code == 200:
                data = r.json()
            else:
                return False, "", "", "poke_proxy_http_%d:%s" % (r.status_code, r.text[:200])
        except Exception as e2:
            return False, "", "", "poke_conn_fail:%s" % str(e)[:120]
    items = (data.get("data") or [])
    if not items:
        return False, "", "", "poke_no_data:%s" % str(data)[:200]
    it = items[0]
    b64 = it.get("b64_json")
    if b64:
        img_bytes = base64.b64decode(b64)
    elif it.get("url"):
        # 极少数情况返回 url，拉取下来存本地
        try:
            rr = requests.get(it["url"], timeout=120)
            img_bytes = rr.content
        except Exception as e3:
            return False, "", "", "poke_url_fetch_fail:%s" % str(e3)[:120]
    else:
        return False, "", "", "poke_no_image_field"
    ts = time.strftime("%Y%m%d_%H%M%S")
    ext = "png"  # gpt-image-2 返回 PNG
    fname = "%s_%s.%s" % (ts, abs(hash(prompt)) % 100000, ext)
    host_path = os.path.join(GEN_DIR, fname)
    open(host_path, "wb").write(img_bytes)
    container_path = os.path.join(GEN_CONT, fname)
    return True, host_path, container_path, ""


def gen_image_gemini(prompt: str, reference_image: str = None):
    """调用 NAS fygo 浏览器 + Gemini 生图（gemini_gen_nas.js），复用已登录标签页，返回 (ok, host_path, container_path, error)。
    reference_image: 主机绝对路径的参考图，传给 node --reference，让 Gemini 参考生图。"""
    os.makedirs(GEN_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    fname = "%s_g_%s.png" % (ts, abs(hash(prompt)) % 100000)
    host_path = os.path.join(GEN_DIR, fname)
    env = dict(OC_ENV)
    env["GEMINI_DEBUG_PORT"] = "16002"
    cmd = [NODE_BIN, GEMINI_SCRIPT, "--prompt", prompt, "--out", host_path, "--no-launch"]
    if reference_image and os.path.exists(reference_image):
        cmd += ["--reference", reference_image]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env)
    except subprocess.TimeoutExpired:
        return False, "", "", "gemini_timeout(240s)"
    except Exception as e:
        return False, "", "", "gemini_exec_error:%s" % e
    # 解析 RESULT_JSON（最后一行 JSON）
    result = None
    for line in (proc.stdout or "").splitlines()[::-1]:
        if line.startswith("RESULT_JSON"):
            try:
                result = json.loads(line[len("RESULT_JSON "):])
            except Exception:
                pass
            break
    if proc.returncode != 0 or not result:
        tail = (proc.stderr or proc.stdout or "")[-400:]
        return False, "", "", "gemini_rc=%d:%s" % (proc.returncode, tail)
    if not result.get("image_generated") or not result.get("screenshot"):
        saved_path = result.get("screenshot") or ""
        if saved_path and os.path.exists(saved_path) and os.path.getsize(saved_path) > 1024:
            # 图片已实际落地（成图检测超时但取图成功）→ 兜底通过
            container_path = os.path.join(GEN_CONT, os.path.basename(saved_path))
            log.info("gemini fallback-accept saved file -> %s", container_path)
            return True, saved_path, container_path, ""
        return False, "", "", "gemini_no_image:%s" % (result.get("detail") or "")
    saved = result["screenshot"]
    if not os.path.exists(saved) or os.path.getsize(saved) < 1024:
        return False, "", "", "gemini_file_missing"
    container_path = os.path.join(GEN_CONT, os.path.basename(saved))
    return True, saved, container_path, ""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path == "/run":
            self._handle_run()
        elif self.path == "/image":
            self._handle_image()
        elif self.path == "/image-gemini":
            self._handle_image_gemini()
        else:
            self._send(404, {"ok": False, "error": "not_found"})

    def _handle_run(self):
        tok = self.headers.get("X-Relay-Token", "")
        if tok != TOKEN:
            self._send(403, {"ok": False, "error": "forbidden"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send(400, {"ok": False, "error": "bad_json:%s" % e})
            return
        task = (data.get("task") or "").strip()
        if not task:
            self._send(400, {"ok": False, "error": "empty_task"})
            return
        log.info("run task: %s", task[:120])
        text, calls, images, err = run_openclaw(task)
        if err:
            log.warning("task error: %s", err)
            self._send(200, {"ok": False, "text": text, "calls": calls, "images": images, "error": err})
        else:
            log.info("task ok calls=%s len=%d imgs=%d", calls, len(text), len(images))
            self._send(200, {"ok": True, "text": text, "calls": calls, "images": images, "error": ""})

    def _handle_image(self):
        tok = self.headers.get("X-Relay-Token", "")
        if tok != TOKEN:
            self._send(403, {"ok": False, "error": "forbidden"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send(400, {"ok": False, "error": "bad_json:%s" % e})
            return
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            self._send(400, {"ok": False, "error": "empty_prompt"})
            return
        model = data.get("model") or "gpt-image-2"
        size = data.get("size") or "1024x1024"
        log.info("gen image: model=%s prompt=%s", model, prompt[:80])
        ok, host_path, container_path, err = gen_image(prompt, model, size)
        if not ok:
            log.warning("image error: %s", err)
            self._send(200, {"ok": False, "error": err})
        else:
            log.info("image ok -> %s", container_path)
            self._send(200, {"ok": True, "path": host_path, "container_path": container_path, "error": ""})

    def _handle_image_gemini(self):
        tok = self.headers.get("X-Relay-Token", "")
        if tok != TOKEN:
            self._send(403, {"ok": False, "error": "forbidden"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            self._send(400, {"ok": False, "error": "bad_json:%s" % e})
            return
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            self._send(400, {"ok": False, "error": "empty_prompt"})
            return
        reference_image = (data.get("reference_image") or "").strip()
        if reference_image and not os.path.exists(reference_image):
            reference_image = ""  # 路径不存在则忽略参考图
        log.info("gemini image: prompt=%s ref=%s", prompt[:80], reference_image)
        ok, host_path, container_path, err = gen_image_gemini(prompt, reference_image or None)
        if not ok:
            log.warning("gemini error: %s", err)
            self._send(200, {"ok": False, "error": err})
        else:
            log.info("gemini ok -> %s", container_path)
            self._send(200, {"ok": True, "path": host_path, "container_path": container_path, "error": ""})

    def log_message(self, *args):
        pass


def main():
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("OpenClaw relay listening on %s:%d", HOST, PORT)
    srv.serve_forever()


if __name__ == "__main__":
    main()
