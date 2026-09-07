# -*- coding: utf-8 -*-
p = 'c:/Users/user/WorkBuddy/20260407224338/_relay_current.py'
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

new_m = (
'    def _handle_image_gemini(self):\n'
'        tok = self.headers.get("X-Relay-Token", "")\n'
'        if tok != TOKEN:\n'
'            self._send(403, {"ok": False, "error": "forbidden"})\n'
'            return\n'
'        try:\n'
'            length = int(self.headers.get("Content-Length", "0"))\n'
'            data = json.loads(self.rfile.read(length) or b"{}")\n'
'        except Exception as e:\n'
'            self._send(400, {"ok": False, "error": "bad_json:%s" % e})\n'
'            return\n'
'        prompt = (data.get("prompt") or "").strip()\n'
'        if not prompt:\n'
'            self._send(400, {"ok": False, "error": "empty_prompt"})\n'
'            return\n'
'        reference_image = (data.get("reference_image") or "").strip()\n'
'        reference_b64 = (data.get("reference_image_b64") or "").strip()\n'
'        ref_path = None\n'
'        if reference_b64:\n'
'            try:\n'
'                raw = base64.b64decode(reference_b64)\n'
'                os.makedirs(GEN_DIR, exist_ok=True)\n'
'                ts = time.strftime("%Y%m%d_%H%M%S")\n'
'                ref_path = os.path.join(GEN_DIR, "ref_%s_%d.png" % (ts, os.getpid()))\n'
'                open(ref_path, "wb").write(raw)\n'
'                log.info("gemini ref decoded -> %s (%d bytes)", ref_path, len(raw))\n'
'            except Exception as e:\n'
'                log.warning("gemini ref b64 decode fail: %s", e)\n'
'                ref_path = None\n'
'        elif reference_image and os.path.exists(reference_image):\n'
'            ref_path = reference_image\n'
'        log.info("gemini image: prompt=%s ref=%s", prompt[:80], ref_path)\n'
'        try:\n'
'            ok, host_path, container_path, err = gen_image_gemini(prompt, ref_path)\n'
'        finally:\n'
'            if ref_path and ref_path != reference_image and os.path.exists(ref_path):\n'
'                try:\n'
'                    os.remove(ref_path)\n'
'                except Exception:\n'
'                    pass\n'
'        if not ok:\n'
'            log.warning("gemini error: %s", err)\n'
'            self._send(200, {"ok": False, "error": err})\n'
'        else:\n'
'            log.info("gemini ok -> %s", container_path)\n'
'            self._send(200, {"ok": True, "path": host_path, "container_path": container_path, "error": ""})\n'
)
s = replace_method(s, '    def _handle_image_gemini(self):', new_m)

with open(p, 'w', encoding='utf-8') as f:
    f.write(s)
print("RELAY PATCHED OK; len=", len(s))
compile(s, p, 'exec')
print("SYNTAX OK")
