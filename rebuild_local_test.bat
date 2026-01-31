@echo off
setlocal

REM --- Configuration ---
REM --- Configuration Check ---
if "%PROJECT_ID%"=="" (
    echo [ERROR] PROJECT_ID environment variable is not set.
    exit /b 1
)
if "%BUCKET_NAME%"=="" (
    echo [ERROR] BUCKET_NAME environment variable is not set.
    exit /b 1
)
set CREDENTIALS_FILE=%APPDATA%\gcloud\application_default_credentials.json

REM --- Check Credentials ---
if not exist "%CREDENTIALS_FILE%" (
    echo [ERROR] Credentials file not found at: %CREDENTIALS_FILE%
    echo Please run: gcloud auth application-default login
    exit /b 1
)

REM --- Build Job Image (Standard Name) ---
echo [1/4] Building Job Image (anneal-dev)...
xcopy /E /I /Y template\spec spec >nul
xcopy /E /I /Y template\generated generated >nul
docker build -t anneal-dev .
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

REM --- Build API Image (Standard Name) ---
echo [2/4] Building API Image (anneal-api-dev)...
cd trigger_api
docker build -t anneal-api-dev .
cd ..
if %ERRORLEVEL% NEQ 0 exit /b %ERRORLEVEL%

REM --- Stop Old Containers ---
docker stop anneal-api-local 2>nul & docker rm anneal-api-local 2>nul
docker stop anneal-job-local 2>nul & docker rm anneal-job-local 2>nul

REM --- Run API Container ---
echo [3/4] Starting API Container (anneal-api-local) on port 8080...
echo     Points to Bucket: %BUCKET_NAME%
echo     Points to Project: %PROJECT_ID%
echo.
docker run -d --name anneal-api-local -p 8080:8080 ^
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json ^
  -e PROJECT_ID=%PROJECT_ID% ^
  -e BUCKET_NAME=%BUCKET_NAME% ^
  -e JOB_NAME=anneal-job-local ^
  -e LOCAL_MODE=true ^
  -v "%CREDENTIALS_FILE%":/tmp/keys/creds.json:ro ^
  anneal-api-dev

REM --- Done ---
echo.
echo [4/4] Setup Complete!
echo.
echo API is running at: http://localhost:8080
echo.
echo To RUN A JOB (Simulate Cloud Run):
echo 1. Trigger it (Cmd): curl -X POST http://localhost:8080/submit -H "Content-Type: application/json" -d "{\"prompt\": \"Test Prompt\"}"
echo    Trigger it (PS):  Invoke-RestMethod -Uri http://localhost:8080/submit -Method Post -ContentType "application/json" -Body '{"prompt": "Test Prompt"}'
echo 2. (Copy the job_id from the output)
echo 3. Run the Worker:
echo    [CMD]  (Copy/Paste this):
echo    docker run --rm --name anneal-job-local ^
echo      -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json ^
echo      -e JOB_ID=REPLACE_WITH_JOB_ID ^
echo      -e RESULTS_BUCKET=%BUCKET_NAME% ^
echo      -e GEMINI_API_KEY=%GEMINI_API_KEY% ^
echo      -e ARISTOTLE_API_KEY=%ARISTOTLE_API_KEY% ^
echo      -e PROJECT_ID=%PROJECT_ID% ^
echo      -v "%CREDENTIALS_FILE%":/tmp/keys/creds.json:ro ^
echo      anneal-dev
echo.
echo    [PowerShell] (Copy/Paste this):
echo    docker run --rm --name anneal-job-local `
echo      -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json `
echo      -e JOB_ID="REPLACE_WITH_JOB_ID" `
echo      -e RESULTS_BUCKET=$env:BUCKET_NAME `
echo      -e GEMINI_API_KEY=$env:GEMINI_API_KEY `
echo      -e ARISTOTLE_API_KEY=$env:ARISTOTLE_API_KEY `
echo      -e PROJECT_ID=$env:PROJECT_ID `
echo      -v "$env:APPDATA\gcloud\application_default_credentials.json:/tmp/keys/creds.json:ro" `
echo      anneal-dev
