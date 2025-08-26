@echo off
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Starting XTTS GUI...
python XTTS_GUI.py

pause
