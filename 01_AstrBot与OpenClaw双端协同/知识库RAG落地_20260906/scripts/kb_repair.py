#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复：以 /AStrBot/data/cmd_config.json（完整含 poke）为基准，
补上知识库绑定，并同步写入 /AstrBot/data/cmd_config.json（运行实例实际读取的那份）。
"""
import nas_ssh, base64

code = r'''
import json, shutil, time, os

SRC = "/AStrBot/data/cmd_config.json"   # 完整版（含 poke / tts / stt / nim_embed）
DST = "/AstrBot/data/cmd_config.json"   # 运行实例实际读取的那份

for p in (SRC, DST):
    shutil.copy(p, p + ".bak_kbrepair_" + time.strftime("%Y%m%d_%H%M%S"))
print("backed up both")

d = json.loads(open(SRC, encoding="utf-8-sig").read())

# 1) 知识库绑定
d["kb_names"] = ["\u91cd\u8981AI\u914d\u7f6e\u6587\u6863"]
d["kb_fusion_top_k"] = 20
d["kb_final_top_k"] = 6
d["kb_agentic_mode"] = False

# 2) 确保 nim_embed provider 条目完整（运行实例里生效的那份）
cur = json.loads(open(DST, encoding="utf-8-sig").read())
cur_embed = [p for p in (cur.get("provider") or []) if p.get("id") == "nim_embed"]
prov = d.get("provider") or []
prov = [p for p in prov if p.get("id") != "nim_embed"]
if cur_embed:
    prov.append(cur_embed[0])
d["provider"] = prov

# 3) 确保 source 含 nim_embed
srcs = d.get("provider_sources") or []
if not any(s.get("id") == "nim_embed" for s in srcs):
    srcs.append({
        "id": "nim_embed",
        "type": "nvidia_embedding",
        "enable": True,
        "embedding_api_key": "<NIM_KEY>",
        "embedding_model": "nvidia/nemotron-3-embed-1b",
    })
    d["provider_sources"] = srcs

out = json.dumps(d, ensure_ascii=False, indent=2)
for p in (SRC, DST):
    open(p, "w", encoding="utf-8-sig").write(out)
    print("wrote", p, os.path.getsize(p), "bytes")

# 校验
for p in (SRC, DST):
    dd = json.loads(open(p, encoding="utf-8-sig").read())
    print("%s -> providers=%s sources=%s kb_names=%s"
          % (p, [x.get("id") for x in dd.get("provider") or []],
             [x.get("id") for x in dd.get("provider_sources") or []],
             dd.get("kb_names")))
'''

b64 = base64.b64encode(code.encode("utf-8")).decode()
print(nas_ssh.run_cmd(
    'docker exec astrbot python -c "import base64;exec(base64.b64decode(\'%s\'))"' % b64))
