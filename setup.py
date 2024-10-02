from setuptools import setup

APP = ['audio_splitter_gui.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'packages': ['pydub'],
    'includes': ['pydub', 'numpy'],
    # 'iconfile': 'icon.icns',  # Commented out if you don't have an icon file
}

setup(
    app=APP,
    name='Audio Splitter',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
