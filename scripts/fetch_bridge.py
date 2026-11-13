"""Fetch pinned official OpenRGB files without running them or touching devices."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(url, expected, target):
    if target.exists() and digest(target) == expected:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': 'PrismKeyboardStudio/2.5'})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            with urllib.request.urlopen(request, timeout=60) as response:
                shutil.copyfileobj(response, stream)
        if digest(temporary) != expected:
            raise ValueError(f'Checksum mismatch for {target.name}')
        temporary.replace(target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return target


def main():
    provenance = json.loads((ROOT/'docs/bridge-provenance.json').read_text(encoding='utf-8'))
    manifest = json.loads((ROOT/'src/bridge-manifest.json').read_text(encoding='utf-8'))
    destination = ROOT/'bridge'
    if any(destination.rglob('*.bin')):
        raise ValueError('Remove unexpected .bin files from bridge before rebuilding.')
    current = all((destination/name).is_file() and digest(destination/name) == expected
                  for name, expected in manifest.items())
    if not current:
        archive = download(provenance['asset'], provenance['sha256']['official_portable_archive'],
                           ROOT/'.cache/OpenRGB-1.1-Windows.zip')
        with zipfile.ZipFile(archive) as zipped:
            files = {}
            for name, expected in manifest.items():
                relative = PurePosixPath(name)
                if relative.is_absolute() or '..' in relative.parts or relative.suffix.lower() == '.bin':
                    raise ValueError(f'Unsafe bridge manifest entry: {name}')
                matches = [entry for entry in zipped.namelist()
                           if entry == name or entry.endswith('/'+name)]
                if len(matches) != 1:
                    raise ValueError(f'Expected one archive entry for {name}')
                data = zipped.read(matches[0])
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError(f'Checksum mismatch for {name}')
                files[name] = data
        for name, data in files.items():
            target = destination/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    source = download(provenance['source'], provenance['sha256']['corresponding_source'],
                      ROOT/'src/OpenRGB-1.1-corresponding-source.zip')
    print(f'Verified {len(manifest)} bridge files and {source.name}. No device access.')


if __name__ == '__main__':
    main()
