@echo off
for /f %%i in ('git rev-parse HEAD') do set GIT_COMMIT=%%i
ECHO { "gitCommitId": "%GIT_COMMIT%", "buildTimestamp": "%DATE:/=-%_%TIME::=-%" } > resources\meta.json
docker build -t flightradar:latest .
DEL resources\meta.json