@echo off
pushd %~dp0
cd ..
cd ..
c:\python27\python w32service.py install
if errorlevel 5 echo You need to run this file as an administrator. Right click and click Run As Administrator.
popd
pause