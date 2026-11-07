from pathlib import Path
import ast

p = Path(r'S:\work\WCIS\repos\HA4FPAI\lang\npuserv\server.py')
s = p.read_text(encoding='utf-8')
old = """    def status(self):
        j = self.job or {}
        out = {'state': j.get('state', 'idle'), 'resident': True,"""
new = """    def describe_model(self, m):
        return {'id': m['adapter'] and m.get('id', ''), 'adapter': m['adapter'],
                'adapter_exists': os.path.exists(m['adapter']),
                'capabilities': m['capabilities'], 'defaults': m['defaults']}

    def status(self):
        j = self.job or {}
        out = {'state': j.get('state', 'idle'), 'resident': True,"""
assert old in s
s = s.replace(old, new)
# /models handler: tolerate dict entries
old2 = '''"models": [m.describe() for m in sorted(
                                                sv.models.values(), key=lambda x: x.id)]}'''
new2 = '''"models": [(m.describe() if hasattr(m, "describe") else
                                                dict(sorted(m.items())) ) for _, m in sorted(
                                                sv.models.items())]}'''
assert old2 in s, 'models handler anchor missing'
s = s.replace(old2, new2)
p.write_text(s, encoding='utf-8', newline='')
ast.parse(s)
print('describe compat + syntax_ok')