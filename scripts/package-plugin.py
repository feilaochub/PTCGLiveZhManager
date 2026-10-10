"""Build separate platform base packages and a shared translation package."""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOADERS = {
    'windows': ('BepInEx_win_x64_5.4.23.5.zip', '82f9878551030f54657792c0740d9d51a09500eeae1fba21106b0c441e6732c4'),
    'osx': ('BepInEx_macos_universal_5.4.23.5.zip', '01c2ae782eb016dfd6c345a18dbd2dcafffb3d9d318449d6486689f426b4a323'),
}
sha = lambda data: hashlib.sha256(data).hexdigest()
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--component', choices=['translation', 'base'], default='translation')
p.add_argument('--platform', choices=['osx', 'windows'])
p.add_argument('--dll', type=Path)
p.add_argument('--loader', type=Path)
p.add_argument('--loader-license', type=Path)
p.add_argument('--output-dir', type=Path, default=ROOT / 'work' / 'releases')
a = p.parse_args()
release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
assert type(release['translation_revision']) is int and release['translation_revision'] >= 0, 'Revision must be a nonnegative integer (r0 is valid).'
version = release['game_version']
project = (ROOT / 'mod/PTCGLiveZhMod.csproj').read_text(encoding='utf-8')
assert re.search(r'<FileVersion>([^<]+)</FileVersion>', project)[1] == version
assert re.search(r'<AssemblyVersion>([^<]+)</AssemblyVersion>', project)[1] == version
assert f'"{version}")]' in (ROOT / 'mod/Plugin.cs').read_text(encoding='utf-8')
assert json.loads((ROOT / 'manager/package.json').read_text(encoding='utf-8'))['version'] == version
files = {}
executable = set()
manifest = {
    'component': a.component,
    'game_version': version,
    'base_version': release['base_version'],
    'required_base_version': release['required_base_version'],
    'translation_revision': release['translation_revision'],
    'runtime_verified_on_macos': False,
    'runtime_verified_for_this_release': False,
    'status': 'release; macOS base is experimental',
}
if a.component == 'translation':
    if a.platform or not a.dll or not a.dll.is_file():
        p.error('Translation package is shared: supply --dll, without --platform.')
    files['PTCGLiveZhMod/PTCGLiveZhMod.dll'] = a.dll.read_bytes()
    build_path = Path(str(a.dll) + '.build.json')
    record = None
    if build_path.is_file():
        record = json.loads(build_path.read_text(encoding='utf-8-sig'))
        assert record['version'] == version, 'Build version mismatch'
        assert record['dll_sha256'] == sha(a.dll.read_bytes()), 'DLL changed after build'
        sources = {x.relative_to(ROOT).as_posix(): sha(x.read_bytes()) for x in (ROOT / 'mod').rglob('*') if x.is_file() and x.suffix in ['.cs', '.csproj'] and not any(v in ['bin', 'obj'] for v in x.relative_to(ROOT / 'mod').parts)}
        assert sources == record['sources_sha256'], 'Sources changed after build'
        files['build-record.json'] = build_path.read_bytes()
    counts = {}
    for source, target in [('databases_zh-CN', 'databases'), ('text_zh-CN', 'text')]:
        for path in sorted((ROOT / source).glob('*.json')):
            records = json.loads(path.read_text(encoding='utf-8-sig'))
            records = {k: v.rstrip() for k, v in records.items() if v.strip()}
            content = ''.join(f'|{k}:{v}\n' for k, v in records.items()) + '|\n'
            parsed = {m[1]: m[2].strip() for m in re.finditer(r'^\|([^:\n]+):(.*?)(?=^\||\Z)', content, re.M | re.S)}
            assert parsed == {k: v.strip() for k, v in records.items()}, path
            name = f'PTCGLiveZhMod/{target}/{path.stem}.txt'
            files[name] = content.encode('utf-8')
            counts[name] = len(records)
    files['PTCGLiveZhMod/translation-version.json'] = (json.dumps(release, indent=2) + '\n').encode()
    # Fonts and loaders belong only to the base packages. Private notes are never included.
    for directory in ['mod', 'scripts', 'docs', 'licenses', 'databases', 'databases_untranslated', 'databases_zh-CN', 'text_untranslated', 'text_zh-CN']:
        for path in sorted((ROOT / directory).rglob('*')):
            if not path.is_file() or any(v in ['bin', 'obj', '__pycache__'] for v in path.relative_to(ROOT / directory).parts):
                continue
            if directory == 'mod' and path.suffix not in ['.cs', '.csproj']:
                continue
            if directory == 'scripts' and path.suffix not in ['.py', '.ps1', '.js']:
                continue
            files['SOURCE/' + path.relative_to(ROOT).as_posix()] = path.read_bytes()
    for name in ['LICENSE', 'README.md', 'dictionary.json', 'THIRD_PARTY_NOTICES.md', 'release.json']:
        files['SOURCE/' + name] = (ROOT / name).read_bytes()
    manifest.update(platform='shared', loader_included=False, fonts_included=False,
                    source_correspondence_verified=record is not None, translation_record_counts=counts)
    filename = f'PTCGLiveZhManager-{version}-r{release["translation_revision"]}.zip'
else:
    if not a.platform or not a.loader or not a.loader_license or a.dll:
        p.error('Base package requires --platform, --loader and --loader-license; no --dll.')
    loader_name, expected = LOADERS[a.platform]
    assert sha(a.loader.read_bytes()) == expected, 'Loader differs from the pinned upstream release'
    license_data = a.loader_license.read_bytes()
    assert b'MIT License' in license_data and b'Copyright (c) 2018 Bepis' in license_data
    with zipfile.ZipFile(a.loader) as z:
        assert z.testzip() is None
        for entry in z.infolist():
            path = PurePosixPath(entry.filename)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in entry.filename
            if not entry.is_dir():
                files[entry.filename] = z.read(entry)
                if entry.filename.endswith('.sh'):
                    executable.add(entry.filename)
    files['BepInEx/plugins/PTCGLiveZhMod/fonts/TextMeshPro_font'] = (ROOT / f'fonts/TextMeshPro_font.{a.platform}').read_bytes()
    files['licenses/BepInEx-LICENSE.txt'] = license_data
    files['licenses/MiSans-License.pdf'] = (ROOT / 'licenses/MiSans-License.pdf').read_bytes()
    files['licenses/Project-LICENSE.txt'] = (ROOT / 'LICENSE').read_bytes()
    files['THIRD_PARTY_NOTICES.md'] = (ROOT / 'THIRD_PARTY_NOTICES.md').read_bytes()
    files['README.md'] = (ROOT / 'README.md').read_bytes()
    files['SOURCE/release.json'] = (ROOT / 'release.json').read_bytes()
    files['SOURCE/scripts/package-plugin.py'] = Path(__file__).read_bytes()
    if a.platform == 'osx':
        # Standard upstream Doorstop launch route. Does not copy or patch game assemblies.
        files['Start-PTCGL.command'] = b'''#!/bin/sh
set -eu
cd "$(dirname "$0")"
game_app=$(osascript -e 'POSIX path of (choose file with prompt "Select Pokemon TCG Live.app" of type {"com.apple.application-bundle"})')
if [ ! -f "$game_app/Contents/Info.plist" ]; then
    echo "Please select the game .app." >&2
    exit 1
fi
exec /bin/sh ./run_bepinex.sh "$game_app"
'''
        executable.add('Start-PTCGL.command')
    manifest.update(platform=a.platform, loader_included=True, fonts_included=True,
                    loader_version='5.4.23.5', loader_sha256=expected,
                    loader_source=f'https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.5/{loader_name}',
                    macos_loader_route='upstream-doorstop; experimental, differs from original hardpatch manager' if a.platform == 'osx' else None)
    filename = f'PTCGLiveZhManager-base-{a.platform}-b{release["base_version"]}' + ('-experimental' if a.platform == 'osx' else '') + '.zip'
files['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
manifest['sha256'] = {name: sha(data) for name, data in files.items()}
files['manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
a.output_dir.mkdir(parents=True, exist_ok=True)
output = a.output_dir / filename
if output.exists():
    p.error(f'Refusing to overwrite {output}; use another output directory for unpublished builds, or increment the revision/base version for a published update.')
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for name, data in sorted(files.items()):
        info = zipfile.ZipInfo(name, date_time=(2026, 10, 9, 0, 0, 0))
        info.create_system = 3
        info.external_attr = (0o100755 if name in executable else 0o100644) << 16
        z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
with zipfile.ZipFile(output) as z:
    assert z.testzip() is None
    for name, data in files.items():
        assert z.read(name) == data, name
checksum = sha(output.read_bytes())
output.with_suffix('.zip.sha256').write_text(f'{checksum}  {output.name}\n', encoding='utf-8')
print('Packaged and verified:', output)
print('Bytes:', output.stat().st_size, 'SHA256:', checksum)
