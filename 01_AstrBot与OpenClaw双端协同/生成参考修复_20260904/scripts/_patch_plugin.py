# -*- coding: utf-8 -*-
p = 'c:/Users/user/WorkBuddy/20260407224338/_new_main.py'
with open(p, 'r', encoding='utf-8') as f:
    s = f.read()

def replace_method(src, start_marker, new_method):
    lines = src.split('\n')
    si = None
    for i, l in enumerate(lines):
        if l == start_marker or l.startswith(start_marker):
            si = i
            break
    if si is None:
        raise SystemExit('method start not found: ' + repr(start_marker))
    indent = len(lines[si]) - len(lines[si].lstrip())
    ei = len(lines)
    for j in range(si + 1, len(lines)):
        stripped = lines[j].lstrip()
        cur_indent = len(lines[j]) - len(stripped)
        if cur_indent <= indent and (stripped.startswith('def ') or stripped.startswith('async def ')
                                     or stripped.startswith('@') or stripped.startswith('class ')):
            ei = j
            break
    new_lines = new_method.split('\n')
    return '\n'.join(lines[:si] + new_lines + lines[ei:])

# A: 删除只读挂载常量（凡含 REF_DIR 的行一并删，含中文注释行）
out_lines = []
for l in s.split('\n'):
    if 'REF_DIR' in l:
        continue
    out_lines.append(l)
s = '\n'.join(out_lines)

# B: _save_ref_image -> _ref_image_b64（返回 base64，不再写容器 FS）
new_b = (
'    async def _ref_image_b64(self, img):\n'
'        """把 Image 组件解析为 base64 字符串（读取下载后的文件字节），直传 relay 解码。失败返回 None。"""\n'
'        src = None\n'
'        try:\n'
'            src = await img.convert_to_file_path()\n'
'        except Exception:\n'
'            src = None\n'
'        if src and os.path.exists(src):\n'
'            try:\n'
'                with open(src, "rb") as f:\n'
'                    return base64.b64encode(f.read()).decode("ascii")\n'
'            except Exception:\n'
'                return None\n'
'        b = getattr(img, "base64", None)\n'
'        if b:\n'
'            return b\n'
'        return None\n'
)
s = replace_method(s, '    async def _save_ref_image(self, img):', new_b)

# C: _do_gemini_gen 内 ref_host -> ref_b64（ASCII 定向替换，跳过中文 docstring）
repls = [
    ('payload["reference_image"] = ref_host', 'payload["reference_image_b64"] = ref_b64'),
    ('ref_host: str = None):', 'ref_b64: str = None):'),
    ('ref_host = await self._save_ref_image(imgs[0])', 'ref_b64 = await self._ref_image_b64(imgs[0])'),
    ('if require_ref and not ref_host:', 'if require_ref and not ref_b64:'),
    ('if not ref_host:', 'if not ref_b64:'),
]
for old, new in repls:
    n = s.count(old)
    if n != 1:
        raise SystemExit('FAIL C expected 1 for %r got %d' % (old, n))
    s = s.replace(old, new)
# 剩余两处缩进不同的 `if ref_host:`（8 空格与 12 空格）统一改 ref_b64
n = s.count('if ref_host:')
if n < 1:
    raise SystemExit('FAIL C if ref_host: none left')
s = s.replace('if ref_host:', 'if ref_b64:')

# D: _on_any_message 清理诊断日志，改用 base64 直传（真实 emoji，无 REFDIAG）
new_d = (
'    async def _on_any_message(self, event: AstrMessageEvent):\n'
'        """捕获「/生成参考 <描述>」之后用户单独发来的参考图，完成多轮生图。命令消息由 command handler 处理；本 handler 仅在有待定且收到图时才动作，其余消息直接 return，无副作用。"""\n'
'        key = self._session_key(event)\n'
'        pending = self._pending_ref.get(key)\n'
'        if not pending:\n'
'            return\n'
'        if time.time() - pending.get("ts", 0) > self._pending_ttl:\n'
'            self._pending_ref.pop(key, None)\n'
'            event.stop_event()\n'
'            yield event.plain_result("\u26a0\ufe0f 参考图等待已超时（5 分钟），请重新发 /生成参考 <描述>。")\n'
'            return\n'
'        imgs = self._extract_images(event)\n'
'        if not imgs:\n'
'            return\n'
'        event.stop_event()\n'
'        img = imgs[0]\n'
'        ref_b64 = await self._ref_image_b64(img)\n'
'        if not ref_b64:\n'
'            yield event.plain_result("\u26a0\ufe0f 没认出图片内容（已记录，鲸鱼娘正在修）。")\n'
'            return\n'
'        self._pending_ref.pop(key, None)\n'
'        async for r in self._do_gemini_gen(event, pending["prompt"], require_ref=False, ref_b64=ref_b64):\n'
'            yield r\n'
)
s = replace_method(s, '    async def _on_any_message(self, event: AstrMessageEvent):', new_d)

# E: 版本号
if s.count('version="1.4.3",') != 1:
    raise SystemExit('FAIL E version not found')
s = s.replace('version="1.4.3",', 'version="1.4.4",')

with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print("PLUGIN PATCHED OK; len=", len(s))
compile(s, p, 'exec')
print("SYNTAX OK")
