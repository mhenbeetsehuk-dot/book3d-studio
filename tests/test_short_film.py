from pathlib import Path
import tempfile, json, py_compile
from app.short_film import create_demo_project, story_manifest, generate_music, generate_sfx, generate_scene_voice
from app.blender_runtime import prepare_scene

p=create_demo_project()
assert len(p.scenes)==6
assert sum(sh.duration_s for sc in p.scenes for sh in sc.shots)==30
assert all(len(sc.shots)==1 for sc in p.scenes)
assert p.style=='Stylized Cartoon 3D'
m=story_manifest(p)
assert m['runtime_seconds']==30 and len(m['scenes'])==6
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    generate_music(td/'music.wav',30)
    assert (td/'music.wav').stat().st_size>10000
    generate_sfx(5,td/'sfx.wav',5)
    assert (td/'sfx.wav').stat().st_size>1000
    for sc in p.scenes:
        rd,script,out=prepare_scene(p,td,sc.id,'quality')
        py_compile.compile(str(script),doraise=True)
print('BOOK3D_SHORT_FILM_TEST_PASS')
