#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""容器内读取指定源码文件的行区间（绕开 shell 路径解析怪癖）"""
import nas_ssh, base64, sys

p = sys.argv[1]
a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
b = int(sys.argv[3]) if len(sys.argv) > 3 else 0

code = r'''
p = %r
a, b = %d, %d
try:
    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
except Exception as e:
    print("OPEN FAIL:", e); raise SystemExit
if b == 0: b = len(lines)
for i, l in enumerate(lines[a:b], start=a+1):
    print("%%5d| %%s" %% (i, l))
''' % (p, a, b)

b64 = base64.b64encode(code.encode("utf-8")).decode()
out = nas_ssh.run_cmd('docker exec astrbot python -c "import base64;exec(base64.b64decode(\'%s\'))"' % b64)
print(out)
