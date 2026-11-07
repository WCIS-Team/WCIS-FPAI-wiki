#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ERNIE 多轮验收（板上跑，真 npuserv）：第一问记住名字，第二问看能否召回。"""

import sys, os, threading, time
sys.path.insert(0, '/root/lang/server')
os.environ['NPUSERV_MODEL'] = 'ernie-4.5-0.3b'
os.environ['NPUSERV_MAX_NEW'] = '32'

from backends import llm as L

class S(object):
    def __init__(self, *a, **kw): pass

L.Stage = S

def mk():
    b = L.NpuServ.__new__(L.NpuServ)
    b.name = 'npuserv'; b.profile = {}
    b.base = 'http://127.0.0.1:18080'
    b.model = 'ernie-4.5-0.3b'; b.max_new = 32; b.timeout = 300; b.wait_s = 10
    b.history_turns = 2
    b.system = '你是一个中文语音助手，回答口语化、简短。'
    b._hist = {}
    b._hlock = threading.Lock()
    return b

print('load ernie');
b = mk()
print(b._get('/status'))

r1, m1 = b.run('我叫小明', session='user1')
print('T1:', r1); print('turns=', m1.get('turns')); print('-'*40)

r2, m2 = b.run('请问我叫什么名字？', session='user1')
print('T2:', r2); print('turns=', m2.get('turns')); print('-'*40)

if '小明' in r2.lower():
    print('PASS: 多轮上下文识别成功')
else:
    print('FAIL: 没有记住名字', r2)