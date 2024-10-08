# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['audio_splitter_gui.py'],
    pathex=[],
    binaries=[('ffmpeg/ffmpeg', 'ffmpeg'), ('ffmpeg/ffprobe', 'ffmpeg')],
    datas=[],
    hiddenimports=['tkinter', 'pydub', 'numpy'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['test', 'unittest', 'email', 'html', 'http', 'xml', 'urllib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZQ SFX Audio Splitter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ZQ SFX Audio Splitter',
)
app = BUNDLE(
    coll,
    name='ZQ SFX Audio Splitter.app',
    icon=None,
    bundle_identifier=None,
)
