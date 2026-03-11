@echo off
set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
pushd %PROJECT_ROOT%
python start.py --suite e2e %*
popd