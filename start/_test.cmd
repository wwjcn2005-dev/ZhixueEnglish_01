@echo off
rem ============================================================
rem  Zhixue English - phone test environment launcher (CMD)
rem  Wrapper only: calls _test.ps1 in the same folder.
rem  ASCII-only on purpose (cmd.exe reads .cmd with the OEM code page);
rem  the Chinese "press any key" line is printed by PowerShell from
rem  Unicode code points, so it never gets garbled.
rem  No system ExecutionPolicy change, no admin, no install.
rem ============================================================
setlocal
set "EXIT_CODE=1"
set "PS1=%~dp0_test.ps1"

if not exist "%PS1%" (
    echo.
    echo [ERROR] Cannot find launcher script:
    echo         "%PS1%"
    echo         Please make sure _test.ps1 exists in the same folder.
    set "EXIT_CODE=2"
    goto :done
)

echo ============================================================
echo  Zhixue English - phone test environment
echo ============================================================
echo.

rem one-shot ExecutionPolicy Bypass (does NOT change the system policy)
powershell.exe -ExecutionPolicy Bypass -File "%PS1%"
set "EXIT_CODE=%ERRORLEVEL%"

:done
echo.
if "%EXIT_CODE%"=="0" (
    echo [DONE] Launcher finished.
) else (
    echo [WARN] Launcher returned exit code %EXIT_CODE% - see messages above.
)

rem Chinese prompt from Unicode code points (safe under any console code page)
powershell.exe -NoProfile -Command "Write-Host ([string]([char]0x6309+[char]0x4EFB+[char]0x610F+[char]0x952E+[char]0x9000+[char]0x51FA+[char]0x2026+[char]0x2026))"
pause >nul
exit /b %EXIT_CODE%