"""Machine-translate BMM en.json -> ru cache (Argos model via ctranslate2, batched). Usage: mt.py en.json cache.json"""
import json, re, sys, os, glob, time
import ctranslate2, sentencepiece as spm

PROTECT = re.compile(
    r'\{\{[^{}]*\}\}|\{[^{}]*\}|\$\{[^}]*\}|<[^>]+>|`[^`]*`|&#?\w+;|%[sdn]|https?://\S+'
    r'|\bBetter ?Mods? ?Manager\b|\bBetterCommunity\b|\bBetterInstaller\b|\bBMMScript\b|\bBMMS?\b|\bLaya\b|\bB\.MD\b|\bMCP\b|\bGitHub\b|\bDCS\b'
    r'|\[\d+\]')
TOK = re.compile(r'\[(\d+)\]')
SENT = re.compile(r'(?<=[.!?:])\s+(?=[A-Z\[(«"])')

d = glob.glob(os.path.expanduser('~/.local/share/argos-translate/packages/*/'))[0]
sp = spm.SentencePieceProcessor(model_file=d + 'sentencepiece.model')
model = ctranslate2.Translator(d + 'model', device='cpu', inter_threads=1, intra_threads=4)


def mt(units):
    """Translate unique units in one batched pass; returns dict unit -> ru."""
    uniq = sorted(set(units), key=len)
    out = {}
    for i in range(0, len(uniq), 256):
        chunk = uniq[i:i + 256]
        res = model.translate_batch([sp.encode(u, out_type=str) for u in chunk], beam_size=4,
                                    max_batch_size=64, max_decoding_length=512)
        for u, r in zip(chunk, res):
            out[u] = sp.decode(r.hypotheses[0])
        print(f'  {min(i + 256, len(uniq))}/{len(uniq)}', flush=True)
    return out


def has_letters(s):
    return re.search(r'[A-Za-z]{2,}', s) is not None


def plan(s):
    """Split a string into a template of fixed pieces and translatable units (masked)."""
    pieces = []  # list of (kind, value, spans) ; kind 'f' fixed or 'u' unit
    for li, line in enumerate(s.split('\n')):
        if li:
            pieces.append(('f', '\n', None))
        spans = []

        def keep(m):
            spans.append(m.group(0))
            return f'[{len(spans) - 1}]'
        masked = PROTECT.sub(keep, line)
        for si, sent in enumerate(SENT.split(masked)):
            if si:
                pieces.append(('f', ' ', None))
            m = re.match(r'^(\s*)(.*?)(\s*)$', sent, re.S)
            lead, core, trail = m.groups()
            pieces.append(('f', lead, None))
            if has_letters(TOK.sub('', core)):
                pieces.append(('u', core, spans))
            else:
                pieces.append(('f', TOK.sub(lambda t: spans[int(t.group(1))], core), None))
            pieces.append(('f', trail, None))
    return pieces


def ok(src, dst):
    return sorted(TOK.findall(src)) == sorted(TOK.findall(dst))


def strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from strings(x)


if __name__ == '__main__':
    src, cache_path = sys.argv[1], sys.argv[2]
    en = json.load(open(src, encoding='utf-8'))
    cache = json.load(open(cache_path, encoding='utf-8')) if os.path.exists(cache_path) else {}
    todo = sorted({s for s in strings(en) if s not in cache})
    print(f'{len(todo)} strings to translate', flush=True)
    plans = {s: plan(s) for s in todo}
    units = [p[1] for pl in plans.values() for p in pl if p[0] == 'u']
    t0 = time.time()
    tr = mt(units)
    # Units whose placeholders got mangled: translate the text between placeholders separately
    bad = [u for u in tr if not ok(u, tr[u])]
    print(f'{len(bad)} units need placeholder-safe retry', flush=True)
    sub_units = [p.strip() for u in bad for p in re.split(r'\[\d+\]', u) if has_letters(p)]
    tr2 = mt(sub_units)
    for u in bad:
        tr[u] = ''.join(p if TOK.fullmatch(p) or not has_letters(p) else
                        re.match(r'^\s*', p).group(0) + tr2[p.strip()] + re.search(r'\s*$', p).group(0)
                        for p in re.split(r'(\[\d+\])', u))
    for s, pl in plans.items():
        cache[s] = ''.join(v if k == 'f' else TOK.sub(lambda t: spans[int(t.group(1))], tr[v])
                           for k, v, spans in pl)
    json.dump(cache, open(cache_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'done in {time.time() - t0:.0f}s', flush=True)
