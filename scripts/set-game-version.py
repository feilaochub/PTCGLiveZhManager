"""Synchronize project versions with a verified game version, without downloading or publishing."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('version', help='Verified game version, e.g. 1.43.0')
p.add_argument('--revision', type=int, default=0)
a = p.parse_args()
if not re.fullmatch(r'\d+\.\d+\.\d+', a.version) or a.revision < 0:
    p.error('Use a three-part game version and a nonnegative revision (r0 for the initial release).')
if any(int(x) > 65534 for x in a.version.split('.')):
    p.error('Version components exceed the .NET assembly version range.')
config = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
config.update(game_version=a.version, translation_revision=a.revision)
(ROOT / 'release.json').write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
path = ROOT / 'mod/PTCGLiveZhMod.csproj'
s = path.read_text(encoding='utf-8')
for tag in ['AssemblyVersion', 'FileVersion']:
    s = re.sub(rf'<{tag}>[^<]+</{tag}>', f'<{tag}>{a.version}</{tag}>', s)
path.write_text(s, encoding='utf-8')
path = ROOT / 'mod/Plugin.cs'
s = path.read_text(encoding='utf-8')
s, count = re.subn(r'(\[BepInPlugin\("[^"]+", "[^"]+", ")[^"]+("\)\])', rf'\g<1>{a.version}\2', s)
assert count == 1
path.write_text(s, encoding='utf-8')
for name in ['package.json', 'package-lock.json']:
    path = ROOT / 'manager' / name
    data = json.loads(path.read_text(encoding='utf-8'))
    data['version'] = a.version
    if name == 'package-lock.json':
        data['packages']['']['version'] = a.version
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Synchronized game/plugin/manager version: {a.version}, translation revision: {a.revision}')
