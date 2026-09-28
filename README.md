# Book3D Studio v0.7.0

Book/manuscript → story plan → **Graphic Novel / Motion Comic** → MP4, with the experimental 3D path still available.

## Recommended mode for low-resource PCs
The primary acceptance path is now **Graphic Novel / Motion Comic**. It generates original illustrated panels locally with Pillow, adds restrained camera movement with FFmpeg, generates local voice/audio, and assembles the final MP4. It does **not require Blender or a modern GPU**.

## Quick start
1. Run `install_windows.bat`.
2. Run `start_windows.bat`.
3. Click **Create 30s Graphic-Novel Demo**.
4. Click **Render Full 30s Quality Motion Comic**.
5. Open the final MP4 when the status reaches complete.

The built-in acceptance film is **LAST SIGNAL**: six ~5-second scenes, with consistent Mara Voss design, graphic-novel panels, motion, voices, original procedural music and SFX.

## Requirements
- Python 3.14 supported by the included dependency ranges.
- FFmpeg available on PATH, or set `BOOK3D_FFMPEG` to `ffmpeg.exe`.
- Pillow is installed automatically by `install_windows.bat`.
- Windows PowerShell enables offline TTS; otherwise the pipeline uses a tone fallback.
- Blender is optional and used only for the experimental 3D mode.

## Render profiles
- Fast: 960×540, 15 fps.
- Quality: 1280×720, 24 fps.
- Main: 1920×1080, 24 fps.

## Commercial path
The local procedural illustrator is an acceptance renderer and offline fallback. The panel manifest also emits clean scene prompts so future commercial image providers can plug into the same pipeline without changing story/audio/assembly logic.
