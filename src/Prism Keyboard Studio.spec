# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

source = Path(SPECPATH)
a = Analysis([str(source / 'app.py')], pathex=[str(source)], binaries=[], datas=[(str(source / "compatibility.json"), "."), (str(source / "bridge-manifest.json"), "."), (str(source / "speed-baselines.json"), ".")],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=[], noarchive=False, optimize=0)
# Qt on Windows imports the OS's unversioned ICU API. A developer PATH can
# contain an incompatible, version-suffixed ICU (e.g. Poppler's ICU 78).
# Windows 10/11 supplies ICU and API-set forwarders; don't bundle other apps'
# similarly named DLLs. This was verified against the actual frozen executable.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in ('icuuc.dll', 'icuin.dll')
              and not Path(entry[0]).name.lower().startswith(('icudt', 'api-ms-', 'ext-ms-'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Prism Keyboard Studio',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
          console=False, disable_windowed_traceback=False,
          icon=[str(source / 'prism.ico')])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True,
               name='Prism Keyboard Studio')
