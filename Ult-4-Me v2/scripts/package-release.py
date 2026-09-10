"""Build a public ZIP from a verified portable build and public release settings.

Local configuration, backups, logs, and unselected template experiments are never
copied. This does not change the local portable installation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    'ULT-4-ME V2.exe', 'chrome_100_percent.pak', 'chrome_200_percent.pak',
    'd3dcompiler_47.dll', 'dxcompiler.dll', 'dxil.dll', 'ffmpeg.dll',
    'icudtl.dat', 'libEGL.dll', 'libGLESv2.dll', 'LICENSE.electron.txt',
    'LICENSES.chromium.html', 'resources.pak', 'snapshot_blob.bin',
    'v8_context_snapshot.bin', 'vk_swiftshader_icd.json', 'vk_swiftshader.dll',
    'vulkan-1.dll',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'dist/win-unpacked')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    version = json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
    output = args.output or ROOT/'dist'/f'ULT-4-ME-V2-{version}.zip'
    config = json.loads((ROOT/'release-settings.json').read_text(encoding='utf-8'))
    assert config['lovense_ip'] == '' and config['onboarding_completed'] is False
    filenames = {d['filename'] for d in config['detectables'].values() if d.get('filename')}
    for det in config['detectables'].values(): filenames.update(det.get('examples', []))
    assert all(Path(name).name == name and '\\' not in name for name in filenames)
    (ROOT/'build').mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='public-release-', dir=ROOT/'build'))
    package = stage/'ULT-4-ME V2'
    package.mkdir()
    for name in RUNTIME_FILES: shutil.copy2(args.source/name, package/name)
    for name in ('locales', 'vision-worker'):
        shutil.copytree(args.source/name, package/name)
    (package/'resources').mkdir()
    shutil.copy2(args.source/'resources/app.asar', package/'resources/app.asar')
    (package/'templates').mkdir()
    for name in sorted(filenames):
        shutil.copy2(ROOT/'templates'/name, package/'templates'/name)
    shutil.copy2(ROOT/'release-settings.json', package/'config.json')
    # Fail if a modified source runtime directory introduced personal-state files.
    assert not any(p.suffix.lower() in ('.log', '.bak') for p in package.rglob('*'))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file(): archive.write(path, path.relative_to(stage))
    with zipfile.ZipFile(output) as archive: assert archive.testzip() is None
    receipt = dict(version=version, package=str(package), zip=str(output),
                   size=output.stat().st_size, sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                   templates=len(filenames))
    output.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__': main()
