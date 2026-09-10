#!/bin/bash
# Run the audio_controller from within its package directory.
# set -e: abort on error; pipefail: fail a pipeline if any part fails.
# (-u is intentionally omitted: sourcing the venv activate script trips on unset vars.)
set -eo pipefail

# resolve paths relative to this script, not the current working directory (B2)
cd "$(dirname "$0")"

source pyenv/bin/activate
cd audio_controller
# -u: ongebufferde stdout. Zonder dit is stdout naar journald (een pipe) blok-
# gebufferd en krijgen alle print()-regels het tijdstip van de bufferflush in
# plaats van dat van de gebeurtenis. Op west stonden daardoor 20+ ongerelateerde
# regels op dezelfde seconde, waardoor de journal niet te gebruiken was om een
# storing terug te zoeken.
python3 -u -m audio_controller
cd ..
deactivate
