
Activate Virtual Environment

source venv/bin/activate 
(make sure you're in the project root directory)


Build Project:
pyinstaller --windowed --onedir --name "ZQ SFX Audio Splitter" audio_splitter_gui.py \
--add-binary "ffmpeg/ffmpeg:ffmpeg" \
--add-binary "ffmpeg/ffprobe:ffmpeg" \
--hidden-import=tkinter --hidden-import=pydub --hidden-import=numpy \
--exclude-module=test --exclude-module=unittest --exclude-module=email \
--exclude-module=html --exclude-module=http --exclude-module=xml \
--exclude-module=urllib --log-level=DEBUG

Code Formatter:
black audio_splitter_gui.py
