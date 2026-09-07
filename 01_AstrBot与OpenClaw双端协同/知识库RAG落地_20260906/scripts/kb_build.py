#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鲸鱼娘 知识库 RAG 构建/验证脚本（Windows 侧驱动 AstrBot dashboard API）
用法:
  python kb_build.py login          # 测试登录，打印 token
  python kb_build.py create         # 建库「重要AI配置文档」(embedding=nim_embed)，打印 kb_id
  python kb_build.py ingest SAMPLE  # 只摄入 1 个样本文件，验证 embedding 跑通
  python kb_build.py ingest ALL     # 批量摄入桌面 311 份
  python kb_build.py stats          # 查 kb 统计(文档数/分块数)
  python kb_build.py retrieve "问题" # 检索验证
"""
import sys, os, json, uuid, urllib.request, urllib.error, base64

BASE = "http://<NAS_LAN_IP>:6185"
USER = "astrbot"
PASS = "<DASHBOARD_PASSWORD>"  # 容器首次启动日志中的初始随机密码(真实可用)
DOC_DIR = r"C:\Users\user\Desktop\重要ai配置文档"
KB_NAME = "重要AI配置文档"
EMBED_ID = "nim_embed"
KB_ID_FILE = os.path.join(os.path.dirname(__file__), "kb_id.txt")


def _req(method, path, token=None, data=None, files=None, raw=None):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if files is not None:
        import io, uuid
        boundary = "----kb%d" % uuid.uuid4().hex
        body = bytearray()
        for fk, fv in files.items():
            fname, fcontent = fv
            body += ("--%s\r\n" % boundary).encode()
            body += ('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (fk, fname)).encode("utf-8")
            body += b"Content-Type: application/octet-stream\r\n\r\n"
            body += fcontent + b"\r\n"
        body += ("--%s--\r\n" % boundary).encode()
        headers["Content-Type"] = "multipart/form-data; boundary=%s" % boundary
        data_bytes = bytes(body)
    elif raw is not None:
        data_bytes = raw
        headers["Content-Type"] = "application/json"
    else:
        data_bytes = data.encode("utf-8") if data else None
        if data_bytes is not None:
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


TOKEN_FILE = os.path.join(os.path.dirname(__file__), "kb_token.txt")


def _b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=")


def _load_cached_token():
    if os.path.exists(TOKEN_FILE):
        t = open(TOKEN_FILE, encoding="utf-8").read().strip()
        if t:
            return t
    return None


def _save_cached_token(t):
    try:
        open(TOKEN_FILE, "w", encoding="utf-8").write(t)
    except Exception:
        pass


def login():
    # 优先用缓存 token(7天有效)；否则用容器初始随机密码登录拿新 token
    cached = _load_cached_token()
    if cached:
        return cached
    st, body = _req("POST", "/api/auth/login",
                    raw=json.dumps({"username": USER, "password": PASS}).encode("utf-8"))
    print("login status:", st)
    if st == 200:
        try:
            tok = json.loads(body).get("data", {}).get("token") or json.loads(body).get("token")
        except Exception:
            tok = None
        if tok:
            _save_cached_token(tok)
            return tok
    print("login body:", body[:200])
    return None


def save_kb_id(kid):
    open(KB_ID_FILE, "w", encoding="utf-8").write(kid)


def load_kb_id():
    if os.path.exists(KB_ID_FILE):
        return open(KB_ID_FILE, encoding="utf-8").read().strip()
    return None


def create_kb(token):
    payload = {
        "kb_name": KB_NAME,
        "description": "用户多年积累的 NAS/代理/模型/AI 配置资产，供鲸鱼娘随身问答",
        "emoji": "📚",
        "embedding_provider_id": EMBED_ID,
        "chunk_size": 800,
        "chunk_overlap": 120,
        "top_k_dense": 5,
        "top_k_sparse": 5,
        "top_m_final": 6,
    }
    st, body = _req("POST", "/api/v1/knowledge-bases", token=token, data=json.dumps(payload))
    print("create status:", st)
    print("create body:", body[:500])
    try:
        j = json.loads(body)
        kid = j.get("kb_id") or (j.get("data") or {}).get("kb_id")
        if kid:
            save_kb_id(kid)
            print("KB_ID saved:", kid)
    except Exception as e:
        print("parse err:", e)


# 只摄入纯文本类资产；跳过图片/压缩包/快捷方式/无扩展名
TEXT_EXT = (".md", ".txt", ".py", ".js", ".cjs", ".json", ".jsonl",
            ".yaml", ".yml", ".html", ".sh", ".bat", ".ini", ".toml", ".conf")


def _list_files():
    out = []
    for root, _, files in os.walk(DOC_DIR):
        for f in files:
            if f.lower().endswith(TEXT_EXT):
                out.append(os.path.join(root, f))
    return sorted(out)


def _wait_task(token, tid, timeout=900):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        st, body = _req("GET", "/api/v1/knowledge-bases/tasks/%s" % tid, token=token)
        try:
            d = (json.loads(body).get("data") or {})
            status = d.get("status")
            prog = d.get("progress") or {}
            pct = prog.get("current"), prog.get("total")
            if status in ("completed", "failed"):
                return status, body
            print("    ...%s %s/%s %s" % (status, pct[0], pct[1], prog.get("stage", "")))
        except Exception:
            print("    ...parse err", body[:120])
        time.sleep(6)
    return "timeout", ""


def _post_documents(token, kid, paths, chunk_size=800, chunk_overlap=120):
    """multipart 上传一批文档到 /documents（字段名 file，服务端自动解析+分块）"""
    boundary = "----kb" + uuid.uuid4().hex
    body = bytearray()
    for key, val in [("chunk_size", str(chunk_size)), ("chunk_overlap", str(chunk_overlap))]:
        body += ("--%s\r\n" % boundary).encode()
        body += ('Content-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (key, val)).encode()
    for p in paths:
        fn = os.path.basename(p)
        with open(p, "rb") as fh:
            content = fh.read()
        body += ("--%s\r\n" % boundary).encode()
        body += ('Content-Disposition: form-data; name="file"; filename="%s"\r\n' % fn).encode("utf-8")
        body += b"Content-Type: application/octet-stream\r\n\r\n"
        body += content + b"\r\n"
    body += ("--%s--\r\n" % boundary).encode()
    headers = {"Authorization": "Bearer " + token,
               "Content-Type": "multipart/form-data; boundary=%s" % boundary}
    url = BASE + "/api/v1/knowledge-bases/%s/documents" % kid
    req = urllib.request.Request(url, data=bytes(body), method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            st, b = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        st, b = e.code, e.read().decode("utf-8", "replace")
    return st, b


def ingest(token, mode, batch=25, start=0):
    kid = load_kb_id()
    if not kid:
        print("NO kb_id, run create first"); return
    files = _list_files()
    print("total doc files found:", len(files))
    if start:
        files = files[start:]
        print("skip first %d files, remaining %d" % (start, len(files)))
    if mode == "SAMPLE":
        files = files[:1]
        batch = 1
    print("ingesting %d files in batches of %d" % (len(files), batch))
    tasks = []
    ok_batches = 0
    for i in range(0, len(files), batch):
        chunk = files[i:i + batch]
        st, b = _post_documents(token, kid, chunk)
        tid = None
        try:
            tid = ((json.loads(b).get("data") or {}) or {}).get("task_id")
        except Exception:
            pass
        print("[batch %d-%d] status %s task=%s" % (i, i + len(chunk) - 1, st, tid))
        if tid:
            tasks.append(tid)
            status, body = _wait_task(token, tid)
            print("    -> %s" % status)
            if status == "completed":
                ok_batches += 1
            elif status == "failed":
                print("    FAIL body:", body[:300])
                break
        else:
            print("    no task_id:", b[:200])
            break
    print("batches ok: %d / %d ; task_ids: %s" % (ok_batches, len(tasks), [t[:8] for t in tasks]))
    if tasks:
        open(os.path.join(os.path.dirname(__file__), "kb_tasks.txt"), "w",
             encoding="utf-8").write("\n".join(tasks))


def tasks_status(token):
    try:
        tids = open(os.path.join(os.path.dirname(__file__), "kb_tasks.txt"),
                    encoding="utf-8").read().split()
    except Exception:
        print("no kb_tasks.txt"); return
    for tid in tids:
        st, body = _req("GET", "/api/v1/knowledge-bases/tasks/%s" % tid, token=token)
        print("[%s] %s :: %s" % (tid[:8], st, body[:220]))


def stats(token):
    kid = load_kb_id()
    if not kid:
        print("NO kb_id"); return
    st, body = _req("GET", "/api/v1/knowledge-bases/%s/stats" % kid, token=token)
    print("stats status:", st, body[:600])


def retrieve(token, q):
    kid = load_kb_id()
    if not kid:
        print("NO kb_id"); return
    payload = {"query": q, "kb_names": [KB_NAME], "top_k": 5}
    st, body = _req("POST", "/api/v1/knowledge-bases/%s/retrieve" % kid, token=token, data=json.dumps(payload))
    print("retrieve status:", st)
    try:
        j = json.loads(body)
        res = j.get("results") or j.get("data") or j
        if isinstance(res, list):
            for it in res[:5]:
                txt = it.get("content") or it.get("text") or ""
                score = it.get("score")
                print("  [score=%s] %s" % (score, txt[:160].replace("\n", " ")))
        else:
            print(body[:800])
    except Exception as e:
        print("retrieve parse err:", e, body[:400])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "login"
    tok = login()
    if not tok and cmd != "login":
        print("LOGIN FAILED"); sys.exit(1)
    if cmd == "login":
        pass
    elif cmd == "create":
        create_kb(tok)
    elif cmd == "ingest":
        a = sys.argv[2] if len(sys.argv) > 2 else "ALL"
        bsz = int(sys.argv[3]) if len(sys.argv) > 3 else 25
        st0 = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        ingest(tok, a, bsz, st0)
    elif cmd == "stats":
        stats(tok)
    elif cmd == "tasks":
        tasks_status(tok)
    elif cmd == "retrieve":
        retrieve(tok, sys.argv[2] if len(sys.argv) > 2 else "relay token 在哪")
