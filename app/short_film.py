from __future__ import annotations
from pathlib import Path
import json, math, os, shutil, subprocess, threading, time, wave, struct
from .models import Project, Character, Location, Scene, Shot
from .blender_runtime import start_render, status as scene_render_status

TITLE = "LAST SIGNAL"

def create_demo_project() -> Project:
    characters = [
        Character(name="Mara Voss", description="Solo salvage pilot in a compact pressure suit.", visual_anchor="stylized female sci-fi pilot, cropped dark hair, amber visor, charcoal pressure suit with cyan trim", voice_anchor="calm adult female, alert, restrained"),
        Character(name="Station Voice", description="Damaged relay intelligence / unknown signal.", visual_anchor="cyan holographic waveform and terminal glow", voice_anchor="neutral synthetic voice, quiet, slightly distorted"),
    ]
    locations = [
        Location(name="Relay K-17", description="Abandoned lunar communications relay.", visual_anchor="stylized abandoned moon relay interior, dark metal, cyan consoles, red emergency lights"),
        Location(name="Moon Exterior", description="Airless crater around Relay K-17.", visual_anchor="stylized moon crater, black sky, distant stars, buried alien geometry"),
    ]
    scenes = [
        Scene(id="D001", chapter="30s Demo", title="The Dead Relay", location="Relay K-17", characters=["Mara Voss"], summary="Mara enters a dead relay and discovers one impossible signal.", shots=[
            Shot(number=1,duration_s=5,shot_type="wide",camera_move="slow push-in",action="Mara steps into the abandoned relay. A single cyan console wakes in the darkness.",dialogue="",mood="uneasy",characters=["Mara Voss"],location="Relay K-17",assets=["cyan console","dust","helmet light"]),
        ]),
        Scene(id="D002", chapter="30s Demo", title="The Warning", location="Relay K-17", characters=["Mara Voss","Station Voice"], summary="A hologram warns Mara not to answer the signal.", shots=[
            Shot(number=1,duration_s=5,shot_type="medium",camera_move="dolly",action="A broken holographic waveform flickers above the console while Mara leans closer.",dialogue="Station Voice: Do not answer the signal.",mood="warning",characters=["Mara Voss","Station Voice"],location="Relay K-17",assets=["hologram","console"]),
        ]),
        Scene(id="D003", chapter="30s Demo", title="It Answers", location="Relay K-17", characters=["Mara Voss","Station Voice"], summary="The relay transmits by itself, then replies using Mara's own voice.", shots=[
            Shot(number=1,duration_s=5,shot_type="close-up",camera_move="subtle handheld",action="The transmit light turns on by itself. Mara freezes as the waveform changes to match her voiceprint.",dialogue="Station Voice: Mara... I found you.",mood="dread",characters=["Mara Voss","Station Voice"],location="Relay K-17",assets=["voiceprint","red transmit light"]),
        ]),
        Scene(id="D004", chapter="30s Demo", title="Seal", location="Relay K-17", characters=["Mara Voss","Station Voice"], summary="The door locks and the station orders Mara away from the console.", shots=[
            Shot(number=1,duration_s=5,shot_type="over-the-shoulder",camera_move="slow orbit",action="The hatch slams shut. Red emergency lights pulse behind Mara as she reaches for the power core.",dialogue="Station Voice: Step away from the console.",mood="urgent",characters=["Mara Voss","Station Voice"],location="Relay K-17",assets=["sealed hatch","red alarm lights","power core"]),
        ]),
        Scene(id="D005", chapter="30s Demo", title="Cut the Power", location="Relay K-17", characters=["Mara Voss"], summary="Mara tears out the relay power core and everything goes black.", shots=[
            Shot(number=1,duration_s=5,shot_type="medium",camera_move="dolly",action="Mara yanks the glowing power core free. The relay drops into total darkness except for her visor light.",dialogue="Mara Voss: Not today.",mood="decisive",characters=["Mara Voss"],location="Relay K-17",assets=["power core","sparks","visor light"]),
        ]),
        Scene(id="D006", chapter="30s Demo", title="Below the Crater", location="Moon Exterior", characters=["Station Voice"], summary="Outside, something enormous beneath the crater wakes because Mara cut the power.", shots=[
            Shot(number=1,duration_s=5,shot_type="establishing wide",camera_move="slow push-in",action="Outside the silent relay, a vast buried geometric structure beneath the crater lights up in concentric cyan lines.",dialogue="Station Voice: Thank you.",mood="cosmic reveal",characters=["Station Voice"],location="Moon Exterior",assets=["moon crater","buried alien structure","cyan light rings","stars"]),
        ]),
    ]
    return Project(id="demo_last_signal", title=TITLE, source_filename="built_in_demo", style="Stylized Cartoon 3D", characters=characters, locations=locations, scenes=scenes)


def story_manifest(project: Project) -> dict:
    return {
        "title": project.title,
        "runtime_seconds": 30,
        "format": "6 scenes x ~5 seconds",
        "visual_style": "stylized cartoon 3D, graphic lighting, low-resource friendly",
        "audio": {
            "music": "original procedural sci-fi ambient pulse generated locally",
            "voices": {"Mara Voss":"offline Windows TTS voice", "Station Voice":"offline Windows TTS voice with lower rate"},
            "sfx": "procedural beeps, alarms, power-down and low-frequency reveal rumble"
        },
        "scenes": [dict(s.model_dump(), generation_prompt=(f"Stylized cartoon 3D sci-fi short. {s.location}. {s.shots[0].action} Graphic cinematic lighting, clean silhouettes, low-poly production-friendly geometry, consistent Mara Voss design, no text, 16:9.")) for s in project.scenes],
    }


def find_ffmpeg() -> str | None:
    env=os.environ.get("BOOK3D_FFMPEG")
    if env and Path(env).exists(): return env
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def _write_wav(path: Path, duration: float, generators, rate: int=44100):
    path.parent.mkdir(parents=True, exist_ok=True)
    n=max(1,int(duration*rate))
    with wave.open(str(path),'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        frames=bytearray()
        for i in range(n):
            t=i/rate
            sample=sum(fn(t) for fn in generators)
            sample=max(-1.0,min(1.0,sample))
            frames += struct.pack('<h', int(sample*32767))
        w.writeframes(frames)


def _tone(freq, amp=0.15, start=0.0, end=999.0, fade=0.05):
    def f(t):
        if t<start or t>end: return 0.0
        local=t-start
        env=min(1.0, local/fade if fade else 1.0, (end-t)/fade if fade else 1.0)
        return math.sin(2*math.pi*freq*t)*amp*max(0.0,env)
    return f


def generate_music(path: Path, duration: float=30.0):
    gens=[_tone(55,0.06), _tone(82.41,0.035), _tone(110,0.02)]
    for t in range(0,30,2):
        gens.append(_tone(220 if (t//2)%2==0 else 196,0.035,t,t+0.18,0.03))
    _write_wav(path,duration,gens)


def generate_sfx(scene_index: int, path: Path, duration: float=5.0):
    gens=[]
    if scene_index==0:
        gens=[_tone(880,0.10,3.8,4.05,0.02),_tone(1320,0.06,3.92,4.12,0.02)]
    elif scene_index==1:
        gens=[_tone(660,0.08,0.4,0.65,0.02),_tone(990,0.05,0.65,0.8,0.02)]
    elif scene_index==2:
        gens=[_tone(440,0.09,0.2,0.35,0.01),_tone(440,0.09,0.5,0.65,0.01)]
    elif scene_index==3:
        gens=[_tone(180,0.08,0,5,0.03),_tone(720,0.05,0.2,0.45,0.02),_tone(720,0.05,1.2,1.45,0.02)]
    elif scene_index==4:
        gens=[_tone(90,0.14,1.5,2.1,0.04),_tone(45,0.10,1.7,3.4,0.08)]
    else:
        gens=[_tone(38,0.18,0,5,0.2),_tone(76,0.05,1.8,5,0.2)]
    _write_wav(path,duration,gens)


def _powershell_tts(text: str, path: Path, rate: int=0, gender: str='Female') -> tuple[bool,str]:
    if os.name != 'nt': return False,'Windows TTS is available on Windows only.'
    ps=shutil.which('powershell') or shutil.which('powershell.exe')
    if not ps: return False,'PowerShell not found.'
    env=os.environ.copy(); env['BOOK3D_TTS_TEXT']=text; env['BOOK3D_TTS_OUT']=str(path.resolve()); env['BOOK3D_TTS_RATE']=str(rate); env['BOOK3D_TTS_GENDER']=gender
    script=("Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate=[int]$env:BOOK3D_TTS_RATE; try { $g=[System.Speech.Synthesis.VoiceGender]::$($env:BOOK3D_TTS_GENDER); $s.SelectVoiceByHints($g) } catch {}; "
            "$s.SetOutputToWaveFile($env:BOOK3D_TTS_OUT); "
            "$s.Speak($env:BOOK3D_TTS_TEXT); $s.Dispose()")
    try:
        cp=subprocess.run([ps,'-NoProfile','-NonInteractive','-Command',script],capture_output=True,text=True,timeout=30,env=env)
        ok=cp.returncode==0 and path.exists() and path.stat().st_size>44
        return ok,(cp.stderr or cp.stdout or '').strip()
    except Exception as e: return False,repr(e)


def generate_scene_voice(scene: Scene, path: Path) -> dict:
    line=scene.shots[0].dialogue.strip() if scene.shots else ''
    if not line:
        _write_wav(path,5.0,[])
        return {'ok':True,'mode':'silence'}
    speaker,text=(line.split(':',1)+[''])[:2] if ':' in line else ('Narrator',line)
    speaker=speaker.strip(); text=text.strip()
    ok,detail=_powershell_tts(text,path, rate=-2 if speaker=='Station Voice' else 0, gender='Male' if speaker=='Station Voice' else 'Female')
    if not ok:
        _write_wav(path,5.0,[_tone(300 if speaker=='Mara Voss' else 190,0.04,0.5,2.8,0.08)])
        return {'ok':False,'mode':'tone_fallback','detail':detail}
    return {'ok':True,'mode':'windows_tts','speaker':speaker,'text':text}


def _ffmpeg_mix_scene(ffmpeg: str, visual: Path, voice: Path, music: Path, sfx: Path, out: Path, music_offset: float):
    cmd=[ffmpeg,'-y','-i',str(visual),'-i',str(voice),'-ss',f'{music_offset:.3f}','-t','5','-i',str(music),'-i',str(sfx),
         '-filter_complex','[1:a]volume=1.35[a1];[2:a]volume=0.22[a2];[3:a]volume=0.65[a3];[a1][a2][a3]amix=inputs=3:duration=longest:dropout_transition=0[a]',
         '-map','0:v:0','-map','[a]','-c:v','copy','-c:a','aac','-b:a','160k','-shortest',str(out)]
    cp=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    if cp.returncode!=0: raise RuntimeError('FFmpeg scene mix failed: '+(cp.stderr or '')[-1200:])


def _concat(ffmpeg: str, clips: list[Path], out: Path):
    lst=out.with_suffix('.concat.txt')
    lst.write_text('\n'.join("file '"+str(p.resolve()).replace("'","'\\''")+"'" for p in clips),encoding='utf-8')
    cp=subprocess.run([ffmpeg,'-y','-f','concat','-safe','0','-i',str(lst),'-c','copy',str(out)],capture_output=True,text=True,timeout=120)
    if cp.returncode!=0:
        cp=subprocess.run([ffmpeg,'-y','-f','concat','-safe','0','-i',str(lst),'-c:v','libx264','-preset','veryfast','-crf','21','-c:a','aac','-b:a','160k',str(out)],capture_output=True,text=True,timeout=240)
    if cp.returncode!=0: raise RuntimeError('FFmpeg concat failed: '+(cp.stderr or '')[-1200:])


def start_demo_movie(project: Project, project_folder: Path, profile: str='quality') -> dict:
    profile=profile if profile in ('fast','quality','main') else 'quality'
    build_dir=project_folder/'demo_movie'; build_dir.mkdir(parents=True,exist_ok=True)
    status_path=build_dir/'status.json'
    def write(**kw):
        cur={}
        if status_path.exists():
            try: cur=json.loads(status_path.read_text(encoding='utf-8'))
            except Exception: pass
        cur.update(kw); cur['updated_at']=time.time(); status_path.write_text(json.dumps(cur,indent=2),encoding='utf-8')
    if status_path.exists():
        try:
            old=json.loads(status_path.read_text(encoding='utf-8'))
            if old.get('status')=='rendering': return old
        except Exception: pass
    write(status='rendering',step='preparing audio',profile=profile,progress=0)

    def worker():
        try:
            ffmpeg=find_ffmpeg()
            if not ffmpeg: raise RuntimeError('FFmpeg was not found. Install FFmpeg or set BOOK3D_FFMPEG.')
            music=build_dir/'music.wav'; generate_music(music,30.0)
            clips=[]; audio_notes=[]
            for i,scene in enumerate(project.scenes):
                write(status='rendering',step=f'rendering scene {i+1}/6',progress=int(i/6*75),scene_id=scene.id)
                start_render(project,project_folder,scene.id,profile)
                deadline=time.time()+(900 if profile=='quality' else 420)
                while time.time()<deadline:
                    st=scene_render_status(project_folder,scene.id)
                    if st.get('status') in ('complete','failed'): break
                    time.sleep(1.5)
                st=scene_render_status(project_folder,scene.id)
                if st.get('status')!='complete': raise RuntimeError(f"{scene.id} render failed: {st.get('error','timeout')}")
                visual=Path(st.get('video') or (project_folder/'renders'/scene.id/f'{profile}.mp4'))
                voice=build_dir/f'{scene.id}_voice.wav'; sfx=build_dir/f'{scene.id}_sfx.wav'; mixed=build_dir/f'{scene.id}_mixed.mp4'
                audio_notes.append(generate_scene_voice(scene,voice)); generate_sfx(i,sfx,5.0)
                write(status='rendering',step=f'mixing audio {i+1}/6',progress=75+int(i/6*18),scene_id=scene.id)
                _ffmpeg_mix_scene(ffmpeg,visual,voice,music,sfx,mixed,i*5.0); clips.append(mixed)
            write(status='rendering',step='joining six scenes',progress=95)
            final=build_dir/'LAST_SIGNAL_30s.mp4'; _concat(ffmpeg,clips,final)
            (build_dir/'story_manifest.json').write_text(json.dumps(story_manifest(project),indent=2),encoding='utf-8')
            write(status='complete',step='done',progress=100,video=str(final),bytes=final.stat().st_size,audio_notes=audio_notes)
        except Exception as e:
            write(status='failed',error=str(e))
    threading.Thread(target=worker,daemon=True).start()
    return json.loads(status_path.read_text(encoding='utf-8'))


def demo_status(project_folder: Path) -> dict:
    p=project_folder/'demo_movie'/'status.json'
    if not p.exists(): return {'status':'not_started','progress':0}
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {'status':'unknown','progress':0}
