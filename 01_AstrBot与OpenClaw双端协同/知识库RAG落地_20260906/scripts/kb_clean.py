#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清理知识库中的毒药分块：只有 breadcrumb/标题/分隔线、无实质正文的块。
这些块 embedding 接近常量，任何查询都给固定高分，严重挤占 top_k。
"""
import sys, os, json, re, importlib.util

spec = importlib.util.spec_from_file_location(
    'kb', os.path.join(os.path.dirname(__file__), 'kb_build.py'))
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)

MIN_KEEP = int(os.environ.get('MIN_KEEP', '60'))  # 实质正文少于该字数 -> 判垃圾

tok = kb.login()
kid = kb.load_kb_id()
docs = json.load(open(os.path.join(os.path.dirname(__file__), 'kb_docs.json'),
                      encoding='utf-8'))


def essence(t):
    """剥离 breadcrumb / 标题符号 / 分隔线 / 省略号前缀后的实质正文"""
    t = t or ''
    t = t.replace('...', ' ')
    # 去掉 "> " 面包屑最后一段之前的所有内容
    if '>' in t:
        t = t.split('>')[-1]
    t = re.sub(r'-{3,}', '', t)      # 分隔线
    t = re.sub(r'[#*`|~\[\]()]', '', t)
    t = re.sub(r'\s+', '', t)
    return t


all_chunks = []
for d in docs:
    page = 1
    while True:
        st, body = kb._req(
            'GET', '/api/v1/knowledge-bases/%s/chunks?doc_id=%s&page=%d&page_size=200'
                   % (kid, d['doc_id'], page), token=tok)
        try:
            dd = (json.loads(body).get('data') or {})
        except Exception:
            break
        items = dd.get('items') or []
        if not items:
            break
        for c in items:
            c['_doc'] = d['doc_name']
            all_chunks.append(c)
        if len(items) < 200:
            break
        page += 1

print('total chunks:', len(all_chunks))
buckets = {}
for c in all_chunks:
    n = len(essence(c.get('content')))
    b = 0 if n < 30 else (1 if n < 60 else (2 if n < 120 else 3))
    buckets[b] = buckets.get(b, 0) + 1
print('实质正文字数分布: <30字=%d  30-60=%d  60-120=%d  >=120=%d'
      % (buckets.get(0, 0), buckets.get(1, 0), buckets.get(2, 0), buckets.get(3, 0)))

junk = [c for c in all_chunks if len(essence(c.get('content'))) < MIN_KEEP]
print('判定垃圾块(实质<%d字): %d / %d' % (MIN_KEEP, len(junk), len(all_chunks)))
for c in junk[:8]:
    print('   %s :: %s' % (c['_doc'], (c.get('content') or '').replace('\n', ' ')[:90]))

if '--delete' in sys.argv:
    ok = 0
    for c in junk:
        st, b = kb._req('DELETE', '/api/v1/knowledge-bases/%s/chunks/%s'
                        % (kid, c.get('chunk_id')), token=tok)
        if st == 200:
            ok += 1
    print('deleted %d / %d' % (ok, len(junk)))
    kb.stats(tok)
else:
    print('\n(dry-run) 加 --delete 执行删除；MIN_KEEP 环境变量可调阈值')
