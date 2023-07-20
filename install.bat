@echo off

py -m venv venv
call venv/scripts/activate
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt

python dowload_models.py

pause