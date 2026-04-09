@echo off
setlocal
cd /d "%~dp0"
python -m tingon_py.webapp --host 127.0.0.1 --port 8765
