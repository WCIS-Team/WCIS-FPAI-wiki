from pathlib import Path
import ast

p = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\server\backends\llm.py')
s = p.read_text(encoding='utf-8')
n = 0

# 1) 文档串：把 npuserv 那三行换掉（按实际 9 空格缩进）
old_doc = ("npuserv  板上 NPU 槽位（`lang/npuserv/`，2026-11-04 从 lang/llm/ 移入，本次移到 lang/npuserv，仍 server 管辖）。**只能 HTTP 编排**：CMA 池随 worker 进程\n"
           "         退出才归还、一次一模型、apply 50-132 s——这个档不装载任何模型，只调 /generate。\n"
           "         ids-in/ids-out 的件（ERNIE）需要分词器桥，见 README「缺什么」——没有就是明确报错。")
new_doc = ("npuserv  板上 NPU 槽位（`lang/npuserv/`，2026-11-04 从 lang/llm/ 移入，仍 server 管辖）。**只能 HTTP 编排**：\n"
           "         这个档不装载任何模型，只调 /generate。多轮上下文在本档内按 session 分桶\n"
           "         （`history_turns` 默认 2 轮，与 openai 档同款）——板端的件都是「每轮整 prompt\n"
           "         重放、KV 清零」，所以多轮＝纯文本拼接，不需要 KV 状态。件必须 text_in=true。")
if old_doc in s:
    s = s.replace(old_doc, new_doc); n += 1
else:
    print('skip doc')

# 2) __init__ 尾部加多轮参数
old_init = "        self.wait_s = int(_pick(p, \"wait_s\", \"NPUSERV_WAIT_S\", 10) or 10)"
new_init = ("        self.wait_s = int(_pick(p, \"wait_s\", \"NPUSERV_WAIT_S\", 10) or 10)\n"
            "        self.history_turns = int(_pick(p, \"history_turns\", \"HISTORY_TURNS\", 2) or 0)\n"
            "        self.system = os.environ.get(\"SYSTEM_PROMPT\") or p.get(\"system_prompt\", \"\") or DEFAULT_SYSTEM\n"
            "        self._hist = {}                                  # session -> [(user, reply)]\n"
            "        self._hlock = threading.Lock()")
if old_init in s:
    s = s.replace(old_init, new_init, 1); n += 1
else:
    print('skip init')

# 3) run 开头：拼 prompt
old_run = "    def run(self, text, session=None):\n        models = self._get(\"/models\")"
new_run = ("    def _prompt(self, text, hist):\n"
           "        \"\"\"历史轮拼成纯文本 prompt（件侧不套 chat template，形状归本层）。\"\"\"\n"
           "        parts = []\n"
           "        if self.system:\n"
           "            parts.append(self.system)\n"
           "        for turn in hist:\n"
           "            parts.append(\"用户：%s\" % turn[0])\n"
           "            parts.append(\"助手：%s\" % turn[1])\n"
           "        parts.append(\"用户：%s\" % text)\n"
           "        parts.append(\"助手：\")\n"
           "        return \"\\n\".join(parts)\n"
           "\n"
           "    def run(self, text, session=None):\n"
           "        sid = session or \"default\"\n"
           "        models = self._get(\"/models\")")
if old_run in s:
    s = s.replace(old_run, new_run, 1); n += 1
else:
    print('skip run head')

# 4) POST 用 prompt
old_post = ("        t0 = time.time()\n"
            "        obj = self._post(\"/generate\", {\"model\": self.model, \"text\": text,")
new_post = ("        with self._hlock:\n"
            "            hist = list(self._hist.get(sid, []))\n"
            "        prompt = self._prompt(text, hist) if self.history_turns > 0 else text\n"
            "        t0 = time.time()\n"
            "        obj = self._post(\"/generate\", {\"model\": self.model, \"text\": prompt,")
if old_post in s:
    s = s.replace(old_post, new_post, 1); n += 1
else:
    print('skip post')

# 5) 返回处回填历史 + reset 生效
old_ret = ("        return reply, {\"llm_ms\": int((time.time() - t0) * 1000),\n"
           "                       \"llm_model\": self.model, \"npuserv\": True}\n"
           "\n"
           "    def reset(self, session=None):\n"
           "        pass                                              # 多轮是 adapter 层的事，这里无状态")
new_ret = ("        with self._hlock:\n"
           "            if self.history_turns > 0:\n"
           "                h = self._hist.setdefault(sid, [])\n"
           "                h.append((text, reply))\n"
           "                if len(h) > self.history_turns:\n"
           "                    del h[:len(h) - self.history_turns]\n"
           "        meta = {\"llm_ms\": int((time.time() - t0) * 1000),\n"
           "                \"llm_model\": self.model, \"npuserv\": True, \"session\": sid}\n"
           "        if self.history_turns > 0:\n"
           "            meta[\"turns\"] = len(hist) + 1\n"
           "        return reply, meta\n"
           "\n"
           "    def reset(self, session=None):\n"
           "        with self._hlock:\n"
           "            if session:\n"
           "                self._hist.pop(session, None)\n"
           "            else:\n"
           "                self._hist.clear()")
if old_ret in s:
    s = s.replace(old_ret, new_ret, 1); n += 1
else:
    print('skip ret')

p.write_text(s, encoding='utf-8', newline='')
ast.parse(s)
print('applied', n, 'of 5 + syntax_ok')