@echo off
setlocal
cd /d "%~dp0"
python -m tingon_py.webapp --mock --host 127.0.0.1 --port 8765
