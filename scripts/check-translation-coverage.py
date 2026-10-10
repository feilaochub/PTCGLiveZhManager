"""Check every known English source key against Chinese JSON or a packaged ZIP.

This measures known source-table coverage, not live-client or card-art coverage.
Exits 1 when translations are missing or conflicting.
"""
import argparse
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# CardActionDataRow.Name and RichTextName strip square-bracket contents.
# These exact whole-field labels therefore have no visible name. Preserve the
# engine metadata and report it separately instead of counting it as Chinese.
NON_DISPLAY_ATTACK_LABELS = frozenset({
    '[BREAK Evolution rule]', '[Primal Reversion Rule]',
    '[α Recovery]', '[Ω Barrage]', '[α Growth]', '[Ω Barrier]',
    '[Δ Evolution]', '[Δ Plus]', '[Δ Wild]',
    '[Θ Double]', '[Θ Stop]', '[Θ Max]',
})


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key in {path}: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def check(package=None):
    translated = {'text': {}, 'databases': {}}
    conflicts = []
    def merge(group, entries, origin):
        # UI files share one localization dictionary. Card names, attack names,
        # and attack effects are separate dictionaries even for identical hashes.
        destination = translated[group] if group == 'text' else translated[group].setdefault(Path(origin).stem, {})
        for key, value in entries.items():
            if not isinstance(value, str):
                raise ValueError(f'Non-string translation: {origin}/{key}')
            if not value.strip():
                continue
            previous = destination.get(key)
            if previous is not None and previous != value.strip():
                conflicts.append({'group': group, 'key': key, 'origin': origin})
            destination[key] = value.strip()
    if package:
        with zipfile.ZipFile(package) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError(f'ZIP CRC error: {bad}')
            for group in translated:
                prefix = f'PTCGLiveZhMod/{group}/'
                for name in archive.namelist():
                    if name.startswith(prefix) and name.endswith('.txt'):
                        content = archive.read(name).decode('utf-8-sig')
                        pairs = re.findall(r'^\|([^:\n]+):(.*?)(?=^\||\Z)', content, re.M | re.S)
                        if len(dict(pairs)) != len(pairs):
                            raise ValueError(f'Duplicate TXT key: {name}')
                        merge(group, dict(pairs), name)
    else:
        for group in translated:
            for path in sorted((ROOT / f'{group}_zh-CN').glob('*.json')):
                merge(group, load_json(path), path.relative_to(ROOT).as_posix())
    files = {}
    total = missing = 0
    metadata_count = metadata_preserved = metadata_missing = 0
    for group in translated:
        for path in sorted((ROOT / f'{group}_untranslated').glob('*.json')):
            source = load_json(path)
            destination = translated[group] if group == 'text' else translated[group].get(path.stem, {})
            gaps = [{'key': key, 'english': value} for key, value in source.items()
                    if not destination.get(key, '').strip()]
            if group == 'databases' and path.stem == 'attks-name':
                markers = {key: value for key, value in source.items()
                           if value in NON_DISPLAY_ATTACK_LABELS}
                metadata_count += len(markers)
                metadata_preserved += sum(destination.get(key) == value for key, value in markers.items())
                metadata_missing += sum(not destination.get(key, '').strip() for key in markers)
                for key, value in markers.items():
                    if destination.get(key) and destination[key] != value:
                        conflicts.append({'group': group, 'key': key,
                                          'origin': path.relative_to(ROOT).as_posix(),
                                          'reason': 'non-display engine metadata changed'})
            count = len(source)
            total += count
            missing += len(gaps)
            files[path.relative_to(ROOT).as_posix()] = {
                'source_count': count, 'covered_count': count - len(gaps),
                'missing_count': len(gaps), 'missing': gaps,
            }
    return {'scope': 'known English source keys; excludes card art and undiscovered runtime text',
            'input': str(package) if package else 'current Chinese source JSON',
            'source_count': total, 'covered_count': total - missing, 'missing_count': missing,
            'coverage_percent': round(100 * (total - missing) / total, 4) if total else 100,
            'non_display_metadata_source_count': metadata_count,
            'preserved_non_display_metadata_count': metadata_preserved,
            'display_source_count': total - metadata_count,
            'covered_display_source_count': total - metadata_count - missing + metadata_missing,
            'display_coverage_percent': round(100 * (total - metadata_count - missing + metadata_missing)
                                              / (total - metadata_count), 4) if total != metadata_count else 100,
            'conflicts': conflicts, 'files': files}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip', type=Path, help='Read runtime TXT from a translation package')
    parser.add_argument('--output', type=Path, help='Write full coverage and missing-key report')
    args = parser.parse_args()
    report = check(args.zip)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report['missing_count'] or report['conflicts'] else 0)
