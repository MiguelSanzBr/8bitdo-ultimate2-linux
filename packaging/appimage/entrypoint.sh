#! /bin/bash
# Launcher used by python-appimage; "$@" are forwarded to the GUI.
{{ python-executable }} -c 'import sys; from ultimate2.gui.app import main; sys.exit(main())' "$@"
