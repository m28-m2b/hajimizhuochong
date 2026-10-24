@echo off
rem Hajimi desktop pet launcher (pythonw = no console window)
setlocal
set "PYW=C:\Users\39906\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" "%PYW%" "%~dp0hajimi_pet.py" %*
endlocal
