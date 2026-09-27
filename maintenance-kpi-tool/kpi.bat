@echo off
rem Maintenance KPI dashboard. Usage: kpi [SAP export file(s) or folder]
where python >nul 2>nul
if %errorlevel%==0 (
    python "%~dp0kpi.py" %*
) else (
    py -3 "%~dp0kpi.py" %*
)
