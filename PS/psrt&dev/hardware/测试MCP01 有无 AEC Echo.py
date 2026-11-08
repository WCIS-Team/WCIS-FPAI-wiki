#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP01 板「自放自录 + WebRTC AEC」取证 —— 桌面双击入口。

干活的正本只有一个：S:\\work\\WCIS\\workenv\\aec1029b\\aec_flow.py
这个文件负责把控制台切到 UTF-8、让你选模式、然后起那个正本；不复制任何逻辑。

双击后直接回车 = 1（全流程）。全流程每一步都会停下等你按回车，
所以你可以按自己节奏来；中途关窗口 = 放弃这一轮，已录的文件留在 workenv。
"""
import os
import subprocess
import sys
import traceback

SRC = r"S:\work\WCIS\workenv\aec1029b"
PULL = os.path.join(SRC, "pull")
MENU = """
要跑哪一种？（直接回车 = 1）

  1  全流程：板子录音 -> WebRTC AEC -> ASR -> 交付到桌面文件夹
       前提：MCP01 喇叭已插上 / 板子 192.168.1.113 可达 / 占用登记 113.txt = off
       顺序：先录 15 s 底噪(都别出声) -> 你讲话 -> 板子三档响(你别说话) -> 板子放整段(你别说话) -> 你和板子同时讲
  2  只查前提：连板子、看喇叭、看占用登记、确认 deb-h61 上编译件在不在；不录音
  3  离线跑 pull/run2.wav（既有录音：板子放 + 你讲话）—— 不碰板子
  4  离线跑 pull/run1.wav（既有录音：板子放）—— 不碰板子
  5  只算对齐与电平（不 AEC、不 ASR、不写交付），用 pull/run2.wav

产物：桌面 MCP01-AEC-<时间戳>\\ 里有 AEC.报告.md、原声、AEC 后、参考原件、两份文字。
"""


def pick():
    while True:
        try:
            c = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if c in ("", "1"):
            return "1"
        if c in ("2", "3", "4", "5"):
            return c
        print("  只认 1/2/3/4/5（回车算 1）。")


def argv_for(c):
    if c == "1":
        return ["live"]
    if c == "2":
        return ["check"]
    if c in ("3", "4"):
        mic = os.path.join(PULL, "run2.wav" if c == "3" else "run1.wav")
        ref = os.path.join(PULL, "prog.wav")
        amb = os.path.join(PULL, "amb15.wav")
        if not (os.path.isfile(mic) and os.path.isfile(ref)):
            print("  缺 %s 或 %s，跑不了离线。" % (mic, ref))
            return None
        # 标签跟着素材走（run2.wav -> RUN2），不然报告里的轮次名和文件对不上
        tag = "RUN2" if c == "3" else "RUN1"
        argv = ["offline", mic, ref, tag]
        if os.path.isfile(amb):
            argv.append(amb)
        else:
            print("  没有 %s，这份报告就没有环境底噪当地板，dB 只能文件内部自比。" % amb)
        return argv
    if c == "5":
        return ["metrics", os.path.join(PULL, "run2.wav"), os.path.join(PULL, "prog.wav")]
    return None


def main():
    subprocess.run(["chcp.com", "65001"], capture_output=True, timeout=10)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("=" * 70)
    print("MCP01 板自放自录 + WebRTC AEC3 取证流水线")
    print("=" * 70)
    print(MENU)
    c = pick()
    if c is None:
        print("取消了。")
        return 0
    argv = argv_for(c)
    if argv is None:
        return 2
    if not os.path.isfile(os.path.join(SRC, "aec_flow.py")):
        print("正本不在：%s\\aec_flow.py" % SRC)
        return 3
    sys.path.insert(0, SRC)
    import aec_flow

    print("\n开始：%s\n" % " ".join(argv))
    try:
        return aec_flow.main(["aec_flow.py"] + argv)
    except KeyboardInterrupt:
        print("\n你按了 Ctrl+C，这一轮就到这里；已录的东西留在 %s 下最新的 run-* 目录。" % SRC)
        return 130
    except Exception:
        print("\n出了没预料到的错，原文如下：")
        traceback.print_exc()
        print("\n如果是'板子连不上/喇叭不在位/占用登记不是 off'，处理完再双击一次就行。")
        return 1


if __name__ == "__main__":
    code = 2
    try:
        code = main()
    finally:
        try:
            input("\n跑完了（退出码 %s），按回车关窗口。" % code)
        except Exception:
            pass
    sys.exit(code)
