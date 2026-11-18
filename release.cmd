@echo off
rem ============================================================================
rem  VOIDLOCK release helper.  Double-click it, or run "release.cmd" in this folder.
rem  1. checks the version is the same everywhere (and CHANGELOG / What's new are written)
rem  2. runs the same tests the GitHub build runs
rem  3. commits everything, pushes, and puts the tag vX.Y.Z on that commit
rem  4. checks that GitHub really received it
rem  It stops at the first problem, before anything is pushed.
rem ============================================================================
setlocal enableextensions
cd /d "%~dp0"
set PYTHONUTF8=1
echo.
echo === VOIDLOCK release ===

where git >nul 2>nul
if errorlevel 1 ( echo [X] git is not installed or not in PATH. & goto :fail )
where python >nul 2>nul
if errorlevel 1 ( echo [X] python is not installed or not in PATH. & goto :fail )
git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 ( echo [X] This folder is not a git repository. & goto :fail )

echo.
echo [1/4] Checking the version...
python tools\release_check.py > "%TEMP%\vl_version.txt"
if errorlevel 1 ( echo [X] Fix the problems above, then run this again. & goto :fail )
set /p VER=<"%TEMP%\vl_version.txt"
echo       Version %VER%

echo.
echo [2/4] Running the tests - about a minute...
python tests\logic_test.py > "%TEMP%\vl_tests.txt" 2>&1
if errorlevel 1 goto :fail_logic
echo       logic_test: all passed
where node >nul 2>nul
if errorlevel 1 goto :no_node
node android\tests\js_unit_test.js > "%TEMP%\vl_js.txt" 2>&1
if errorlevel 1 goto :fail_js
echo       js tests: all passed
python android\tests\report_parity_test.py > "%TEMP%\vl_parity.txt" 2>&1
if errorlevel 1 goto :fail_parity
echo       report parity: all passed
goto :tests_done
:no_node
echo       [!] node is not installed, so the phone-side tests were skipped. The GitHub build still runs them.
:tests_done

echo.
echo [3/4] Git...
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do set BR=%%b
git add -A
echo.
echo These changes will be released as v%VER% on branch "%BR%":
git status --short
echo.
set "OK="
set /p OK=Type Y and press Enter to commit, push and tag (anything else cancels): 
if /i not "%OK%"=="Y" ( echo Cancelled. Nothing was pushed. & goto :end )

git diff --cached --quiet
if errorlevel 1 (
  git commit -q -m "Release v%VER%"
  if errorlevel 1 ( echo [X] git commit failed. & goto :fail )
) else (
  echo       Nothing new to commit - releasing the current commit.
)
git push origin "%BR%"
if errorlevel 1 ( echo [X] git push failed. & goto :fail )

set "REMOTE_TAG="
for /f "delims=" %%t in ('git ls-remote --tags origin "refs/tags/v%VER%"') do set REMOTE_TAG=%%t
git rev-parse -q --verify "refs/tags/v%VER%" >nul 2>nul
set LOCAL_TAG=%errorlevel%
if defined REMOTE_TAG set LOCAL_TAG=0
if not "%LOCAL_TAG%"=="0" goto :tag_create
echo.
echo The tag v%VER% already exists.
set "MV="
set /p MV=Move it to this commit? That starts a new build. Y/N: 
if /i not "%MV%"=="Y" ( echo Cancelled. The commit is pushed, the tag was not touched. & goto :end )
git tag -d "v%VER%" >nul 2>nul
git push origin ":refs/tags/v%VER%" >nul 2>nul
:tag_create
git tag "v%VER%"
if errorlevel 1 ( echo [X] Could not create the tag. & goto :fail )
git push origin "v%VER%"
if errorlevel 1 ( echo [X] Could not push the tag. & goto :fail )

echo.
echo [4/4] Checking what GitHub received...
git fetch origin --tags -q
for /f "delims=" %%h in ('git rev-parse HEAD') do set HEAD_SHA=%%h
for /f "delims=" %%h in ('git rev-parse "origin/%BR%"') do set BRANCH_SHA=%%h
for /f "delims=" %%h in ('git rev-parse "v%VER%^{commit}"') do set TAG_SHA=%%h
if /i not "%HEAD_SHA%"=="%BRANCH_SHA%" ( echo [X] GitHub's branch is not at your latest commit. & goto :fail )
if /i not "%HEAD_SHA%"=="%TAG_SHA%" ( echo [X] The tag is not on your latest commit. & goto :fail )
echo       Branch and tag v%VER% are both on %HEAD_SHA:~0,8%.
echo.
echo DONE. Open the Actions tab on GitHub: the build for v%VER% has started.
goto :end

:fail_logic
echo [X] tests\logic_test.py failed. The failed checks:
findstr /b /c:"FAIL" /c:"  FAILED:" /c:"Traceback" "%TEMP%\vl_tests.txt"
echo     Full output: %TEMP%\vl_tests.txt
goto :fail

:fail_js
echo [X] android\tests\js_unit_test.js failed. See %TEMP%\vl_js.txt
goto :fail

:fail_parity
echo [X] The computer and phone reports differ. See %TEMP%\vl_parity.txt
goto :fail

:fail
echo.
echo *** STOPPED. Nothing after the failed step was done. ***
endlocal
pause
exit /b 1

:end
endlocal
pause
exit /b 0
