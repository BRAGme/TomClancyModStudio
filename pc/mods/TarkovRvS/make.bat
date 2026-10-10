@echo off
rem ===========================================================================
rem  Build TarkovRvS.u with Raven Shield's own compiler.
rem
rem  Usage:   make.bat "D:\SteamLibrary\steamapps\common\Rainbow Six 3 Gold"
rem
rem  `ucc.exe` ships in <game>\system -- you do not need the fan SDK to
rem  COMPILE. You need it to read the stock classes, which is a different job
rem  (see README.md, "Reading the classes you are extending").
rem
rem  What this does, in the order Unreal wants it:
rem    1. copies Classes\*.uc to <game>\TarkovRvS\Classes\, because ucc
rem       resolves a package by looking for a folder of that name beside
rem       system\, not by being told a path
rem    2. writes <game>\system\TarkovBuild.ini -- RavenShield.ini plus one
rem       EditPackages line -- so the game's own config is not touched
rem    3. runs ucc make against that ini
rem    4. leaves TarkovRvS.u in <game>\system
rem
rem  Nothing here writes to a retail file. TarkovBuild.ini is ours and the
rem  package it produces is new.
rem ===========================================================================

setlocal
if "%~1"=="" (
    echo Usage: make.bat "^<path to Rainbow Six 3 Gold^>"
    exit /b 1
)
set GAME=%~1
set SYS=%GAME%\system

if not exist "%SYS%\ucc.exe" (
    echo Cannot find "%SYS%\ucc.exe" -- is that the game folder?
    exit /b 1
)
if not exist "%SYS%\RavenShield.ini" (
    echo Cannot find "%SYS%\RavenShield.ini".
    exit /b 1
)

echo [1/4] copying sources
if exist "%GAME%\TarkovRvS\Classes" rmdir /s /q "%GAME%\TarkovRvS\Classes"
mkdir "%GAME%\TarkovRvS\Classes" 2>nul
copy /y "%~dp0Classes\*.uc" "%GAME%\TarkovRvS\Classes\" >nul
if errorlevel 1 exit /b 1

echo [2/4] writing TarkovBuild.ini
rem ucc reads EditPackages from [Editor.EditorEngine]. Appending ours at the
rem END matters: a package may only extend packages listed before it.
copy /y "%SYS%\RavenShield.ini" "%SYS%\TarkovBuild.ini" >nul
findstr /i /c:"EditPackages=TarkovRvS" "%SYS%\TarkovBuild.ini" >nul
if errorlevel 1 (
    rem Appended under its own section header, which Unreal merges with the
    rem one already in the file.
    echo.>>"%SYS%\TarkovBuild.ini"
    echo [Editor.EditorEngine]>>"%SYS%\TarkovBuild.ini"
    echo EditPackages=TarkovRvS>>"%SYS%\TarkovBuild.ini"
)

echo [3/4] compiling
if exist "%SYS%\TarkovRvS.u" del "%SYS%\TarkovRvS.u"
pushd "%SYS%"
ucc.exe make -ini=TarkovBuild.ini
set RC=%ERRORLEVEL%
popd

echo [4/4] result
if not exist "%SYS%\TarkovRvS.u" (
    echo.
    echo BUILD FAILED. Read the compiler output above -- and read it closely,
    echo because two files in this mod are DELIBERATE guesses and the error
    echo message is how you find out what they should have been:
    echo.
    echo   * TarkovPawn*.uc    the R6TakeDamage argument list
    echo   * TarkovInjector.uc the type of m_pCurrentMod
    echo.
    echo Both are documented at the top of their own file, with what to do.
    exit /b 1
)
echo Built "%SYS%\TarkovRvS.u".
echo.
echo Next: copy TarkovRvS.ini to "%SYS%" and add these two lines to
echo [Engine.GameEngine] in "%SYS%\RavenShield.ini":
echo.
echo     ServerPackages=TarkovRvS
echo     ServerActors=TarkovRvS.TarkovInjector
echo.
endlocal
