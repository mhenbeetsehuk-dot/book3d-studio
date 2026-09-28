from pathlib import Path
import tempfile, py_compile
from app.analyzer import analyze
from app.blender_runtime import prepare_scene

TEXT = '''PROLOGUE — The Descent\n\nKessara entered the Queen's Chamber with Commander Cole. The chamber shook as burning objects crossed the sky. Kessara pulled her daughter close and ordered Cole to seal the doors.\n\nCole said, “We cannot hold this place forever.” Kessara looked toward the lower passage as alarms echoed through the chamber. They moved toward the passage while the floor trembled beneath them.\n\nCHAPTER ONE\n\nDr Lena Vasik arrived at Meridian Base after midnight. Officer Webb met her inside the command room. The monitors showed a signal repeating beneath the colony. Vasik studied the pattern and asked Webb to isolate the source.\n\nWebb crossed the room and opened the archive. The signal changed. Both of them stopped speaking as a new sequence appeared across every display in Meridian Base.'''

p=analyze(TEXT,'Regression Story','regression.txt')
assert p.scenes, 'no scenes'
assert all(s.shots for s in p.scenes), 'scene without shots'
assert len({s.id for s in p.scenes})==len(p.scenes), 'duplicate scene IDs'
with tempfile.TemporaryDirectory() as d:
    folder=Path(d)
    rd, script, out=prepare_scene(p,folder,p.scenes[0].id,'quality')
    py_compile.compile(str(script),doraise=True)
    assert out.name=='quality.mp4'
print('BOOK3D_REGRESSION_PASS',len(p.scenes),len(p.characters),len(p.locations))
