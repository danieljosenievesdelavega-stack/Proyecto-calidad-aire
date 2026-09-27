@echo off
@echo off
cd /d "%~dp0"
call "%~dp0.venv\Scripts\activate.bat"
python "%~dp0src\orquestacion\pipeline.py"