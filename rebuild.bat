@echo off
xcopy /E /I /Y template\spec spec
xcopy /E /I /Y template\generated generated
docker build -t anneal-dev .
docker stop anneal-work 2>nul & docker rm anneal-work 2>nul
docker run -d --name anneal-work anneal-dev
