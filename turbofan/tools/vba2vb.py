#!/usr/bin/env python3
"""Translate the Turbo Fan Design AutoCAD-VBA project into VB.NET.

    python3 tools/vba2vb.py

reads   original/vba/*.bas|*.cls|*.frm   and   tools/forms.json   (form layouts from the .dvb)
writes  src/Converted/*.vb               (modules, classes, form code)
        src/Forms/*.Designer.vb          (form layouts)
        src/Resources/*                  (pictures embedded in forms)

The translation keeps the original statements line for line wherever VB.NET allows,
so the converted code can be compared side by side with the VBA.
"""
import json, os, re, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC_VBA = os.path.join(ROOT, 'original', 'vba')
OUT = os.path.join(ROOT, 'src', 'Converted')
OUT_FORMS = os.path.join(ROOT, 'src', 'Forms')
OUT_RES = os.path.join(ROOT, 'src', 'Resources')

SKIP_MODULES = {'ThisDrawing', 'ResizeFrm', 'GetOSVersion', 'mStart'}   # unused / replaced by Program.vb

FORMS = json.load(open(os.path.join(HERE, 'forms.json'), encoding='utf-8'))

WRAP = {'TextBox': 'MTextBox', 'ComboBox': 'MComboBox', 'ListBox': 'MComboBox', 'OptionButton': 'MOptionButton',
        'CheckBox': 'MCheckBox', 'ToggleButton': 'MCheckBox', 'CommandButton': 'MCommandButton', 'Label': 'MLabel',
        'Frame': 'MFrame', 'Image': 'MImage'}
DEFAULT_PROP = {'TextBox': 'Text', 'ComboBox': 'Text', 'ListBox': 'Text', 'OptionButton': 'Value', 'CheckBox': 'Value',
                'ToggleButton': 'Value', 'Label': 'Caption', 'Frame': 'Caption', 'CommandButton': 'Caption',
                'Image': 'Picture'}


def all_controls(ctrls):
    for c in ctrls:
        yield c
        if 'children' in c:
            yield from all_controls(c['children'])


FORM_CONTROLS = {}
for fname, f in FORMS.items():
    FORM_CONTROLS[fname] = {c['name']: c['type'] for c in all_controls(f['controls'])}
FORM_NAMES = set(FORMS) - {'frmSetLogo'}

# "Public x As New T" in any standard module: VBA re-creates it on the next use after "Set x = Nothing"
GLOBAL_NEW_VARS = {}

# ------------------------------------------------------------------ lexical helpers

def split_comment(line):
    """-> (code, comment) ; comment includes the leading quote."""
    in_str = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_str = not in_str
        elif ch == "'" and not in_str:
            return line[:i], line[i:]
        elif not in_str and line[i:i + 4].lower() == 'rem ' and line[:i].strip() == '':
            return line[:i], "'" + line[i + 3:]
        i += 1
    return line, ''


def mask_strings(s):
    """replace string literal contents by \x01 so regexes do not see them; returns masked, restore()"""
    lits = []

    def rep(m):
        lits.append(m.group(0))
        return '\x02%d\x03' % (len(lits) - 1)
    masked = re.sub(r'"(?:[^"]|"")*"', rep, s)

    def restore(t):
        return re.sub('\x02(\\d+)\x03', lambda m: lits[int(m.group(1))], t)
    return masked, restore


def split_top(s, sep):
    """split masked string s on separator char at paren depth 0"""
    out, depth, cur = [], 0, ''
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if depth == 0 and s.startswith(sep, i):
            if sep == ':' and s.startswith(':=', i):
                cur += ':='
                i += 2
                continue
            out.append(cur)
            cur = ''
            i += len(sep)
            continue
        cur += ch
        i += 1
    out.append(cur)
    return out


def find_kw(s, kw):
    """position of keyword kw (as a whole word) at depth 0 in masked s, or -1"""
    depth = 0
    for m in re.finditer(r'[()]|\b%s\b' % kw, s, re.I):
        t = m.group(0)
        if t == '(':
            depth += 1
        elif t == ')':
            depth -= 1
        elif depth == 0:
            return m.start()
    return -1


def matching_paren(s, i):
    depth = 0
    for j in range(i, len(s)):
        if s[j] == '(':
            depth += 1
        elif s[j] == ')':
            depth -= 1
            if depth == 0:
                return j
    return -1


STATEMENT_KW = {'dim', 'redim', 'if', 'elseif', 'else', 'end', 'for', 'next', 'do', 'loop', 'while', 'wend', 'select',
                'case', 'with', 'exit', 'goto', 'on', 'resume', 'return', 'call', 'const', 'public', 'private',
                'static', 'set', 'let', 'sub', 'function', 'property', 'option', 'type', 'declare', 'open', 'close',
                'input', 'line', 'print', 'get', 'put', 'global', 'erase', 'randomize', 'stop', 'friend', 'debug.print',
                'mid', 'each', 'until', 'byval', 'byref', 'optional'}

TYPE_MAP = {'variant': 'Object', 'currency': 'Decimal', 'form': 'Object', 'control': 'Object', 'userform': 'Object',
            'textbox': 'MTextBox', 'combobox': 'MComboBox', 'label': 'MLabel', 'commandbutton': 'MCommandButton',
            'optionbutton': 'MOptionButton', 'checkbox': 'MCheckBox', 'frame': 'MFrame', 'image': 'MImage',
            'collection': 'VBCollection'}


def map_type(t):
    t = t.strip()
    low = t.lower()
    if low.startswith('msforms.'):
        low = low[8:]
        t = t[8:]
    if low in TYPE_MAP:
        return TYPE_MAP[low]
    if re.match(r'acad\w*$', low) or low.startswith('word.') or low.startswith('autocad.'):
        return 'Object'
    return t


VB_RESERVED = {'variant', 'wend', 'gosub', 'let', 'object', 'short', 'char', 'structure', 'class', 'interface',
               'delegate', 'try', 'catch', 'finally', 'using', 'handles', 'shared', 'inherits', 'namespace', 'module',
               'imports', 'overloads', 'overrides', 'protected', 'readonly', 'shadows', 'when', 'throw', 'operator',
               'partial', 'continue', 'of', 'default', 'mybase', 'myclass', 'narrowing', 'widening', 'synclock',
               'ctype', 'directcast', 'trycast', 'gettype', 'isnot', 'uinteger', 'ulong', 'ushort', 'sbyte', 'cobj',
               'cchar', 'cshort', 'csbyte', 'cuint', 'culng', 'cushort', 'addhandler', 'removehandler', 'raiseevent',
               'notinheritable', 'notoverridable', 'mustinherit', 'mustoverride', 'overridable', 'writeonly',
               'andalso', 'orelse', 'global', 'async', 'await', 'iterator', 'yield'}

# ------------------------------------------------------------------ translator


class Translator:
    def __init__(self, modname, kind, form_ctrls=None):
        self.mod = modname
        self.kind = kind            # 'bas' | 'cls' | 'frm'
        self.form_ctrls = form_ctrls or {}
        self.new_vars = {}          # name.lower() -> type for "As New T" declarations
        self.warnings = []
        self.handlers = []          # (proc name, control, event) for forms
        self.has_initialize = False
        self.byref_params = {}      # proc -> set of param names assigned

    def warn(self, msg):
        self.warnings.append('%s: %s' % (self.mod, msg))

    # --- expressions -------------------------------------------------------
    def expr(self, s, lhs=False):
        """translate an expression (masked string)"""
        # ThisDrawing helpers
        s = re.sub(r'\bThisDrawing\.Application\.Path\b', 'SupportRoot()', s, flags=re.I)
        s = re.sub(r'\bThisDrawing\.Utility\.PolarPoint\s*\(', 'PolarPoint(', s, flags=re.I)
        # $-suffixed string functions
        s = re.sub(r'\b(Left|Right|Mid|Trim|LTrim|RTrim|Str|Chr|UCase|LCase|Space|String|Format|Hex|Oct)\$', r'\1', s, flags=re.I)
        # VBA Date / Time / Now as values
        s = re.sub(r'(?<![.\w])Date(?![\w(])', 'DateTime.Today', s)
        # Null comparisons
        s = re.sub(r'(\b[\w.()]+)\s*=\s*Null\b', r'IsNothing(\1)', s, flags=re.I)
        s = re.sub(r'\bIsNull\s*\(', 'IsNothing(', s, flags=re.I)
        # New Word.Application
        s = re.sub(r'\bNew\s+Word\.Application\b', 'CreateObject("Word.Application")', s, flags=re.I)
        # string functions that collide with Form members inside form classes
        if self.kind == 'frm':
            s = re.sub(r'(?<![.\w])(Left|Right)\s*\(', r'Strings.\1(', s)
        # TypeOf x Is TextBox
        s = re.sub(r'\bIs\s+(TextBox|ComboBox|Label|CommandButton|OptionButton|CheckBox|Frame|Image)\b',
                   lambda m: 'Is ' + TYPE_MAP[m.group(1).lower()], s)
        s = self.default_props(s)
        if self.kind == 'frm':
            s = re.sub(r'(?<![.\w])%s\.' % self.mod, 'Me.', s, flags=re.I)
        return s

    def default_props(self, s):
        """frmX.ctrl / bare ctrl used as a value -> add default property (.Text/.Value/.Caption)"""
        def repl_qualified(m):
            form, ctrl = m.group(1), m.group(2)
            fdef = FORM_CONTROLS.get(form)
            if fdef is None or ctrl not in fdef:
                ckey = {k.lower(): k for k in (fdef or {})}.get(ctrl.lower())
                if not ckey:
                    return m.group(0)
                ctrl = ckey
            prop = DEFAULT_PROP.get(fdef[ctrl])
            if not prop:
                return m.group(0)
            return '%s.%s.%s' % (form, m.group(2), prop)
        s = re.sub(r'(?<![.\w])(%s)\.(\w+)(?![\w.(])' % '|'.join(FORM_NAMES), repl_qualified, s, flags=re.I)
        if self.kind == 'frm':
            names = {k.lower(): v for k, v in self.form_ctrls.items()}

            def repl_bare(m):
                n = m.group(2)
                t = names.get(n.lower())
                if not t or t not in DEFAULT_PROP:
                    return m.group(0)
                return '%s%s.%s' % (m.group(1), n, DEFAULT_PROP[t])
            s = re.sub(r'(^|[^.\w])(\w+)(?![\w.(])', repl_bare, s)
            s = re.sub(r'\bMe\.(\w+)(?![\w.(])', lambda m: 'Me.%s.%s' % (m.group(1), DEFAULT_PROP[names[m.group(1).lower()]])
                       if names.get(m.group(1).lower()) in DEFAULT_PROP else m.group(0), s)
        return s

    def paren_value(self, s):
        """argument positions: wrap control default-property reads in parens so they are passed by value"""
        return s

    # --- statements ----------------------------------------------------------
    def statement(self, st):
        """translate a single statement (masked, no comment, no ':' separators)"""
        lead = re.match(r'\s*', st).group(0)
        body = st.strip()
        if body == '':
            return st
        low = body.lower()
        first = re.match(r'[\w.$#]+', low)
        firstw = first.group(0) if first else ''

        # labels (handled by caller), single-line If
        if firstw == 'if' and re.search(r'\bthen\b\s*\S', low):
            return lead + self.single_if(body)
        if firstw in ('if', 'elseif'):
            return lead + self.expr(body)
        if firstw == 'set':
            body = body[3:].strip()
            m = re.match(r'([\w.]+)\s*=\s*Nothing$', body, re.I)
            if m and m.group(1).lower() in self.new_vars:
                return lead + '%s = New %s' % (m.group(1), self.new_vars[m.group(1).lower()])
            if m and m.group(1).lower() in GLOBAL_NEW_VARS:
                return lead + '%s = New %s' % (m.group(1), GLOBAL_NEW_VARS[m.group(1).lower()])
            return lead + self.assignment(body, is_set=True)
        if firstw == 'let':
            body = body[3:].strip()
            return lead + self.assignment(body)
        if firstw == 'wend':
            return lead + 'End While'
        if firstw in ('dim', 'static', 'private', 'public', 'global', 'const', 'redim') and not re.match(
                r'(private|public|friend|static)\s+(sub|function|property|declare|type|enum)\b', low):
            return lead + self.declaration(body)
        if firstw == 'debug.print':
            return lead + 'Debug.WriteLine(%s)' % self.expr(body[11:].strip() or '""')
        if firstw == 'open':
            m = re.match(r'Open\s+(.+?)\s+For\s+(Input|Output|Append|Binary|Random)\s+As\s+#?\s*(\w+)$', body, re.I)
            if m:
                return lead + 'FileOpen(%s, %s, OpenMode.%s)' % (m.group(3), self.expr(m.group(1)), m.group(2).capitalize())
        if firstw == 'close':
            m = re.match(r'Close\s*#?\s*(\w*)$', body, re.I)
            if m:
                return lead + ('FileClose(%s)' % m.group(1) if m.group(1) else 'FileClose()')
        if firstw == 'input':
            m = re.match(r'Input\s*#\s*(\w+)\s*,\s*(.+)$', body, re.I)
            if m:
                vars_ = [v.strip() for v in split_top(m.group(2), ',')]
                return lead + ' : '.join('Input(%s, %s)' % (m.group(1), self.expr(v)) for v in vars_)
        if firstw == 'line':
            m = re.match(r'Line\s+Input\s*#\s*(\w+)\s*,\s*(.+)$', body, re.I)
            if m:
                return lead + '%s = LineInput(%s)' % (self.expr(m.group(2)), m.group(1))
        if firstw == 'print':
            m = re.match(r'Print\s*#\s*(\w+)\s*,\s*(.*)$', body, re.I)
            if m:
                return lead + 'PrintLine(%s, %s)' % (m.group(1), self.expr(m.group(2)))
        if firstw == 'call':
            return lead + 'Call ' + self.expr(body[4:].strip())
        if firstw in ('for',):
            m = re.match(r'For\s+Each\s+(\w+)\s+In\s+(.+)$', body, re.I)
            if m:
                return lead + 'For Each %s In %s' % (m.group(1), self.expr(m.group(2)))
            return lead + self.expr(body)
        if firstw in ('do', 'loop', 'while', 'select', 'case', 'with', 'exit', 'goto', 'on', 'resume', 'return', 'else',
                      'end', 'next', 'erase', 'randomize', 'stop', 'elseif'):
            if firstw == 'with':
                return lead + 'With ' + self.expr_no_default(body[4:].strip())
            if firstw == 'end' and low == 'end':
                return lead + 'End'
            return lead + self.expr(body)
        # assignment or call
        return lead + self.call_or_assign(body)

    def expr_no_default(self, s):
        saved = self.form_ctrls
        # With <control> must stay the control
        if self.kind == 'frm' and re.match(r'\w+$', s):
            return s
        if re.match(r'(%s)\.\w+$' % '|'.join(FORM_NAMES), s, re.I):
            return s
        return self.expr(s)

    def single_if(self, body):
        p = find_kw(body, 'then')
        cond = body[:p]
        rest = body[p + 4:].strip()
        e = find_kw(rest, 'else')
        then_part, else_part = (rest[:e], rest[e + 4:]) if e >= 0 else (rest, None)
        out = self.expr(cond) + 'Then ' + self.multi(then_part.strip())
        if else_part is not None:
            out += ' Else ' + self.multi(else_part.strip())
        return out

    def multi(self, s):
        return ' : '.join(self.statement(x).strip() for x in split_top(s, ':') if x.strip())

    def assignment_split(self, body):
        """-> (lhs, rhs) if body is an assignment, else None"""
        m = re.match(r'(\.?[\w]+(?:\s*\([^=]*?\))?(?:\.[\w]+(?:\s*\([^=]*?\))?)*)\s*=(?!=)(.*)$', body)
        if not m:
            return None
        lhs = m.group(1)
        # make sure the '(' groups in lhs are balanced
        if lhs.count('(') != lhs.count(')'):
            return None
        return lhs, m.group(2)

    def assignment(self, body, is_set=False):
        a = self.assignment_split(body)
        if not a:
            return self.expr(body)
        lhs, rhs = a
        rhs_t = self.expr(rhs.strip())
        lhs_t = self.expr(lhs.strip(), lhs=True)
        if not is_set and re.match(r'[\w.]+$', rhs.strip()) and not re.match(r'[\d.]+$', rhs.strip()) \
                and rhs.strip().lower() not in ('true', 'false', 'nothing', 'empty') and not rhs_t.lower().endswith(('.text', '.value', '.caption')):
            rhs_t = 'VbCopy(%s)' % rhs_t
        if re.search(r'\.(BackColor|ForeColor|BorderColor)$', lhs_t, re.I) and self.kind == 'frm' or \
                re.match(r'(%s)\.\w+\.(BackColor|ForeColor)$' % '|'.join(FORM_NAMES), lhs_t, re.I):
            rhs_t = 'OleColor(%s)' % rhs_t
        return '%s = %s' % (lhs_t, rhs_t)

    def call_or_assign(self, body):
        a = self.assignment_split(body)
        if a:
            return self.assignment(body)
        m = re.match(r'\.?[A-Za-z_]\w*', body)
        if not m:
            return self.expr(body)
        # callee chain: ident(.ident|(...))* without blanks
        i = m.end()
        while i < len(body):
            if body[i] == '(':
                j = matching_paren(body, i)
                if j < 0:
                    break
                i = j + 1
                continue
            mm = re.match(r'\.[A-Za-z_]\w*', body[i:])
            if mm:
                i += len(mm.group(0))
                continue
            break
        callee, rest = body[:i], body[i:]
        if rest.strip() == '':
            return self.expr(callee)
        if rest[:1] not in (' ', '\t'):
            return self.expr(body)
        args = split_top(rest.strip(), ',')
        return '%s(%s)' % (self.expr(callee), ', '.join(self.arg(x.strip()) for x in args))

    def arg(self, a):
        """statement-call argument. Anything that reads a property (has a '.') is passed by value:
        VBA never writes a ByRef argument back into a property, VB.NET would."""
        if a == '':
            return ''
        named = re.match(r'(\w+:=)\s*(.*)$', a)
        if named:
            return named.group(1) + self.arg(named.group(2))
        t = self.expr(a)
        if re.match(r'^\.?[A-Za-z_][\w]*(\.[A-Za-z_]\w*)+$', t) and not re.match(r'^(Me)\.\w+$', t, re.I):
            t = '(%s)' % t
        return t

    # --- declarations -------------------------------------------------------
    def declaration(self, body):
        m = re.match(r'(ReDim\s+Preserve|ReDim|Dim|Static|Private\s+Const|Public\s+Const|Global\s+Const|Const|Private|Public|Global)\s+(.*)$', body, re.I)
        if not m:
            return self.expr(body)
        kw, rest = m.group(1), m.group(2)
        kwl = kw.lower()
        if kwl.startswith('global'):
            kw = 'Public' + kw[6:]
        if self.kind == 'bas' and kwl == 'dim':
            pass
        if 'const' in kwl:
            return '%s %s' % (kw, self.expr(rest))
        items = split_top(rest, ',')
        out = []
        for it in items:
            it = it.strip()
            mm = re.match(r'(?:WithEvents\s+)?(\w+)\s*(\([^)]*\))?\s*(?:As\s+(New\s+)?([\w.]+)(?:\s*\*\s*\d+)?)?\s*(=.*)?$', it, re.I)
            if not mm:
                out.append(self.expr(it))
                continue
            name, dims, new, typ, init = mm.groups()
            if name.lower() in VB_RESERVED:
                name = '[%s]' % name
            d = ''
            if dims is not None:
                inner = dims[1:-1].strip()
                if inner:
                    parts = []
                    for p in split_top(inner, ','):
                        p2 = re.sub(r'^\s*(.+?)\s+To\s+', '', p, flags=re.I)
                        lb = re.match(r'^\s*(.+?)\s+To\s+', p, re.I)
                        if lb and lb.group(1).strip() not in ('0', '1'):
                            self.warn('array lower bound %s in %s' % (lb.group(1), it))
                        parts.append(self.expr(p2.strip()))
                    d = '(%s)' % ', '.join(parts)
                else:
                    d = '()'
            t = ''
            if typ:
                mt = map_type(typ)
                if new:
                    if typ.lower().startswith('word.'):
                        t = ' As Object = CreateObject("Word.Application")'
                    else:
                        t = ' As New %s' % mt
                        self.new_vars[name.lower().strip('[]')] = mt
                else:
                    t = ' As %s' % mt
            elif kwl.startswith('redim'):
                t = ''
            else:
                t = ' As Object' if not d else ' As Object'
            out.append('%s%s%s%s' % (name, d, t, (' ' + init) if init else ''))
        return '%s %s' % (kw, ', '.join(out))

    def proc_header(self, line, body_lines):
        """Sub/Function header -> VB.NET header"""
        m = re.match(r'(\s*)((?:Public|Private|Friend)\s+)?(Static\s+)?(Sub|Function)\s+(\w+)\s*\((.*)\)\s*(As\s+[\w.]+)?\s*$', line, re.I)
        if not m:
            raise ValueError('cannot parse header: ' + line)
        lead, vis, static, kind, name, params, ret = m.groups()
        vis = (vis or '').strip()
        # form event handlers
        if self.kind == 'frm':
            h = self.form_handler(name, params)
            if h:
                return h
        ps = []
        body = '\n'.join(body_lines)
        assigned = set()
        for p in split_top(params, ',') if params.strip() else []:
            p = p.strip()
            pm = re.match(r'(Optional\s+)?(ByVal\s+|ByRef\s+)?(ParamArray\s+)?(\w+)(\(\))?\s*(?:As\s+([\w.]+))?\s*(=\s*.+)?$', p, re.I)
            if not pm:
                raise ValueError('param: ' + p)
            opt, by, parr, pname, arr, ptype, dflt = pm.groups()
            ptype_t = map_type(ptype) if ptype else 'Object'
            if by is None and not parr:
                is_assigned = re.search(r'(^|[\n:]|\bThen\b|\bElse\b|\bFor\s+)\s*(Set\s+)?%s\s*(\([^\n]*?\))?\s*=' % re.escape(pname), body, re.I)
                if arr or is_assigned or ptype_t == 'Object':
                    by = 'ByRef '
                    if is_assigned:
                        assigned.add(pname)
                else:
                    by = 'ByVal '
            s = '%s%s%s%s%s As %s' % (opt or '', by or '', parr or '', pname, arr or '', ptype_t)
            if opt and not dflt:
                s += ' = Nothing'
            elif dflt:
                s += ' ' + dflt
            ps.append(s)
        if assigned:
            self.byref_params[name] = assigned
        if name.lower() == 'class_initialize' and self.kind == 'cls':
            return lead + 'Public Sub New()'
        if name.lower() == 'class_terminate':
            return lead + 'Private Sub Class_Terminate()'
        r = ''
        if ret:
            r = ' As ' + map_type(ret[2:].strip())
        elif kind.lower() == 'function':
            r = ' As Object'
        return '%s%s%s %s(%s)%s' % (lead, (vis + ' ') if vis else '', kind.capitalize(), name, ', '.join(ps), r)

    def form_handler(self, name, params):
        m = re.match(r'(\w+)_(\w+)$', name)
        if not m:
            return None
        ctrl, ev = m.group(1), m.group(2)
        evl = ev.lower()
        if ctrl.lower() == 'userform':
            if evl == 'initialize':
                self.has_initialize = True
                return 'Protected Overrides Sub UserForm_Initialize()'
            if evl == 'activate':
                return 'Protected Overrides Sub UserForm_Activate()'
            self.warn('unhandled form event ' + name)
            return None
        names = {k.lower(): k for k in self.form_ctrls}
        if ctrl.lower() not in names:
            return None
        ctrl = names[ctrl.lower()]
        evmap = {'click': 'VbClick', 'change': 'VbChange', 'enter': 'VbEnter', 'exit': 'VbExit',
                 'lostfocus': 'VbExit', 'keydown': 'VbKeyDown', 'afterupdate': 'VbExit'}
        if evl not in evmap:
            self.warn('unhandled control event ' + name)
            return None
        target = evmap[evl]
        if evl == 'keydown':
            self.pending_prologue = ['        Dim KeyCode As Integer = vbE.KeyCode', '        Dim Shift As Integer = vbE.Shift']
            return 'Private Sub %s(sender As Object, vbE As KeyDownVbEventArgs) Handles %s.%s' % (name, ctrl, target)
        if evl == 'exit':
            self.pending_prologue = ['        Dim Cancel As Boolean = False']
        return 'Private Sub %s() Handles %s.%s' % (name, ctrl, target)

    # --- file ---------------------------------------------------------------
    def translate(self, text):
        lines = text.replace('\r\n', '\n').split('\n')
        # drop attributes / Option Explicit
        lines = [l for l in lines if not re.match(r'\s*(Attribute\s+VB_|Option\s+Explicit)', l, re.I)]
        # join continuation lines
        logical = []
        buf = None
        for l in lines:
            code, com = split_comment(l)
            if buf is not None:
                buf = (buf[0] + ' ' + code.strip(), buf[1] + (' ' + com if com else ''))
            else:
                buf = (code, com)
            if re.search(r'(^|\s)_\s*$', buf[0]):
                buf = (re.sub(r'\s_\s*$', '', buf[0]), buf[1])
                continue
            logical.append(buf)
            buf = None
        if buf is not None:
            logical.append(buf)

        # drop Declare statements (replaced by VbaCompat)
        logical = [x for x in logical if not re.match(r'\s*(Public\s+|Private\s+)?Declare\s', x[0], re.I)]

        # first pass: procedure bodies (for ByRef detection)
        out = []
        i = 0
        self.pending_prologue = None
        while i < len(logical):
            code, com = logical[i]
            masked, restore = mask_strings(code)
            if re.match(r'\s*((Public|Private|Friend)\s+)?(Static\s+)?(Sub|Function)\s+\w+', masked, re.I):
                # collect body
                j = i + 1
                body = []
                while j < len(logical) and not re.match(r'\s*End\s+(Sub|Function)\b', logical[j][0], re.I):
                    body.append(mask_strings(logical[j][0])[0])
                    j += 1
                hdr = self.proc_header(masked, body)
                out.append(restore(hdr) + ((' ' + com) if com else ''))
                if self.pending_prologue:
                    out.extend(self.pending_prologue)
                    self.pending_prologue = None
                # VBA: a Dim anywhere in a procedure is visible in the whole procedure.
                # VB.NET: only inside its block. -> move every Dim/Static to the top.
                dims, rest = [], []
                for k in range(i + 1, j):
                    c2, m2 = logical[k]
                    t = self.line(c2, m2)
                    if re.match(r'\s*(Dim|Static)\s', c2, re.I):
                        dims.append('    ' + t.strip())
                    else:
                        rest.append(t)
                out.extend(dims)
                out.extend(rest)
                i = j
                continue
            out.append(self.line(code, com))
            i += 1
        return out

    def line(self, code, com):
        if code.strip() == '':
            return code + com
        masked, restore = mask_strings(code)
        lead = re.match(r'\s*', masked).group(0)
        parts = split_top(masked.strip(), ':')
        res = []
        for k, p in enumerate(parts):
            ps = p.strip()
            if k == 0 and re.match(r'^[A-Za-z_]\w*$', ps) and len(parts) > 1 and ps.lower() not in ('else', 'end', 'loop', 'next', 'wend', 'do', 'return', 'stop', 'resume') and parts[1:] and not self._is_known_call(ps):
                res.append(ps + ':')
                continue
            if re.match(r'^\d+$', ps):
                res.append(ps)
                continue
            try:
                res.append(self.statement(ps).strip())
            except Exception as e:
                self.warn('could not translate: %s (%s)' % (restore(ps), e))
                res.append(ps)
        joined = ''
        for r in res:
            if joined == '':
                joined = r
            elif joined.endswith(':') and re.match(r'^[A-Za-z_]\w*:$', joined):
                joined += ' ' + r
            elif r:
                joined += ' : ' + r
        return restore(lead + joined) + ((' ' + com) if com else '')

    def _is_known_call(self, name):
        return False


# ------------------------------------------------------------------ forms (designer)

def himetric(v):
    return int(round(v * 96.0 / 2540.0))


def ole_color(v):
    v = int(v)
    if v & 0x80000000:
        idx = v & 0xFF
        sysmap = {0x05: 'SystemColors.Window', 0x08: 'SystemColors.WindowText', 0x0F: 'SystemColors.Control',
                  0x12: 'SystemColors.ControlText', 0x04: 'SystemColors.Menu', 0x0D: 'SystemColors.Highlight',
                  0x0E: 'SystemColors.HighlightText', 0x11: 'SystemColors.GrayText', 0x10: 'SystemColors.ControlDark'}
        return sysmap.get(idx, 'SystemColors.Control')
    r, g, b = v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF
    return 'Color.FromArgb(%d, %d, %d)' % (r, g, b)


def vbstr(s):
    s = s.replace('"', '""').replace('\r\n', '\n').replace('\r', '\n')
    parts = s.split('\n')
    return ' & vbCrLf & '.join('"%s"' % p for p in parts)


def designer(fname, f, resources):
    frame = f['vbframe']
    cap = re.search(r'Caption\s*=\s*"(.*)"', frame).group(1)
    cw = int(re.search(r'ClientWidth\s*=\s*(\d+)', frame).group(1)) // 15
    ch = int(re.search(r'ClientHeight\s*=\s*(\d+)', frame).group(1)) // 15
    decls = []
    body = []
    font_default = (f['props'].get('font') or '맑은 고딕', f['props'].get('size_twips', 180) / 20.0)

    def emit(c, parent):
        t = c['type']
        cls = WRAP.get(t)
        if not cls:
            body.append("        ' (생략된 컨트롤 %s: %s)" % (c['name'], t))
            return
        n = c['name']
        decls.append('    Friend WithEvents %s As %s' % (n, cls))
        b = body
        b.append('        Me.%s = New %s()' % (n, cls))
        x, y = himetric(c['x']), himetric(c['y'])
        w, h = himetric(c.get('w', 2000)), himetric(c.get('h', 600))
        b.append('        Me.%s.Name = "%s"' % (n, n))
        b.append('        Me.%s.Location = New Point(%d, %d)' % (n, x, y))
        if t in ('TextBox',):
            b.append('        Me.%s.AutoSize = False' % n)
        if t == 'ComboBox':
            b.append('        Me.%s.DropDownStyle = ComboBoxStyle.%s' % (n, 'DropDownList' if c.get('displaystyle') == 7 else 'DropDown'))
            b.append('        Me.%s.IntegralHeight = False' % n)
            b.append('        Me.%s.MaxDropDownItems = 12' % n)
        b.append('        Me.%s.Size = New Size(%d, %d)' % (n, w, h))
        if c['tab'] >= 0:
            b.append('        Me.%s.TabIndex = %d' % (n, c['tab']))
        if not c.get('tabstop', True) and t not in ('Label', 'Frame', 'Image'):
            b.append('        Me.%s.TabStop = False' % n)
        if not c.get('visible', True):
            b.append('        Me.%s.Visible = False' % n)
        if c.get('enabled') is False:
            b.append('        Me.%s.Enabled = False' % n)
        if c.get('locked'):
            b.append('        Me.%s.Locked = True' % n)
        font = c.get('font') or font_default[0]
        size = (c.get('size_twips') or font_default[1] * 20) / 20.0
        if (font, size) != font_default or c.get('bold'):
            b.append('        Me.%s.Font = New Font("%s", %sF%s)' % (n, font, ('%g' % size), ', FontStyle.Bold' if c.get('bold') else ''))
        if 'backcolor' in c and t not in ('CommandButton',) and int(c['backcolor']) not in (0x80000005, 0x8000000F):
            b.append('        Me.%s.BackColor = %s' % (n, ole_color(c['backcolor'])))
        if 'forecolor' in c and int(c['forecolor']) not in (0x80000008, 0x80000012):
            b.append('        Me.%s.ForeColor = %s' % (n, ole_color(c['forecolor'])))
        align = c.get('align', 1)
        if t == 'TextBox':
            if c.get('multiline'):
                b.append('        Me.%s.Multiline = True' % n)
            if align == 3:
                b.append('        Me.%s.TextAlign = HorizontalAlignment.Center' % n)
            elif align == 2:
                b.append('        Me.%s.TextAlign = HorizontalAlignment.Right' % n)
            if c.get('value'):
                b.append('        Me.%s.Text = %s' % (n, vbstr(c['value'])))
        elif t == 'ComboBox':
            if c.get('value'):
                b.append('        Me.%s.Text = %s' % (n, vbstr(c['value'])))
        elif t in ('OptionButton', 'CheckBox', 'ToggleButton'):
            b.append('        Me.%s.Text = %s' % (n, vbstr(c.get('caption', ''))))
            if c.get('value') == '1':
                b.append('        Me.%s.Checked = True' % n)
        elif t == 'Label':
            b.append('        Me.%s.Text = %s' % (n, vbstr(c.get('caption', ''))))
            b.append('        Me.%s.UseMnemonic = False' % n)
            if align == 3:
                b.append('        Me.%s.TextAlign = ContentAlignment.TopCenter' % n)
            elif align == 2:
                b.append('        Me.%s.TextAlign = ContentAlignment.TopRight' % n)
            if c.get('borderstyle') == 1:
                b.append('        Me.%s.BorderStyle = BorderStyle.FixedSingle' % n)
            elif c.get('specialeffect') in (2, 3):
                b.append('        Me.%s.BorderStyle = BorderStyle.Fixed3D' % n)
        elif t == 'CommandButton':
            b.append('        Me.%s.Text = %s' % (n, vbstr(c.get('caption', ''))))
            b.append('        Me.%s.UseMnemonic = False' % n)
            b.append('        Me.%s.UseVisualStyleBackColor = True' % n)
        elif t == 'Frame':
            b.append('        Me.%s.Text = %s' % (n, vbstr(c.get('caption', ''))))
        elif t == 'Image':
            b.append('        Me.%s.SizeMode = PictureBoxSizeMode.%s' % (n, {0: 'Normal', 1: 'StretchImage', 3: 'Zoom'}.get(c.get('sizemode', 0), 'Normal') if c.get('sizemode', 0) != 0 else 'CenterImage'))
            if c.get('borderstyle', 1) == 1 or c.get('specialeffect'):
                b.append('        Me.%s.BorderStyle = BorderStyle.%s' % (n, 'Fixed3D' if c.get('specialeffect') else 'FixedSingle'))
            if c.get('picture_file'):
                res = '%s_%s' % (fname, n)
                resources.append((res, c['picture_file']))
                b.append('        Me.%s.Image = LoadResourceImage("%s")' % (n, res))
        b.append('        %s.Controls.Add(Me.%s)' % (parent, n))
        if t == 'Frame':
            for ch_ in sorted(c['children'], key=lambda z: z['tab']):
                emit(ch_, 'Me.' + n)

    for c in sorted(f['controls'], key=lambda z: z['tab']):
        emit(c, 'Me')

    out = ['\' 이 파일은 tools/vba2vb.py 가 원본 .dvb 의 폼 배치에서 만든다. 직접 고치지 말 것.',
           'Imports System.Drawing', 'Imports System.Windows.Forms', '',
           'Partial Class %s' % fname, '    Inherits MForm', '']
    out += decls
    out += ['', '    Private Sub InitializeComponent()', '        Me.SuspendLayout()',
            '        Me.AutoScaleMode = AutoScaleMode.Dpi', '        Me.AutoScaleDimensions = New SizeF(96.0F, 96.0F)',
            '        Me.Font = New Font("%s", %gF)' % font_default,
            '        Me.ClientSize = New Size(%d, %d)' % (cw, ch),
            '        Me.Text = %s' % vbstr(cap), '        Me.Name = "%s"' % fname]
    out += body
    out += ['        Me.ResumeLayout(False)', '        Me.PerformLayout()', '    End Sub', 'End Class', '']
    return out


# ------------------------------------------------------------------ main

def main():
    for d in (OUT, OUT_FORMS):
        os.makedirs(d, exist_ok=True)
        for fn in os.listdir(d):
            if fn.endswith('.vb'):
                os.remove(os.path.join(d, fn))
    os.makedirs(OUT_RES, exist_ok=True)
    warnings = []
    resources = []
    for fn in sorted(os.listdir(SRC_VBA)):
        if fn.endswith('.bas'):
            for line in open(os.path.join(SRC_VBA, fn), encoding='utf-8'):
                m = re.match(r'\s*(Public|Global)\s+(\w+)\s+As\s+New\s+([\w.]+)', line, re.I)
                if m:
                    GLOBAL_NEW_VARS[m.group(2).lower()] = map_type(m.group(3))
    byref = {}
    for fn in sorted(os.listdir(SRC_VBA)):
        name, ext = os.path.splitext(fn)
        if name in SKIP_MODULES:
            continue
        kind = ext[1:]
        text = open(os.path.join(SRC_VBA, fn), encoding='utf-8').read()
        tr = Translator(name, kind, FORM_CONTROLS.get(name))
        body = tr.translate(text)
        hdr = ["' 원본: %s (Turbo_Fan_Design.dvb) — tools/vba2vb.py 로 옮긴 코드." % fn,
               "' 원본 VBA 와 줄 단위로 비교할 수 있도록 문장을 최대한 그대로 두었다.",
               'Option Strict Off', 'Option Explicit On', '']
        body = [('    ' + l) if l.strip() else '' for l in body]
        if kind == 'bas':
            code = hdr + ['Public Module %s' % name] + body + ['End Module', '']
        elif kind == 'cls':
            code = hdr + ['Public Class %s' % name] + body + ['End Class', '']
        else:
            ctor = ['', '    Public Sub New()', '        InitializeComponent()', '        EndInitialize()', '    End Sub', '']
            code = hdr + ['Partial Class %s' % name] + ctor + body + ['End Class', '']
            dz = designer(name, FORMS[name], resources)
            open(os.path.join(OUT_FORMS, name + '.Designer.vb'), 'w', encoding='utf-8').write('\n'.join(dz))
        open(os.path.join(OUT, name + '.vb'), 'w', encoding='utf-8').write('\n'.join(code))
        warnings += tr.warnings
        for k, v in tr.byref_params.items():
            byref['%s.%s' % (name, k)] = sorted(v)
    for res, picfile in resources:
        shutil.copy(os.path.join(HERE, 'form_pictures', picfile), os.path.join(OUT_RES, res + os.path.splitext(picfile)[1]))
    for w in warnings:
        print('warning:', w)
    print('procedures that assign to their (ByRef) parameters:')
    for k, v in sorted(byref.items()):
        print('   ', k, v)


if __name__ == '__main__':
    main()
