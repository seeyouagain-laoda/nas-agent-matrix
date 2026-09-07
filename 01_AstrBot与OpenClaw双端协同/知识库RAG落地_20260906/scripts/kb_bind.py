#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 cmd_config.json 根级插入 kb_names 等知识库绑定配置（文本级插入，避免重复键丢失）"""
import nas_ssh, base64

code = r'''
import shutil, time, json, re

p = "/AstrBot/data/cmd_config.json"
bak = p + ".bak_kbbind_" + time.strftime("%Y%m%d_%H%M%S")
shutil.copy(p, bak)
print("backup:", bak)

s = open(p, encoding="utf-8").read()

# 若已有 kb_names 且已绑定则跳过
if '"kb_names"' in s:
    m = re.search(r'"kb_names"\s*:\s*\[[^\]]*\]', s)
    print("existing kb_names:", m.group(0) if m else "?")
    if m and "重要AI配置文档" in m.group(0):
        print("ALREADY_BOUND")
        raise SystemExit

ins = ('"kb_names": ["\u91cd\u8981AI\u914d\u7f6e\u6587\u6863"], '
       '"kb_fusion_top_k": 20, "kb_final_top_k": 6, "kb_agentic_mode": false, ')

i = s.index("{") + 1
s2 = s[:i] + ins + s[i:]
open(p, "w", encoding="utf-8").write(s2)
print("inserted")

# 校验 JSON 可解析（重复键会以最后一个为准，仅做语法校验）
try:
    json.loads(s2)
    print("JSON_OK")
except Exception as e:
    print("JSON_PARSE_WARN:", e)
'''

b64 = base64.b64encode(code.encode("utf-8")).decode()
out = nas_ssh.run_cmd(
    'docker exec astrbot python -c "import base64;exec(base64.b64decode(\'%s\'))"' % b64)
print(out)
