#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ERNIE 多轮验收（板上跑，真 npuserv 18080）：第一问报名字，第二问看能否召回。"""

import sys, os, threading
sys.path.insert(0, '/tmp/langtest')

os.environ['NPUSERV_MODEL'] = 'ernie-4.5-0.3b'
os.environ['NPUSERV_MAX_NEW'] = '32'

from backends import llm as L


class S(object):
    def __init__(self, *a, **kw):
        pass


L.Stage = S


def mk():
    b = L.NpuServ.__new__(L.NpuServ)
    b.name = 'npuserv'
    b.profile = {}
    b.base = 'http://127.0.0.1:18080'
    b.model = 'ernie-4.5-0.3b'
    b.max_new = 32
    b.timeout = 300
    b.wait_s = 10
    b.history_turns = 2
    b.system = '你是一个中文语音助手，回答口语化、简短。'
    b._hist = {}
    b._hlock = threading.Lock()
    return b


b = mk()
print('status:', b._get('/status').get('state'), flush=True)

r1, m1 = b.run('我叫小明', session='user1')
print('T1:', r1, '| turns=', m1.get('turns'), '| ms=', m1.get('llm_ms'), flush=True)
print('-' * 40, flush=True)

r2, m2 = b.run('请问我叫什么名字？', session='user1')
print('T2:', r2, '| turns=', m2.get('turns'), '| ms=', m2.get('llm_ms'), flush=True)
print('-' * 40, flush=True)

print('PASS: 多轮上下文认到名字' if '小明' in r2 else 'FAIL: 未召回名字', flush=True)