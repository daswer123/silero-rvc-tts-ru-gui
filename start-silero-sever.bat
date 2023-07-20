@echo off

call venv/scripts/activate
cd libs/silero_api_server
py server.py --p 8080