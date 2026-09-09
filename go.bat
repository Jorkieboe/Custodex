@echo off
setlocal enabledelayedexpansion

:: =================================================================
:: SECTION 1: CONFIGURATION
:: =================================================================
set "PROJECT_NAME=Custodex"
set "VENV_DIR=.venv"
set "START_SCRIPT=backend.main"
set "SPEC_FILE=%PROJECT_NAME%.spec"
set "FLAG=%1"
set "ARG2=%2"

:: =================================================================
:: SECTION 2: COMMAND ROUTER
:: =================================================================
if /I "%FLAG%"=="" goto :DefaultAction
if /I "%FLAG%"=="i" goto :InstallDeps
if /I "%FLAG%"=="install" goto :InstallDeps
if /I "%FLAG%"=="cmd" goto :OpenCmd
if /I "%FLAG%"=="f" goto :FreezeReqs
if /I "%FLAG%"=="freeze" goto :FreezeReqs
if /I "%FLAG%"=="b" goto :BuildApp
if /I "%FLAG%"=="build" goto :BuildApp
if /I "%FLAG%"=="t" goto :RunTests
if /I "%FLAG%"=="test" goto :RunTests
if /I "%FLAG%"=="tests" goto :RunTests
echo Unrecognized command: "%FLAG%".
goto :Usage

:DefaultAction
    call :ActivateVenv
    if !errorlevel! neq 0 goto :eof
    echo Starting %PROJECT_NAME% backend and services...
    python -m %START_SCRIPT%
    goto :eof

:InstallDeps
    call :CheckUv
    if !errorlevel! neq 0 goto :eof
    call :ActivateVenv
    if !errorlevel! neq 0 goto :eof
    if exist requirements.txt (
        echo Installing Python dependencies with uv...
        uv pip install -r requirements.txt
    )
    if exist package.json (
        echo Installing Node dependencies with npm...
        call npm install
    )
    echo All dependencies installed successfully.
    goto :eof

:OpenCmd
    call :ActivateVenv
    if !errorlevel! neq 0 goto :eof
    echo Virtual environment activated in new command prompt.
    cmd /k
    goto :eof

:FreezeReqs
    call :CheckUv
    if !errorlevel! neq 0 goto :eof
    call :ActivateVenv
    if !errorlevel! neq 0 goto :eof
    echo Freezing dependencies to requirements.txt
    uv pip freeze > requirements.txt
    echo Done.
    goto :eof

:RunTests
    call :ActivateVenv
    if !errorlevel! neq 0 goto :eof
    echo [1/2] Running backend unit test suite with pytest...
    python -m pytest
    if !errorlevel! neq 0 (
        echo Pytest suite failed.
        exit /b 1
    )
    if exist package.json (
        echo [2/2] Running frontend unit test suite with vitest...
        call npm run test:unit
        if !errorlevel! neq 0 (
            echo Vitest suite failed.
            exit /b 1
        )
    )
    echo All test suites passed cleanly.
    goto :eof

:BuildApp
    call :ActivateVenv
    if !errorlevel! neq 0 goto :eof
    echo.
    echo ### Starting Build Process ###
    echo.

    if exist package.json (
        echo Building frontend static distribution...
        call npm run build
        if !errorlevel! neq 0 (
            echo Frontend build failed.
            goto :eof
        )
    )

    echo Deleting old build folders...
    rmdir /s /q dist 2>nul
    rmdir /s /q build 2>nul
    echo.
    echo Running PyInstaller...
    pyinstaller %SPEC_FILE%
    if !errorlevel! neq 0 (
        echo.
        echo FATAL: PyInstaller build failed.
        goto :eof
    )
    echo.
    echo Build complete. Executable is in the 'dist' folder.
    goto :eof

:CheckUv
    where uv >nul 2>nul
    if !errorlevel! neq 0 (
        echo.
        echo ############################################################
        echo # ERROR: 'uv' not found.
        echo # This project uses 'uv' for high-performance Python setup.
        echo # Please install it: https://github.com/astral-sh/uv
        echo ############################################################
        echo.
        exit /b 1
    )
    exit /b 0

:ActivateVenv
    if defined VIRTUAL_ENV exit /b 0

    if not exist "%VENV_DIR%\Scripts\activate" (
        call :CheckUv
        if !errorlevel! neq 0 exit /b 1

        echo.
        echo Virtual environment not found. Creating with uv...
        uv venv %VENV_DIR%
        if !errorlevel! neq 0 (
            echo ERROR: Failed to create venv with uv.
            exit /b 1
        )
        call %VENV_DIR%\Scripts\activate
        if exist requirements.txt (
            echo.
            echo --- Installing Application Requirements with uv ---
            uv pip install -r requirements.txt
            if !errorlevel! neq 0 exit /b 1
        )
        echo.
        echo --- Setup complete! ---
        echo.
    ) else (
        call %VENV_DIR%\Scripts\activate
    )
    exit /b 0

:Usage
    echo.
    echo Commands:
    echo   (no flag)      - Runs the main application script
    echo   i, install     - Installs backend and frontend dependencies
    echo   cmd            - Opens a command prompt with the venv activated
    echo   f, freeze      - Freezes dependencies to requirements.txt
    echo   b, build       - Builds frontend and packages executable via PyInstaller
    echo   t, test, tests - Runs Pytest and Vitest test suites
    echo.
    goto :eof