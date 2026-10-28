"""Build frontend/Lang/ru.json from en.json + MT cache + manual short-string translations."""
import json, re, glob, os

HERE = os.path.dirname(os.path.abspath(__file__))
EN = os.path.join(HERE, '..', 'frontend', 'Lang', 'en.json')
OUT = os.path.join(HERE, '..', 'frontend', 'Lang', 'ru.json')
os.chdir(HERE)

en = json.load(open(EN, encoding='utf-8'))
mt = json.load(open('ru_cache.json', encoding='utf-8'))
short = [l.rstrip('\n').split('\t')[0] for l in open('short.tsv', encoding='utf-8')]
manual = {}
for f in sorted(glob.glob('ru_short_*.txt')):
    for line in open(f, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line:
            continue
        n, ru = line.split('|', 1)
        manual[short[int(n) - 1]] = ru
short_set = set(short)
manual.update(json.load(open('ru_fix.json', encoding='utf-8')))

PH = re.compile(r'\{([A-Za-z0-9_]+)\}')
TAG = re.compile(r'</?[a-zA-Z][^>]*>')
stats = {'manual': 0, 'kept': 0, 'mt': 0, 'fallback': 0}
bad = []


def fix_spacing(src, out):
    # MT puts spaces inside inline tags: "<b> текст </b>" -> "<b>текст</b>"
    for t in ('b', 'strong', 'i', 'em', 'code', 'kbd', 'span'):
        if not re.search(rf'<{t}[^>]*>\s', src):
            out = re.sub(rf'(<{t}(?:\s[^>]*)?>)\s+', r'\1', out)
        if not re.search(rf'\s</{t}>', src):
            out = re.sub(rf'\s+(</{t}>)', r'\1', out)
    return out


def tr(s, key):
    if s in manual:
        stats['manual'] += 1
        out = manual[s]
    elif s in short_set or not re.search(r'[A-Za-z]{2,}', s):
        stats['kept'] += 1
        return s
    elif s in mt:
        stats['mt'] += 1
        out = fix_spacing(s, mt[s])
    else:
        stats['fallback'] += 1
        return s
    if sorted(set(PH.findall(out))) != sorted(set(PH.findall(s))) or \
            sorted(TAG.findall(out)) != sorted(TAG.findall(s)):
        bad.append((key, s, out))
        stats['fallback'] += 1
        return s
    return out


def walk(v, key):
    if isinstance(v, str):
        return tr(v, key)
    if isinstance(v, list):
        return [walk(x, key) for x in v]
    return {k: walk(x, k) for k, x in v.items()}


ru = {}
for k, v in en.items():
    if k.startswith('__'):
        ru[k] = v  # section markers, not shown in the UI
    elif k == '_info':
        ru[k] = {'name': 'Русский', 'flag': 'ru', 'suffix': '_RU'}
    else:
        ru[k] = walk(v, k)

with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write(json.dumps(ru, ensure_ascii=False, indent=2) + '\n')
print(stats, 'bad:', len(bad))
