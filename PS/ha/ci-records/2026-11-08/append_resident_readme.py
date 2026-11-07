from pathlib import Path

repo = Path(r'S:\work\WCIS\repos\HA4FPAI')

# npuserv README: resident 模式段
np = repo / 'lang/npuserv/README.md'
n = np.read_text(encoding='utf-8')
n += """

## Resident mode (2026-11-08, experimental)

One long-lived worker holds **one** device and stacks model sessions on it:
`python server.py --resident`. `/load` imports the adapter inside the worker and
calls `load(params, device=<shared>)`; `/generate` routes by `"model"`;
`/unload` tears the session down, device stays. Measured on 113: qwen3-K168s +
hifigan-0.4s resident together, alternating generates all green (q3 2.06→2.54
tok/s, hf peak 1.0, workers list both engines).

**The rule this is built on (2026-11-08, replaces the earlier "device-exclusive"
conclusion): `openDevice()` must be called exactly once per process. A second
device handle — same process or another process — corrupts the first one's DMA
channels. Sessions on the one shared device can be layered and reloaded freely
(hf reload cycles x3 bit-identical; K128 + hifigan alternating forwards OK).**

Adapters must accept `load(params, device=None)`: when the worker injects the
shared device they must NOT call openDevice (qwen3 `init_device(device)` and the
hifigan `_apply(device=...)` are converted; ERNIE is not yet). A worker crash
loses all residents (Restart re-bootstraps an empty device) — same failure
envelope as before, now with cheaper re-loads for small models.

CMA unchanged: an LLM `apply()` still eats the pool; resident LLM + camera owner
remain mutually exclusive (docs/COEXISTENCE.md).
"""
np.write_text(n, encoding='utf-8', newline='')
print('npuserv README resident section added')
