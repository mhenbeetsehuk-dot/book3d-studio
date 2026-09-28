from pathlib import Path
import tempfile
from PIL import Image
from app.graphic_novel import create_graphic_demo_project, graphic_manifest, render_panel

p=create_graphic_demo_project()
assert p.style == 'Graphic Novel / Motion Comic'
assert len(p.scenes) == 6
m=graphic_manifest(p)
assert m['runtime_seconds'] == 30
assert len(m['scenes']) == 6
assert all('panel_prompt' in s for s in m['scenes'])
with tempfile.TemporaryDirectory() as td:
    out=Path(td)/'D001.png'
    render_panel(p.scenes[0],out,'fast')
    assert out.exists() and out.stat().st_size > 5000
    im=Image.open(out)
    assert im.size == (960,540)
print('BOOK3D_GRAPHIC_NOVEL_TEST_PASS')
