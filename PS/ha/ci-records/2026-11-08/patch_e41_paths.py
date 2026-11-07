from pathlib import Path
import ast

p = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\llm\models\ERNIE-4.5-0.3B-PT4icraft430tai\board\e41_chatd.py')
s = p.read_text(encoding='utf-8')
s = s.replace('JSON_ = os.environ.get("E41_JSON", "/mnt/data/ernie/jr_path/decode/E41-decoder_ZG.json")',
              'JSON_ = os.environ.get("E41_JSON",\n'
              '                     "/root/llm/models/ERNIE-4.5-0.3B-PT4icraft430tai/jr_path/decode/E41-decoder_ZG.json")')
s = s.replace('RAW_ = os.environ.get("E41_RAW", "/mnt/data/ernie/jr_path/decode/E41-decoder_ZG.raw")',
              'RAW_ = os.environ.get("E41_RAW",\n'
              '                     "/root/llm/models/ERNIE-4.5-0.3B-PT4icraft430tai/jr_path/decode/E41-decoder_ZG.raw")')
p.write_text(s, encoding='utf-8', newline='')
ast.parse(s)
print('e41 paths fixed')