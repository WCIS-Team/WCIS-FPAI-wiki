import json
from pathlib import Path

p = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\npuserv\models.json')
d = json.loads(p.read_text(encoding='utf-8'))
for m in d['models']:
    if m['id'] == 'qwen3-0.6b':
        m.setdefault('defaults', {})
        m['defaults']['json'] = '/root/qwen3/jr_path/decode_k128/Q3K128-decoder_ZG.json'
        m['defaults']['raw'] = '/root/qwen3/jr_path/decode_k128/Q3K128-decoder_ZG.raw'
        m['defaults']['max_decode_length'] = 128
        m['note'] = (m.get('note', '')
                     + ' 2026-11-07：K128 深度图（KV [1,8,128,128]，max_tokens_length=128，'
                       'mask0 patch n=128，25 链与校机 HF 参考 26/26 全等）——每步 KV DMA '
                       '112MB→28MB，速度上限目标 ~3 tok/s。回退＝删掉 defaults 的 json/raw '
                       '与 max_decode_length（恢复 512 定长件 /root/qwen3/jr_path/decode/）。')
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8', newline='')
print('registry updated for K128')