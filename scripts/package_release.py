"""Assemble a portable build with source, notices, bridge and a checksum."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--application-dir', type=Path, default=ROOT/'dist/Prism Keyboard Studio')
    args = parser.parse_args()
    application = args.application_dir.resolve()
    if not (application/'Prism Keyboard Studio.exe').is_file() or not (application/'_internal').is_dir():
        raise ValueError('Build the app before assembling the portable release.')
    model = ast.parse((ROOT/'src/model.py').read_text(encoding='utf-8'))
    version = next(ast.literal_eval(node.value) for node in model.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'VERSION' for target in node.targets))
    manifest = json.loads((ROOT/'src/bridge-manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest.items():
        if digest(ROOT/'bridge'/name) != expected:
            raise ValueError(f'Bridge verification failed: {name}')
    if any((ROOT/'bridge').rglob('*.bin')):
        raise ValueError('Unexpected .bin files in bridge.')
    source_archive = ROOT/'src/OpenRGB-1.1-corresponding-source.zip'
    expected_source = json.loads((ROOT/'docs/bridge-provenance.json').read_text(encoding='utf-8'))['sha256']['corresponding_source']
    if digest(source_archive) != expected_source:
        raise ValueError('Corresponding OpenRGB source is missing or changed.')
    output = ROOT/'release'; output.mkdir(exist_ok=True)
    name = f'Prism-Keyboard-Studio-{version}-Windows-x64'
    archive = output/(name+'.zip')
    with tempfile.TemporaryDirectory(prefix='prism-package-', dir=output) as directory:
        package = Path(directory)/'Prism Keyboard Studio'
        package.mkdir()
        shutil.copy2(application/'Prism Keyboard Studio.exe', package/'Prism Keyboard Studio.exe')
        shutil.copytree(application/'_internal', package/'_internal')
        shutil.copytree(ROOT/'bridge', package/'bridge')
        shutil.copytree(ROOT/'licenses', package/'licenses')
        shutil.copytree(ROOT/'src', package/'source', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        # Make the included source independently rebuildable using the repo layout.
        (package/'source/build.ps1').write_text("$ErrorActionPreference = 'Stop'\n& (Join-Path $PSScriptRoot '../build.ps1') @args\n", encoding='utf-8')
        shutil.copytree(ROOT/'scripts', package/'scripts', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copytree(ROOT/'docs', package/'docs')
        build = (ROOT/'build.ps1').read_text(encoding='utf-8').replace('src/', 'source/')
        (package/'build.ps1').write_text(build, encoding='utf-8')
        for script in (package/'scripts').glob('*.py'):
            text = script.read_text(encoding='utf-8').replace("ROOT/'src", "ROOT/'source")
            script.write_text(text, encoding='utf-8')
        for file in ('LICENSE', 'README.md', 'CHANGELOG.md', 'THIRD-PARTY-NOTICES.txt'):
            shutil.copy2(ROOT/file, package/file)
        readme = (package/'README.md').read_text(encoding='utf-8').replace('src/', 'source/')
        (package/'README.md').write_text(readme, encoding='utf-8')
        shutil.copy2(ROOT/'docs/quick-start.txt', package/'START HERE.txt')
        partial = output/(name+'.zip.partial')
        try:
            with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
                for path in sorted(package.rglob('*')):
                    if path.is_file():
                        zipped.write(path, path.relative_to(package.parent).as_posix())
            with zipfile.ZipFile(partial) as zipped:
                corrupt = zipped.testzip()
                if corrupt:
                    raise ValueError(f'ZIP integrity check failed: {corrupt}')
            partial.replace(archive)
        finally:
            if partial.exists():
                partial.unlink()
    checksum = digest(archive)
    (output/'SHA256SUMS.txt').write_text(f'{checksum}  {archive.name}\n', encoding='utf-8')
    print(json.dumps(dict(archive=str(archive), bytes=archive.stat().st_size, sha256=checksum)))


if __name__ == '__main__':
    main()
