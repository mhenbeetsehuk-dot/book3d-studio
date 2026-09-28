from __future__ import annotations
from pathlib import Path
import os, glob, shutil, subprocess, threading, json, time
from .models import Project
from .blender_export import blender_scene_script


def find_blender() -> str | None:
    env = os.environ.get('BOOK3D_BLENDER')
    if env and Path(env).exists():
        return env
    found = shutil.which('blender') or shutil.which('blender.exe')
    if found:
        return found
    if os.name == 'nt':
        roots = [os.environ.get('ProgramFiles', r'C:\\Program Files'), os.environ.get('LOCALAPPDATA','')]
        patterns=[]
        for root in roots:
            if root:
                patterns += [
                    str(Path(root) / 'Blender Foundation' / 'Blender *' / 'blender.exe'),
                    str(Path(root) / 'Programs' / 'Blender Foundation' / 'Blender *' / 'blender.exe'),
                ]
        matches=[]
        for p in patterns: matches.extend(glob.glob(p))
        if matches:
            return sorted(matches, reverse=True)[0]
    return None


def _write_status(folder: Path, **data):
    current={}
    p=folder/'render_status.json'
    if p.exists():
        try: current=json.loads(p.read_text(encoding='utf-8'))
        except Exception: current={}
    current.update(data)
    current['updated_at']=time.time()
    p.write_text(json.dumps(current,indent=2),encoding='utf-8')


def prepare_scene(project: Project, project_folder: Path, scene_id: str, profile: str="quality"):
    scene=next((s for s in project.scenes if s.id==scene_id),None)
    if not scene: raise ValueError('Scene not found')
    render_dir=project_folder/'renders'/scene_id
    render_dir.mkdir(parents=True,exist_ok=True)
    profile = profile if profile in ('fast','quality','main') else 'quality'
    out=render_dir/f'{profile}.mp4'
    script=render_dir/'build_and_render.py'
    script.write_text(blender_scene_script(project,scene,str(out.resolve())),encoding='utf-8')
    _write_status(render_dir,status='prepared',scene_id=scene_id,profile=profile,video=str(out),script=str(script))
    return render_dir,script,out


def start_render(project: Project, project_folder: Path, scene_id: str, profile: str="quality"):
    blender=find_blender()
    if not blender:
        raise FileNotFoundError('Blender was not detected. Install Blender 4.x or set BOOK3D_BLENDER to blender.exe.')
    profile = profile if profile in ('fast','quality','main') else 'quality'
    render_dir,script,out=prepare_scene(project,project_folder,scene_id,profile)
    status_path=render_dir/'render_status.json'
    if status_path.exists():
        try:
            st=json.loads(status_path.read_text(encoding='utf-8'))
            if st.get('status')=='rendering': return st
        except Exception: pass
    _write_status(render_dir,status='rendering',blender=blender,profile=profile,started_at=time.time(),error='')

    def worker():
        expected_out=render_dir/f'{profile}.mp4'
        attempts=[
            # First try Workbench on Vulkan. Blender 5.x can fail on older OpenGL
            # drivers even when Vulkan is usable. --factory-startup avoids a saved
            # user backend overriding this compatibility path.
            ('workbench_vulkan','BLENDER_WORKBENCH','vulkan',180 if profile=='fast' else (600 if profile=='quality' else 1800)),
            # CPU Cycles is slower but avoids Workbench/EEVEE shader paths. Use it
            # as a fallback for quality as well as main renders.
            ('cycles_cpu_vulkan','CYCLES','vulkan',420 if profile=='fast' else (1200 if profile=='quality' else 3600)),
            # Final legacy attempt with Blender's default graphics backend. This can
            # work on Blender 4.5/3.6 systems where Vulkan is unavailable.
            ('cycles_cpu_default','CYCLES',None,420 if profile=='fast' else (1200 if profile=='quality' else 3600)),
        ]
        last_rc=None
        combined_logs=[]
        try:
            for label, forced_engine, gpu_backend, timeout_s in attempts:
                for stale in (expected_out, Path(str(expected_out)+'.mp4')):
                    try:
                        if stale.exists(): stale.unlink()
                    except Exception: pass
                log=render_dir/f'blender_{label}.log'
                env=os.environ.copy()
                env['BOOK3D_RENDER_PROFILE']=profile
                if forced_engine:
                    env['BOOK3D_RENDER_ENGINE']=forced_engine
                else:
                    env.pop('BOOK3D_RENDER_ENGINE',None)
                _write_status(render_dir,status='rendering',attempt=label,engine=forced_engine or 'auto',gpu_backend=gpu_backend or 'default')
                timed_out=False
                try:
                    with log.open('w',encoding='utf-8',errors='replace') as f:
                        cmd=[blender,'--factory-startup']
                        if gpu_backend:
                            cmd += ['--gpu-backend',gpu_backend]
                        cmd += ['--background','--python',str(script.resolve())]
                        proc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout_s,env=env)
                    last_rc=proc.returncode
                except subprocess.TimeoutExpired:
                    timed_out=True
                    last_rc=-999
                    with log.open('a',encoding='utf-8',errors='replace') as f:
                        f.write(f'\nBOOK3D_TIMEOUT: {label} exceeded {timeout_s} seconds and was stopped.\n')
                try:
                    txt=log.read_text(encoding='utf-8',errors='replace')
                except Exception:
                    txt=''
                combined_logs.append(f'===== {label} =====\n'+txt)
                candidates=[expected_out, Path(str(expected_out)+'.mp4')]
                candidates += sorted(render_dir.glob('*.mp4'))
                actual=next((x for x in candidates if x.exists() and x.is_file() and x.stat().st_size>0),None)
                if (not timed_out) and last_rc==0 and actual:
                    final_out=expected_out
                    if actual.resolve()!=expected_out.resolve():
                        try:
                            if expected_out.exists(): expected_out.unlink()
                            actual.replace(expected_out)
                        except Exception:
                            final_out=actual
                    _write_status(render_dir,status='complete',completed_at=time.time(),bytes=final_out.stat().st_size,video=str(final_out),attempt=label,engine=forced_engine or 'auto',gpu_backend=gpu_backend or 'default')
                    return

                _write_status(render_dir,status='rendering',attempt=f'{label}_failed_retrying',returncode=last_rc,timeout=timed_out)

            tail='\n'.join(('\n'.join(combined_logs)).splitlines()[-120:])
            unsupported_gpu = ('GL_ARB_shader_draw_parameters' in tail or 'OpenGL implementation doesn\'t support' in tail or 'Out of resource error' in tail)
            if unsupported_gpu:
                err=('This Blender build cannot use the current graphics driver/hardware. '
                     'Book3D tried Vulkan Workbench and CPU Cycles fallbacks. '
                     'Install/update the manufacturer graphics driver; if the GPU is older, use Blender 4.5 LTS or 3.6 LTS and Book3D will detect it automatically.')
            elif last_rc==0:
                err='Blender completed successfully, but no MP4 was found after compatibility retries.'
            else:
                err=f'Blender failed after automatic compatibility retries (last code {last_rc}).'
            _write_status(render_dir,status='failed',error=err,log_tail=tail,returncode=last_rc,unsupported_gpu=unsupported_gpu)
        except Exception as e:
            _write_status(render_dir,status='failed',error=str(e))

    threading.Thread(target=worker,daemon=True).start()
    return json.loads((render_dir/'render_status.json').read_text(encoding='utf-8'))


def status(project_folder: Path, scene_id: str):
    render_dir=project_folder/'renders'/scene_id
    p=render_dir/'render_status.json'
    if not p.exists(): return {'status':'not_started','scene_id':scene_id}
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {'status':'unknown','scene_id':scene_id}


def run_system_test(root: Path):
    import sys, tempfile, textwrap
    checks=[]
    def add(name, ok, detail=''):
        checks.append({'name':name,'ok':bool(ok),'detail':str(detail)[:1200]})

    add('Python runtime', sys.version_info >= (3, 11), sys.version.split()[0])
    try:
        import fastapi, pydantic
        add('Core Python packages', True, f'FastAPI {fastapi.__version__}; Pydantic {pydantic.__version__}')
    except Exception as e:
        add('Core Python packages', False, repr(e))

    blender=find_blender()
    if not blender:
        add('Blender detected', False, 'Blender executable not found')
        return {'ok':False,'checks':checks,'recommended_engine':None}
    add('Blender detected', True, blender)

    tmp=Path(tempfile.mkdtemp(prefix='book3d_selftest_'))
    probe=tmp/'probe.py'; tiny=tmp/'tiny.py'; out=tmp/'tiny.mp4'
    probe.write_text(textwrap.dedent(r'''
        import bpy, json
        sc=bpy.context.scene
        engines=[]
        for e in ('BLENDER_EEVEE_NEXT','BLENDER_EEVEE','BLENDER_WORKBENCH','CYCLES'):
            try:
                sc.render.engine=e; engines.append(e)
            except Exception: pass
        img=sc.render.image_settings
        media=hasattr(img,'media_type')
        video=False; ffmpeg=False
        if media:
            try: img.media_type='VIDEO'; video=True
            except Exception: pass
        try: img.file_format='FFMPEG'; ffmpeg=True
        except Exception: pass
        print('BOOK3D_PROBE='+json.dumps({'version':bpy.app.version_string,'engines':engines,'media_type':media,'video':video,'ffmpeg':ffmpeg}))
    '''),encoding='utf-8')
    engines=[]
    try:
        cp=subprocess.run([blender,'--factory-startup','--background','--python',str(probe)],capture_output=True,text=True,timeout=45)
        blob=(cp.stdout or '')+'\n'+(cp.stderr or '')
        payload=None
        for line in blob.splitlines():
            if line.startswith('BOOK3D_PROBE='):
                try: payload=json.loads(line.split('=',1)[1])
                except Exception: pass
        if cp.returncode==0 and payload:
            engines=payload.get('engines',[])
            add('Blender API probe', True, f"Blender {payload.get('version')}; engines: {', '.join(engines)}")
            video_ok=bool(payload.get('video') or payload.get('ffmpeg'))
            add('Blender video output', video_ok, f"VIDEO={payload.get('video')} FFMPEG={payload.get('ffmpeg')}")
        else:
            add('Blender API probe', False, blob[-1000:])
    except Exception as e:
        add('Blender API probe', False, repr(e))

    tiny.write_text(textwrap.dedent(f'''
        import bpy, os
        from mathutils import Vector
        sc=bpy.context.scene
        sc.render.engine='BLENDER_WORKBENCH'
        sc.render.resolution_x=320; sc.render.resolution_y=180; sc.render.resolution_percentage=100; sc.render.fps=12
        img=sc.render.image_settings
        if hasattr(img,'media_type'):
            try: img.media_type='VIDEO'
            except Exception: pass
        try: img.file_format='FFMPEG'
        except Exception: pass
        sc.render.ffmpeg.format='MPEG4'; sc.render.ffmpeg.codec='H264'; sc.render.filepath=r"{str(out.with_suffix(''))}"
        bpy.ops.mesh.primitive_cube_add(location=(0,0,0)); cube=bpy.context.object
        bpy.ops.object.camera_add(location=(4,-4,3)); cam=bpy.context.object; sc.camera=cam
        cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler()
        sc.frame_start=1; sc.frame_end=12
        cube.rotation_euler.z=0; cube.keyframe_insert('rotation_euler',frame=1); cube.rotation_euler.z=1.2; cube.keyframe_insert('rotation_euler',frame=12)
        bpy.ops.render.render(animation=True)
        print('BOOK3D_TINY_RENDER_DONE')
    '''),encoding='utf-8')
    tiny_ok=False
    if 'BLENDER_WORKBENCH' in engines:
        try:
            cp=subprocess.run([blender,'--factory-startup','--gpu-backend','vulkan','--background','--python',str(tiny)],capture_output=True,text=True,timeout=120)
            candidates=[out, Path(str(out)+'.mp4'), out.with_suffix('.mp4')]
            candidates += list(tmp.glob('*.mp4'))
            tiny_file=next((p for p in candidates if p.exists() and p.stat().st_size>0),None)
            tiny_ok=(cp.returncode==0 and tiny_file is not None)
            detail=(cp.stdout or '')+'\n'+(cp.stderr or '')
            if tiny_ok:
                add('Tiny MP4 render (Vulkan Workbench)', True, f"code={cp.returncode}; bytes={tiny_file.stat().st_size if tiny_file else 0}")
            else:
                gpu_old=('GL_ARB_shader_draw_parameters' in detail or 'OpenGL implementation doesn\'t support' in detail)
                add('Tiny MP4 render (Vulkan Workbench)', False, ('Blender 5.x graphics requirement not met; Book3D will use CPU/legacy fallback.' if gpu_old else detail[-900:]))
        except subprocess.TimeoutExpired:
            add('Tiny MP4 render (Vulkan Workbench)', False, 'Timed out after 120 seconds')
        except Exception as e:
            add('Tiny MP4 render (Vulkan Workbench)', False, repr(e))
    else:
        add('Tiny MP4 render (Vulkan Workbench)', False, 'Workbench unavailable')

    recommended='BLENDER_WORKBENCH/VULKAN' if tiny_ok else ('CYCLES/CPU' if 'CYCLES' in engines else (engines[0] if engines else None))
    return {'ok':all(c['ok'] for c in checks),'checks':checks,'recommended_engine':recommended}
