from __future__ import annotations

from pathlib import Path
import json
import math
import os
import random
import shutil
import subprocess
import threading
import time
from typing import Iterable

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from .models import Project, Scene
from .short_film import (
    create_demo_project,
    find_ffmpeg,
    generate_music,
    generate_sfx,
    generate_scene_voice,
)

MODE_NAME = "Graphic Novel / Motion Comic"

PROFILES = {
    "fast": {"width": 960, "height": 540, "fps": 15, "crf": 25},
    "quality": {"width": 1280, "height": 720, "fps": 24, "crf": 20},
    "main": {"width": 1920, "height": 1080, "fps": 24, "crf": 18},
}

def _font(size: int, bold: bool = False):
    candidates = []
    if os.name == "nt":
        windir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        candidates.extend([
            windir / "Fonts" / ("arialbd.ttf" if bold else "arial.ttf"),
            windir / "Fonts" / ("seguisb.ttf" if bold else "segoeui.ttf"),
        ])
    else:
        candidates.extend([
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        ])
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except Exception:
                pass
    return ImageFont.load_default()

def _vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        for x in range(w):
            px[x, y] = c
    return img

def _add_halftone(img: Image.Image, spacing: int = 10, alpha: int = 25):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for y in range(0, img.height, spacing):
        offset = (spacing // 2) if (y // spacing) % 2 else 0
        for x in range(offset, img.width, spacing):
            d.ellipse((x, y, x + 2, y + 2), fill=(255, 255, 255, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

def _ink_line(draw, xy, fill=(7, 9, 14), width=6):
    draw.line(xy, fill=fill, width=width, joint="curve")

def _draw_mara(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 1.0, facing: int = 1, closeup: bool = False):
    ink = (5, 7, 11); suit = (31, 39, 49); suit2 = (48, 60, 72)
    cyan = (36, 218, 232); amber = (240, 161, 45); skin = (121, 83, 68)
    if closeup:
        r = int(150 * scale)
        draw.ellipse((x-r, y-r, x+r, y+r), fill=ink)
        draw.ellipse((x-r+10, y-r+10, x+r-10, y+r-10), fill=suit)
        draw.polygon([(x-int(118*scale), y-int(38*scale)), (x+int(110*scale), y-int(62*scale)), (x+int(126*scale), y+int(52*scale)), (x-int(100*scale), y+int(70*scale))], fill=ink)
        draw.polygon([(x-int(108*scale), y-int(30*scale)), (x+int(100*scale), y-int(50*scale)), (x+int(112*scale), y+int(40*scale)), (x-int(92*scale), y+int(58*scale))], fill=amber)
        draw.line((x-int(95*scale), y+int(85*scale), x+int(105*scale), y+int(70*scale)), fill=cyan, width=max(2,int(8*scale)))
        return
    s = scale
    legw = int(34*s); legh = int(125*s)
    for dx in (-int(25*s), int(25*s)):
        draw.rounded_rectangle((x+dx-legw//2, y-int(50*s), x+dx+legw//2, y+legh), radius=max(2,int(8*s)), fill=ink)
        draw.rounded_rectangle((x+dx-legw//2+5, y-int(45*s), x+dx+legw//2-5, y+legh-5), radius=max(2,int(6*s)), fill=suit2)
    bw = int(120*s)
    draw.rounded_rectangle((x-bw//2, y-int(185*s), x+bw//2, y-int(30*s)), radius=max(5,int(22*s)), fill=ink)
    draw.rounded_rectangle((x-bw//2+8, y-int(177*s), x+bw//2-8, y-int(38*s)), radius=max(5,int(16*s)), fill=suit)
    for side in (-1,1):
        ax=x+side*int(74*s)
        draw.rounded_rectangle((ax-int(20*s), y-int(168*s), ax+int(20*s), y-int(50*s)), radius=max(4,int(12*s)), fill=ink)
        draw.rounded_rectangle((ax-int(14*s), y-int(160*s), ax+int(14*s), y-int(56*s)), radius=max(4,int(9*s)), fill=suit2)
    draw.rectangle((x-int(23*s), y-int(220*s), x+int(23*s), y-int(180*s)), fill=ink)
    hr=int(52*s)
    draw.ellipse((x-hr, y-int(274*s)-hr, x+hr, y-int(274*s)+hr), fill=ink)
    draw.ellipse((x-hr+7, y-int(274*s)-hr+7, x+hr-7, y-int(274*s)+hr-7), fill=skin)
    draw.pieslice((x-hr+2, y-int(274*s)-hr+2, x+hr-2, y-int(274*s)+hr-2), 195, 350, fill=suit)
    visor = (x-int(46*s), y-int(294*s), x+int(45*s), y-int(256*s))
    draw.rounded_rectangle(visor, radius=max(3,int(8*s)), fill=ink)
    draw.rounded_rectangle((visor[0]+4,visor[1]+4,visor[2]-4,visor[3]-4), radius=max(3,int(6*s)), fill=amber)
    draw.line((x-int(44*s), y-int(126*s), x+int(44*s), y-int(126*s)), fill=cyan, width=max(2,int(6*s)))
    draw.line((x-int(35*s), y-int(95*s), x+int(35*s), y-int(95*s)), fill=cyan, width=max(2,int(4*s)))

def _draw_console(draw, x, y, w, h, warning=False):
    ink=(5,7,11); metal=(35,44,55); cyan=(31,226,238); red=(241,72,62)
    draw.polygon([(x-w//2,y),(x+w//2,y),(x+int(w*.42),y+h),(x-int(w*.42),y+h)], fill=ink)
    draw.polygon([(x-w//2+8,y+8),(x+w//2-8,y+8),(x+int(w*.39),y+h-8),(x-int(w*.39),y+h-8)], fill=metal)
    c = red if warning else cyan
    draw.rounded_rectangle((x-int(w*.35), y+int(h*.16), x+int(w*.35), y+int(h*.53)), radius=8, fill=ink)
    draw.rounded_rectangle((x-int(w*.32), y+int(h*.19), x+int(w*.32), y+int(h*.50)), radius=6, fill=(9,33,39) if not warning else (47,15,18))
    for i in range(4):
        yy=y+int(h*.24)+i*int(h*.055)
        draw.line((x-int(w*.26),yy,x+int(w*.23),yy), fill=c, width=3)

def _draw_waveform(draw, box, color=(40,232,242), phase=0.0, width=5):
    x0,y0,x1,y1=box; mid=(y0+y1)/2; pts=[]; span=max(1,x1-x0)
    for x in range(x0,x1+1,4):
        p=(x-x0)/span
        amp=(y1-y0)*0.32*(0.35+0.65*math.sin(p*math.pi)**2)
        y=mid + math.sin(p*math.pi*12+phase)*amp*0.55 + math.sin(p*math.pi*31+phase*1.7)*amp*0.15
        pts.append((x,int(y)))
    draw.line(pts, fill=(3,9,12), width=width+7)
    draw.line(pts, fill=color, width=width)

def _draw_stars(draw, w, h, seed=9):
    rnd=random.Random(seed)
    for _ in range(170):
        x=rnd.randrange(w); y=rnd.randrange(int(h*.68)); r=rnd.choice([1,1,1,2]); v=rnd.randrange(90,230)
        draw.ellipse((x-r,y-r,x+r,y+r), fill=(v,v,v))

def _caption(draw, text: str, size, top=True):
    if not text: return
    w,h=size; font=_font(max(20,int(h*.035)),bold=True); pad=max(16,int(h*.026)); maxw=int(w*.76)
    words=text.split(); lines=[]; cur=""
    for word in words:
        trial=(cur+" "+word).strip()
        if draw.textbbox((0,0),trial,font=font)[2] <= maxw: cur=trial
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    lines=lines[:3]; lineh=int(font.size*1.18) if hasattr(font,'size') else 28
    boxh=pad*2+lineh*len(lines); y=pad if top else h-boxh-pad
    draw.rounded_rectangle((pad,y,w-pad,y+boxh),radius=10,fill=(4,7,12,225),outline=(104,121,141),width=2)
    ty=y+pad
    for line in lines:
        draw.text((pad*2,ty),line,font=font,fill=(236,239,242)); ty+=lineh

def _speech(draw, text: str, anchor, size, synthetic=False):
    if not text: return
    w,h=size; maxw=int(w*.42); font=_font(max(20,int(h*.034))); pad=max(12,int(h*.018))
    words=text.split(); lines=[]; cur=""
    for word in words:
        trial=(cur+" "+word).strip()
        if draw.textbbox((0,0),trial,font=font)[2] <= maxw-pad*2: cur=trial
        else:
            if cur: lines.append(cur)
            cur=word
    if cur: lines.append(cur)
    lineh=int(font.size*1.18) if hasattr(font,'size') else 28
    bw=max(draw.textbbox((0,0),x,font=font)[2] for x in lines)+pad*2; bh=lineh*len(lines)+pad*2
    ax,ay=anchor; x=max(pad,min(w-bw-pad,ax-bw//2)); y=max(pad,min(h-bh-pad,ay-bh))
    fill=(11,24,29,235) if synthetic else (244,244,239,240); outline=(40,232,242) if synthetic else (10,11,14)
    draw.rounded_rectangle((x,y,x+bw,y+bh),radius=16,fill=fill,outline=outline,width=4)
    tri=[(ax-12,y+bh),(ax+12,y+bh),(ax,y+bh+22)]; draw.polygon(tri,fill=fill); _ink_line(draw,[tri[0],tri[2],tri[1]],fill=outline,width=3)
    ty=y+pad; color=(231,252,255) if synthetic else (12,13,16)
    for line in lines:
        draw.text((x+pad,ty),line,font=font,fill=color); ty+=lineh

def _scene_visual(scene: Scene, size: tuple[int,int]) -> Image.Image:
    w,h=size; sid=scene.id
    img=_vertical_gradient(size,(4,7,12),(14,17,25)) if sid=="D006" else _vertical_gradient(size,(6,9,15),(17,23,31))
    d=ImageDraw.Draw(img,"RGBA"); cyan=(38,229,240); red=(244,68,61); ink=(4,6,10)
    if sid=="D001":
        for i in range(7):
            x=int(w*(.10+i*.13)); d.line((w//2,int(h*.53),x,h),fill=(43,52,65),width=3)
        for y in (int(h*.62),int(h*.72),int(h*.84),int(h*.96)): d.line((0,y,w,y),fill=(31,39,50),width=3)
        d.rectangle((int(w*.09),int(h*.15),int(w*.91),int(h*.52)),outline=(50,60,72),width=5)
        _draw_console(d,int(w*.60),int(h*.42),int(w*.26),int(h*.30),False)
        _draw_mara(d,int(w*.29),int(h*.64),scale=h/720*1.0)
        _caption(d,"Relay K-17 had been dead for nine years. Then one console woke up.",size,True)
    elif sid=="D002":
        d.rectangle((int(w*.08),int(h*.13),int(w*.92),int(h*.88)),fill=(13,19,27),outline=(65,76,92),width=5)
        _draw_console(d,int(w*.50),int(h*.55),int(w*.38),int(h*.27),False)
        d.rounded_rectangle((int(w*.20),int(h*.20),int(w*.80),int(h*.46)),radius=18,fill=(6,25,30,220),outline=cyan,width=4)
        _draw_waveform(d,(int(w*.24),int(h*.26),int(w*.76),int(h*.40)),cyan,0.2,4)
        _draw_mara(d,int(w*.16),int(h*.72),scale=h/720*.86)
        _speech(d,"DO NOT ANSWER THE SIGNAL.",(int(w*.57),int(h*.30)),size,True)
    elif sid=="D003":
        d.polygon([(0,0),(int(w*.62),0),(int(w*.48),h),(0,h)],fill=(8,20,25))
        _draw_waveform(d,(int(w*.06),int(h*.34),int(w*.51),int(h*.58)),cyan,1.3,5)
        _draw_mara(d,int(w*.77),int(h*.48),scale=h/720*1.18,closeup=True)
        d.rounded_rectangle((int(w*.05),int(h*.12),int(w*.23),int(h*.20)),radius=10,fill=(54,8,8),outline=red,width=3)
        d.text((int(w*.075),int(h*.135)),"TRANSMIT",font=_font(max(18,int(h*.028)),True),fill=(255,219,214))
        _speech(d,"Mara... I found you.",(int(w*.40),int(h*.35)),size,True)
    elif sid=="D004":
        d.rectangle((0,0,w,h),fill=(24,9,12))
        d.rounded_rectangle((int(w*.60),int(h*.15),int(w*.91),int(h*.88)),radius=22,fill=(35,38,43),outline=ink,width=10)
        for i in range(5):
            yy=int(h*(.10+i*.18)); d.rectangle((0,yy,w,yy+int(h*.025)),fill=(red[0],red[1],red[2],120))
        _draw_mara(d,int(w*.34),int(h*.67),scale=h/720*1.02)
        _speech(d,"STEP AWAY FROM THE CONSOLE.",(int(w*.46),int(h*.31)),size,True)
    elif sid=="D005":
        d.rectangle((0,0,w,h),fill=(4,6,9))
        cx,cy=int(w*.62),int(h*.48)
        d.rounded_rectangle((cx-int(w*.045),cy-int(h*.12),cx+int(w*.045),cy+int(h*.12)),radius=14,fill=(6,20,23),outline=cyan,width=6)
        _draw_mara(d,int(w*.38),int(h*.69),scale=h/720*1.05)
        _speech(d,"Not today.",(int(w*.33),int(h*.33)),size,False)
        _caption(d,"Mara tore out the relay's power core.",size,False)
    else:
        _draw_stars(d,w,h,11)
        d.ellipse((-int(w*.15),int(h*.50),int(w*1.15),int(h*1.23)),fill=(42,44,52),outline=ink,width=7)
        d.ellipse((int(w*.12),int(h*.59),int(w*.88),int(h*.98)),fill=(24,28,35),outline=(7,9,13),width=5)
        cx,cy=w//2,int(h*.79)
        for i in range(1,7):
            rx=int(w*(.08+i*.055)); ry=int(h*(.025+i*.022)); d.ellipse((cx-rx,cy-ry,cx+rx,cy+ry),outline=cyan,width=max(3,int(h*.006)))
        _caption(d,"Below the crater, something vast switched on.",size,True)
        _speech(d,"Thank you.",(int(w*.72),int(h*.44)),size,True)
    d.rectangle((8,8,w-9,h-9),outline=(4,6,10),width=max(8,int(h*.014)))
    img=_add_halftone(img,spacing=max(9,int(h/75)),alpha=18)
    return ImageEnhance.Contrast(img).enhance(1.08)

def panel_prompt(scene: Scene) -> str:
    shot=scene.shots[0] if scene.shots else None
    action=shot.action if shot else scene.summary
    dialogue=shot.dialogue if shot else ""
    return ("Original stylized graphic-novel sci-fi panel, bold black ink outlines, cinematic composition, "
            "limited dark palette with cyan and red accents, halftone texture, clean readable silhouettes, "
            "consistent character Mara Voss: cropped dark hair under helmet, amber visor, charcoal pressure suit with cyan trim. "
            f"Location: {scene.location}. Action: {action}. Dialogue context: {dialogue}. "
            "No logos, no watermarks, no copyrighted characters, 16:9.")

def graphic_manifest(project: Project) -> dict:
    return {"title":project.title,"mode":MODE_NAME,"runtime_seconds":sum((s.shots[0].duration_s if s.shots else 5) for s in project.scenes),
            "pipeline":["story","scene plan","panel plan","illustration","motion","voice","music/SFX","assembly"],
            "scenes":[{"id":s.id,"title":s.title,"location":s.location,"duration_s":s.shots[0].duration_s if s.shots else 5,
                       "summary":s.summary,"dialogue":s.shots[0].dialogue if s.shots else "",
                       "panel_prompt":panel_prompt(s),"motion":"slow cinematic push/pan with restrained motion-comic movement"} for s in project.scenes]}

def render_panel(scene: Scene, output: Path, profile: str = "quality") -> Path:
    cfg=PROFILES.get(profile,PROFILES["quality"]); output.parent.mkdir(parents=True,exist_ok=True)
    _scene_visual(scene,(cfg["width"],cfg["height"])).save(output,"PNG",optimize=True); return output

def _render_motion_clip(ffmpeg: str, panel: Path, out: Path, profile: str, duration: float, scene_index: int):
    cfg=PROFILES.get(profile,PROFILES["quality"]); w,h,fps=cfg["width"],cfg["height"],cfg["fps"]
    vf=f"scale={int(w*1.06)}:{int(h*1.06)},crop={w}:{h}:(iw-ow)/2:(ih-oh)/2,fps={fps},format=yuv420p"
    cp=subprocess.run([ffmpeg,"-y","-loop","1","-framerate",str(fps),"-i",str(panel),"-t",f"{duration:.3f}","-vf",vf,"-an","-c:v","libx264","-preset","veryfast","-crf",str(cfg["crf"]),"-pix_fmt","yuv420p",str(out)],capture_output=True,text=True,timeout=120)
    if cp.returncode!=0: raise RuntimeError("FFmpeg motion render failed: "+(cp.stderr or "")[-1400:])

def _mix_scene(ffmpeg: str, visual: Path, voice: Path, music: Path, sfx: Path, out: Path, music_offset: float, duration: float):
    cp=subprocess.run([ffmpeg,"-y","-i",str(visual),"-i",str(voice),"-ss",f"{music_offset:.3f}","-t",f"{duration:.3f}","-i",str(music),"-i",str(sfx),"-filter_complex","[1:a]volume=1.35[a1];[2:a]volume=0.20[a2];[3:a]volume=0.58[a3];[a1][a2][a3]amix=inputs=3:duration=longest:dropout_transition=0[a]","-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","160k","-t",f"{duration:.3f}",str(out)],capture_output=True,text=True,timeout=120)
    if cp.returncode!=0: raise RuntimeError("FFmpeg scene audio mix failed: "+(cp.stderr or "")[-1400:])

def _concat(ffmpeg: str, clips: Iterable[Path], out: Path):
    clips=list(clips); lst=out.with_suffix(".concat.txt")
    lst.write_text("\n".join("file '"+str(p.resolve()).replace("'","'\\''")+"'" for p in clips),encoding="utf-8")
    cp=subprocess.run([ffmpeg,"-y","-f","concat","-safe","0","-i",str(lst),"-c","copy",str(out)],capture_output=True,text=True,timeout=120)
    if cp.returncode!=0: raise RuntimeError("FFmpeg final assembly failed: "+(cp.stderr or "")[-1400:])

def _write_status(path: Path, **kw):
    cur={}
    if path.exists():
        try: cur=json.loads(path.read_text(encoding="utf-8"))
        except Exception: pass
    cur.update(kw); cur["updated_at"]=time.time(); path.write_text(json.dumps(cur,indent=2),encoding="utf-8")

def start_graphic_novel_movie(project: Project, project_folder: Path, profile: str = "quality") -> dict:
    profile=profile if profile in PROFILES else "quality"; build=project_folder/"graphic_novel"; build.mkdir(parents=True,exist_ok=True); status_path=build/"status.json"
    _write_status(status_path,status="rendering",step="planning panels",progress=1,profile=profile,mode=MODE_NAME)
    def worker():
        try:
            ffmpeg=find_ffmpeg()
            if not ffmpeg: raise RuntimeError("FFmpeg was not found. Install FFmpeg or set BOOK3D_FFMPEG to ffmpeg.exe.")
            total=sum((s.shots[0].duration_s if s.shots else 5.0) for s in project.scenes); music=build/"music.wav"; generate_music(music,total)
            clips=[]; elapsed=0.0
            for i,scene in enumerate(project.scenes):
                duration=float(scene.shots[0].duration_s if scene.shots else 5.0)
                panel=build/f"{scene.id}_{profile}.png"; render_panel(scene,panel,profile)
                visual=build/f"{scene.id}_{profile}_motion.mp4"; _render_motion_clip(ffmpeg,panel,visual,profile,duration,i)
                voice=build/f"{scene.id}_voice.wav"; sfx=build/f"{scene.id}_sfx.wav"; mixed=build/f"{scene.id}_{profile}_mixed.mp4"
                generate_scene_voice(scene,voice); generate_sfx(i,sfx,duration); _mix_scene(ffmpeg,visual,voice,music,sfx,mixed,elapsed,duration)
                clips.append(mixed); elapsed+=duration; _write_status(status_path,status="rendering",step=f"scene {i+1}/{len(project.scenes)}",progress=int((i+1)/len(project.scenes)*90))
            final=build/f"LAST_SIGNAL_graphic_novel_{profile}.mp4"; _concat(ffmpeg,clips,final)
            (build/"graphic_manifest.json").write_text(json.dumps(graphic_manifest(project),indent=2),encoding="utf-8")
            _write_status(status_path,status="complete",step="done",progress=100,video=str(final),bytes=final.stat().st_size)
        except Exception as e:
            _write_status(status_path,status="failed",error=str(e))
    threading.Thread(target=worker,daemon=True).start()
    return json.loads(status_path.read_text(encoding="utf-8"))

def graphic_status(project_folder: Path) -> dict:
    p=project_folder/"graphic_novel"/"status.json"
    if not p.exists(): return {"status":"not_started","progress":0,"mode":MODE_NAME}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {"status":"unknown","progress":0,"mode":MODE_NAME}

def create_graphic_demo_project() -> Project:
    p=create_demo_project(); p.style=MODE_NAME; return p
