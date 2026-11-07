import subprocess, sys, os

out = {}
try:
    out['cli_version'] = subprocess.run(['icraft', '--version'], capture_output=True, text=True,
                                        timeout=20).stdout.strip().replace('\n', ' | ')
except Exception as e:
    out['cli_version'] = 'ERR %r' % (e,)

sys.path.insert(0, '/root/icraft39')
for mod in ('icraft', 'icraft.xrt', 'icraft.xir'):
    try:
        m = __import__(mod, fromlist=['x'])
        cand = [a for a in dir(m) if 'ver' in a.lower() or 'build' in a.lower()]
        vals = {}
        for a in cand[:6]:
            try:
                v = getattr(m, a)
                if not callable(v):
                    vals[a] = str(v)[:60]
            except Exception:
                pass
        out[mod] = vals
    except Exception as e:
        out[mod] = 'ERR %r' % (e,)

# .so 里的版本串
try:
    import re
    data = open('/lib/aarch64-linux-gnu/libicraft_xrt.so', 'rb').read(4 << 20)
    vers = sorted(set(re.findall(rb'3\.\d+\.\d+', data)))
    out['so_version_strings'] = [v.decode() for v in vers[:8]]
except Exception as e:
    out['so_version_strings'] = 'ERR %r' % (e,)

for k, v in out.items():
    print(k, '=', v)