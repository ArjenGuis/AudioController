rm -r ./pyenv
python3 -m venv pyenv
source ./pyenv/bin/activate
python -m pip install -U pip
python -m pip install pylint
python -m pip install black
python -m pip install pyserial
python -m pip install tornado
python -m pip install python-socketio
python -m pip install transcrypt
python -m pip install watchdog
python -m pip install python-decouple
python -m pip install onvif-zeep
cd audio_controller
python -m pip install --editable .
cd ..
deactivate