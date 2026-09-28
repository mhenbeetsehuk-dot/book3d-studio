# Changelog

## 0.7.0
- Added primary Graphic Novel / Motion Comic production mode.
- Added original local illustrated panel renderer using Pillow; no Blender/GPU required.
- Added LAST SIGNAL six-panel visual style bible and consistent Mara Voss design.
- Added panel prompts/manifest for future commercial AI image-provider adapters.
- Added lightweight FFmpeg pan/zoom motion-comic animation.
- Reused offline voice, original procedural music and SFX, and final MP4 assembly.
- Added Fast 540p, Quality 720p and Main 1080p graphic-novel profiles.
- Kept the experimental 3D path available as a secondary mode.

## 0.6.1
- Added Vulkan-first Blender compatibility path for problematic OpenGL drivers.
- Added CPU Cycles fallback for fast, quality, and main renders.
- Detects Blender 5.x mandatory OpenGL extension failures such as GL_ARB_shader_draw_parameters.
- System Test now tries Vulkan before declaring local rendering unavailable.
- Added legacy Blender 4.5 LTS / 3.6 LTS fallback guidance for older GPUs.


## 0.6.0
- Added built-in 30-second sci-fi acceptance film **LAST SIGNAL**.
- Six independently rendered ~5-second scenes for low-resource PCs.
- Added one-click complete movie pipeline.
- Added offline Windows TTS voice generation with safe fallback.
- Added original procedural sci-fi music and sound effects.
- Added FFmpeg audio mixing and scene stitching.
- Added story/audio manifest endpoint and downloadable final MP4.
- Added automated short-film regression test and generated Blender-script compilation test.

## 0.5.0
- Added system test and tiny Blender MP4 diagnostics.
