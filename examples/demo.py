"""Create a self-contained synthetic demo in a NEW directory outside the repo."""
import argparse
import importlib.util
import json
from pathlib import Path
import struct
import zlib

script = Path(__file__).resolve().parents[1] / 'skills/artifact-handoff/scripts/artifacts.py'
spec = importlib.util.spec_from_file_location('artifacts', script)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def chunk(kind, body):
    return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body) & 0xffffffff)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    base = Path(args.out).absolute()
    base.mkdir(parents=True, exist_ok=False)
    root = base / 'source'
    root.mkdir()
    (root / 'editable.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="240">'
        '<rect width="480" height="240" fill="#203e56"/>'
        '<rect x="120" y="60" width="240" height="120" fill="#55bca0"/></svg>', encoding='utf-8')
    rows = b''.join(b'\x00' + b''.join(bytes((85, 188, 160) if 120 <= x < 360 and 60 <= y < 180 else (32, 62, 86))
                                     for x in range(480)) for y in range(240))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 480, 240, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
    (root / '海报第二版.png').write_bytes(png)
    (root / '海报副本.png').write_bytes(png)
    source = a.register(root, 'editable.svg', 'source', note='Synthetic editable source')
    final = a.register(root, '海报第二版.png', 'export', 'final', source['id'], 'Synthetic demo final selection')
    result = a.package(root, [source['id'], final['id']], base / 'delivery', ['source', 'export'])
    print(json.dumps({'scan': a.scan(root), 'delivery': result}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
