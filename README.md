# Book3D Studio v0.6.1

Local, no-login Book → animated-video production prototype.

## Quick start
1. Run `install_windows.bat`.
2. Run `start_windows.bat`.
3. Click **Run System Test** once.
4. Click **Create 30s Sci-Fi Demo**.
5. Choose **Render Full 30s Quality Movie**.

The built-in **LAST SIGNAL** demo renders six small scenes separately, generates local voices/music/SFX, mixes them, then joins them into one 30-second MP4.

### Local requirements
- Python 3.14 supported by included dependency range.
- Blender 5.x supported on current GPUs; Book3D also supports Blender 4.5 LTS / 3.6 LTS as compatibility fallbacks for older hardware.
- FFmpeg available on PATH (or `BOOK3D_FFMPEG` set).
- Windows PowerShell for offline TTS; if unavailable, the pipeline uses a tone fallback instead of failing.
