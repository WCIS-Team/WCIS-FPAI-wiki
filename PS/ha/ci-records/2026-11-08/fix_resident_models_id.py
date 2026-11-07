from pathlib import Path
import ast

p = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\npuserv\server.py')
s = p.read_text(encoding='utf-8')
old = """    def describe_model(self, m):
        return {'id': m['adapter'] and m.get('id', ''), 'adapter': m['adapter'],
                'adapter_exists': os.path.exists(m['adapter']),
                'capabilities': m['capabilities'], 'defaults': m['defaults']}"""
new = """    def describe_model(self, model_id, m):
        # id 来自 registry 的 key（self.models[entry['id']]），value 里没有 'id' 字段
        return {'id': model_id, 'adapter': m['adapter'],
                'adapter_exists': os.path.exists(m['adapter']),
                'capabilities': m['capabilities'], 'defaults': m['defaults']}"""
assert old in s, 'describe anchor'
s = s.replace(old, new)
old2 = '''"models": [(m.describe() if hasattr(m, "describe") else
                                                dict(sorted(m.items())) ) for _, m in sorted(
                                                sv.models.items())]}'''
new2 = '''"models": [(m.describe() if hasattr(m, "describe") else
                                                sv.describe_model(k, m)) for k, m in sorted(
                                                sv.models.items())]}'''
assert old2 in s, 'models handler anchor'
s = s.replace(old2, new2)
p.write_text(s, encoding='utf-8', newline='')
ast.parse(s)
print('resident /models id fixed + syntax_ok')