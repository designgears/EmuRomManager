# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('images', 'images'),
        ('switch.ico', '.'),
        ('ACORN', 'ACORN'),
    ],
    hiddenimports=[
        'Crypto',
        'Crypto.Cipher',
        'Crypto.Cipher.AES',
        'Crypto.Util',
        'Crypto.Util.Counter',
        'rich',
        'rich.console',
        'rich.progress',
        'zstandard',
        'art',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['dist', 'build', 'image_cache', 'keys.txt'],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EmuRomManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='switch.ico',
)
