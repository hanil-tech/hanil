import sys
from oletools.olevba import VBA_Parser
p=VBA_Parser(sys.argv[1])
p.set_codepage = None
for (fn, stream, name, code) in p.extract_macros():
    if isinstance(code, bytes): code=code.decode('cp949','replace')
    open(sys.argv[2]+'/'+name,'w',encoding='utf-8').write(code)
    print(name, len(code.splitlines()))
