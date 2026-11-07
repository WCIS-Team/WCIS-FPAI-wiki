import json

d = json.load(open(r'S:\work\WCIS\workenv\migrate-real-preview\ref_fix_chain.json', encoding='utf-8'))
steps = d['chain']['steps']
ref = [s['argmax'] for s in steps]
new = [151667, 198, 99692, 3837, 20002, 56007, 104198, 100165, 1773, 35946, 85106,
       60726, 81167, 20002, 103936, 111450, 1773, 20002, 87267, 101219, 81705,
       97611, 102104, 99788, 3837, 100631]
n = min(len(ref), len(new))
match = sum(1 for i in range(n) if ref[i] == new[i])
print('ref_len=%d match=%d/%d' % (len(ref), match, n))
for i in range(n):
    mark = 'OK ' if ref[i] == new[i] else 'DIF'
    if ref[i] != new[i] or i < 3:
        print(mark, i, 'ref', ref[i], 'k128', new[i])