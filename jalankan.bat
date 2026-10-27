@echo off
REM Double-click to run FleetTrack, then open http://localhost:8000
cd /d "%~dp0"
start "" http://localhost:8000
.venv\Scripts\python.exe manage.py runserver
