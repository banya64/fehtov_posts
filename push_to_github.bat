@echo off
setlocal
rem Создайте приватный репозиторий fehtov_posts на https://github.com/new
rem Затем укажите ваш логин GitHub (или передайте его: set GITHUB_USER=ваш_логин)
if "%GITHUB_USER%"=="" set /p GITHUB_USER="GitHub username: "
if "%GITHUB_USER%"=="" (echo Need GITHUB_USER. & exit /b 1)
set REPO_URL=https://github.com/%GITHUB_USER%/fehtov_posts.git
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git push -u origin master
echo Done.
pause
