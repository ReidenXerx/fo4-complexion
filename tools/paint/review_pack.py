"""Approval sheets for the whole pack, in numbered batches of ten, for a reviewer going through it item by item
(alasdairn, 2026-10-09: "send images of the rest ... I want to see if we can truly perfect the whole pack").

    python tools/paint/review_pack.py <out dir> <worker k> <workers N> [--skip base,base,...]

Bases go in template order (data/tags/complexion.json); batch b goes to worker b % N, so the first batches finish
first. Each batch is <out>/batchNN/ with one sheet per base and a list.txt: "sheet -- what it is".
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def bases(skip):
    tags = json.loads((ROOT / 'data' / 'tags' / 'complexion.json').read_text(encoding='utf-8'))
    seen, out = set(), []
    for key, tag in tags.items():
        base = re.sub(r'_[FM]\d+$', '', key.split(':', 1)[1])
        if base in seen or base in skip:
            continue
        seen.add(base)
        out.append((base, tag.get('note', '')))
    return out


def main():
    out, k, n = pathlib.Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    skip = set()
    if '--skip' in sys.argv:
        skip = set(sys.argv[sys.argv.index('--skip') + 1].split(','))
    todo = bases(skip)
    for b in range(k, (len(todo) + 9) // 10, n):
        chunk = todo[b * 10:(b + 1) * 10]
        d = out / f'batch{b + 1:02d}'
        if (d / 'list.txt').exists():
            continue  # done in an earlier run
        subprocess.run([sys.executable, str(HERE / 'approval.py'), str(d)] + [base for base, _ in chunk])
        if not all((d / f'{base}.jpg').exists() for base, _ in chunk):
            print(d, 'INCOMPLETE', flush=True)   # no list.txt: the auto-poster never posts half a batch
            continue
        (d / 'list.txt').write_text(''.join(f'{base}.jpg -- {note}\n' for base, note in chunk), encoding='utf-8')
        print(d, flush=True)


if __name__ == '__main__':
    main()
