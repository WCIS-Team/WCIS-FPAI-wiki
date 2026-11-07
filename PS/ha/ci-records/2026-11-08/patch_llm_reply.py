from pathlib import Path
import ast

p = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\server\backends\llm.py')
s = p.read_text(encoding='utf-8')
old = """        end = obj.get("end") or obj                       # 兼容直接回 end object 的形状
        reply = None
        for k in ("text", "reply", "content", "gen_text"):
            v = end.get(k) if isinstance(end, dict) else None
            if isinstance(v, str) and v.strip():
                reply = v.strip()
                break
        if reply is None:
            keys = sorted(end.keys()) if isinstance(end, dict) else type(end).__name__
            raise RuntimeError("npuserv 回包里抠不到文本（end=%s）：ids-out 件要接分词器桥，见 README"
                               % keys)"""
new = """        # 真 /generate 的回包就是 end 事件本身：{"end": true, "text": ..., ...}。
        # 不能写 obj.get("end") or obj ——那会把 True 当回包（2026-11-08 单测抓到的真 bug）。
        cand = obj if isinstance(obj, dict) else {}
        nested = cand.get("end")
        if isinstance(nested, dict):
            cand = nested
        reply = None
        for k in ("text", "reply", "content", "gen_text"):
            v = cand.get(k)
            if isinstance(v, str) and v.strip():
                reply = v.strip()
                break
        if reply is None:
            raise RuntimeError("npuserv 回包里抠不到文本（keys=%s）：ids-out 件要接分词器桥，见 README"
                               % sorted(cand.keys()))"""
assert old in s, 'reply extraction anchor'
s = s.replace(old, new)
p.write_text(s, encoding='utf-8', newline='')
ast.parse(s)
print('reply extraction fixed + syntax_ok')