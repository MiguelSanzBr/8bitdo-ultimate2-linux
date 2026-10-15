8BitDo Ultimate 2 - AppImage
============================

FIRST TIME ONLY: install the udev rule. Without it the app cannot open the controller
("permission denied" or "controller not found").

  1. Make the files executable (a zip download loses that):
         chmod +x install-udev.sh 8BitDo-Ultimate-2-*.AppImage
  2. Run the installer (it asks for your administrator password):
         ./install-udev.sh
  3. Unplug and replug the controller (or its 2.4G adapter).
  4. Start the AppImage:
         ./8BitDo-Ultimate-2-*.AppImage

Afterwards you only need the AppImage. It needs a graphical session and nothing else installed.

If the AppImage refuses to start (missing FUSE), run it with:
         APPIMAGE_EXTRACT_AND_RUN=1 ./8BitDo-Ultimate-2-*.AppImage

On a system where your user has no password yet (for example SteamOS), set one first with `passwd`.
