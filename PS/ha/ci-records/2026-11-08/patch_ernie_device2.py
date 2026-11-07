from pathlib import Path
import ast

p = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\llm\models\ERNIE-4.5-0.3B-PT4icraft430tai\board\e41_chatd.py')
s = p.read_text(encoding='utf-8')
old = """    def __init__(self):"""
new = """    def __init__(self, device=None):"""
assert old in s
s = s.replace(old, new, 1)
old2 = """        self.dev = openDevice("zg330", "192.168.125.143", True, False)
        self.sess = initSession("zg330", self.net, self.dev, 1)"""
new2 = """        # multi-resident: device may be injected by npuserv (openDevice once per
        # process; a second handle corrupts other sessions' DMA - 2026-11-08)
        self.dev = device if device is not None else openDevice(
            "zg330", "192.168.125.143", True, False)
        self.sess = initSession("zg330", self.net, self.dev, 1)"""
assert old2 in s
s = s.replace(old2, new2)
p.write_text(s, encoding='utf-8', newline='')
ast.parse(s)
print('e41_chatd __init__(device=None) ok')

p2 = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\llm\models\ERNIE-4.5-0.3B-PT4icraft430tai\board\npuserv_adapter.py')
s2 = p2.read_text(encoding='utf-8')
s2 = s2.replace("def load(params):", "def load(params, device=None):", 1)
s2 = s2.replace("    m = M.E41()", "    m = M.E41(device=device)", 1)
p2.write_text(s2, encoding='utf-8', newline='')
ast.parse(s2)
print('ernie adapter device-aware')