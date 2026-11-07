import time

def snap():
    d = {}
    for line in open('/proc/stat'):
        if line.startswith('cpu') and line[3].isdigit():
            f = line.split()
            # user nice system idle iowait irq softirq steal ...
            busy = sum(int(x) for x in f[1:4]) + sum(int(x) for x in f[6:9])
            idle = int(f[4])
            d[f[0]] = (busy, idle)
    return d

a = snap()
time.sleep(10)
b = snap()
for c in sorted(a):
    tb = b[c][0] - a[c][0]
    ti = b[c][1] - a[c][1]
    tot = tb + ti
    if tot > 0:
        print('%s busy=%.0f%%' % (c, 100.0 * tb / tot))
