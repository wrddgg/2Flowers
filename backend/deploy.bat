@echo off
setlocal
powershell -ExecutionPolicy Bypass -File "%~dp0deploy.ps1"
