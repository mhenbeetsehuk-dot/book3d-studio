from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, FileResponse
from pathlib import Path
import json, shutil, re, traceback
from .parsers import extract_text
from .analyzer import analyze
from .models import Project
from .blender_export import blender_script
from .blender_runtime import find_blender, start_render, status as render_status, prepare_scene, run_system_test
from .short_film import create_demo_project, story_manifest, start_demo_movie, demo_status
from .graphic_novel import create_graphic_demo_project, graphic_manifest, start_graphic_novel_movie, graphic_status, render_panel

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / 'projects'; UPLOADS = ROOT / 'uploads'
UPLOADS.mkdir(exist_ok=True); PROJECTS.mkdir(exist_ok=True)
app = FastAPI(title='Book3D Studio', version='0.7.0')

def safe_name(name: str) -> str: return re.sub(r'[^A-Za-z0-9._-]+','_',name)

def save_project(p: Project):
    folder=PROJECTS/p.id; folder.mkdir(exist_ok=True)
    (folder/'project.json').write_text(p.model_dump_json(indent=2),encoding='utf-8')
    (folder/'build_scene.py').write_text(blender_script(p),encoding='utf-8')

def load_project(project_id:str):
    folder=PROJECTS/safe_name(project_id); path=folder/'project.json'
    if not path.exists(): raise HTTPException(404,'Project not found')
    return Project.model_validate_json(path.read_text(encoding='utf-8')),folder

INDEX=r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Book3D Studio</title>
<style>body{font-family:system-ui;background:#0f1117;color:#f2f4f8;margin:0}.wrap{max-width:1100px;margin:auto;padding:24px}.hero{padding:26px;border:1px solid #303644;border-radius:18px;background:#171b24}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:#171b24;border:1px solid #303644;border-radius:14px;padding:16px;margin-top:16px}input,select,button{font:inherit;padding:11px;border-radius:10px;border:1px solid #3a4252;background:#10141c;color:#fff}button{cursor:pointer;background:#fff;color:#111;font-weight:700}.secondary{background:#202735;color:#fff}.muted{color:#aab3c2}.pill{display:inline-block;padding:4px 9px;border:1px solid #3a4252;border-radius:999px;margin:3px;font-size:12px}.scene{border-top:1px solid #303644;padding:12px 0}.bar{height:8px;background:#252b36;border-radius:99px;overflow:hidden}.fill{height:100%;width:0;background:#fff;transition:.3s}.good{color:#9be3aa}.warn{color:#ffd37a}.bad{color:#ff8e8e}a{color:white}.actions{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.renderbox{background:#10141c;border-radius:10px;padding:10px;margin-top:8px} @media(max-width:760px){.grid{grid-template-columns:1fr}}</style></head>
<body><div class="wrap"><div class="hero"><h1>Book3D Studio <span style="font-size:13px;color:#aab3c2;font-weight:500">v0.7.0</span></h1><p class="muted">Book → story bible → scene direction → 3D preview → reusable production pipeline. Local. No login.</p><form id="f"><input type="file" name="file" accept=".txt,.docx,.pdf,.epub" required> <input name="title" placeholder="Project title (optional)"> <select name="style"><option>Cinematic 3D</option><option>Stylized 3D</option><option>Realistic 3D</option><option>Anime-inspired 3D</option></select> <button>Create Production Plan</button></form><div class="bar" style="margin-top:16px"><div id="fill" class="fill"></div></div><p id="status" class="muted"></p><p id="blender" class="muted">Checking Blender…</p><div class="actions"><button type="button" class="secondary" onclick="systemTest()">Run System Test</button><button type="button" onclick="createGraphicDemo()">Create 30s Graphic-Novel Demo</button><button type="button" class="secondary" onclick="createDemo()">Create 30s 3D Demo</button></div><div id="systemtest" class="renderbox muted" style="display:none"></div></div><div id="out"></div></div>
<script>
let current=null; const f=document.getElementById('f'),out=document.getElementById('out'),status=document.getElementById('status'),fill=document.getElementById('fill'),blender=document.getElementById('blender');
(async()=>{let r=await fetch('/api/blender/status');let b=await r.json(); blender.innerHTML=b.detected?`<span class="good">Blender detected:</span> ${b.path}`:`<span class="warn">Blender not detected yet.</span> Production plans work now; install Blender 4.x or 5.x before rendering 3D previews.`})();
f.onsubmit=async(e)=>{e.preventDefault();fill.style.width='35%';status.textContent='Reading manuscript and building story bible…';out.innerHTML='';let r=await fetch('/api/project',{method:'POST',body:new FormData(f)});if(!r.ok){status.textContent='Error: '+await r.text();fill.style.width='0';return}fill.style.width='100%';current=await r.json();status.textContent=`Created ${current.scenes.length} scenes, ${current.characters.length} character anchors, ${current.locations.length} location anchors.`;render(current)};
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function render(p){let chars=p.characters.map(x=>`<span class="pill">${esc(x.name)}</span>`).join(''),locs=p.locations.map(x=>`<span class="pill">${esc(x.name)}</span>`).join('');let scenes=p.scenes.slice(0,50).map((s,i)=>`<div class="scene"><b>${esc(s.id)} · ${esc(s.chapter)} · ${esc(s.title)}</b><div class="muted">${esc(s.location)} · ${s.shots.length} shots</div><p>${esc(s.summary)}</p><div class="actions"><button class="secondary" onclick="prepare('${s.id}')">Build Blender scene</button>${i===0?`<button onclick="render3d('${s.id}','quality')">Quality Preview</button><button class="secondary" onclick="render3d('${s.id}','fast')">Fast Preview</button><button class="secondary" onclick="render3d('${s.id}','main')">Main Render</button>`:''}</div><div id="r_${s.id}" class="renderbox muted" style="display:none"></div>${s.shots.map(q=>`<div class="muted">Shot ${q.number}: ${esc(q.shot_type)}, ${esc(q.camera_move)}, ${q.duration_s}s — ${esc(q.action)}</div>`).join('')}</div>`).join('');out.innerHTML=`<div class="card"><h2>3D pipeline</h2><p class="muted">v0.7 adds a CPU-friendly Graphic Novel / Motion Comic pipeline alongside the 3D pipeline. Graphic-novel rendering does not require Blender or a modern GPU.</p></div><div class="grid"><div class="card"><h2>Characters</h2>${chars}</div><div class="card"><h2>Locations</h2>${locs}</div></div><div class="card"><h2>Production plan</h2><p><a href="/api/project/${p.id}/json">Project JSON</a> · <a href="/api/project/${p.id}/blender">Blender script</a></p>${scenes}</div>`}
async function createGraphicDemo(){fill.style.width='40%';status.textContent='Creating LAST SIGNAL graphical-novel production plan…';out.innerHTML='';let r=await fetch('/api/graphic-demo/create',{method:'POST'});let j=await r.json();if(!r.ok){status.textContent='Graphic demo error: '+(j.detail||JSON.stringify(j));return}current=j.project;fill.style.width='100%';status.textContent='LAST SIGNAL Graphic Novel ready: six illustrated scenes, voices, music and SFX.';render(current);let card=document.createElement('div');card.className='card';card.innerHTML=\`<h2>Graphic Novel / Motion Comic</h2><p><b>LAST SIGNAL</b> will be drawn as six original illustrated panels and animated with lightweight camera motion. This path does not require Blender or a modern GPU.</p><div class="actions"><button onclick="renderGraphicMovie('quality')">Render Full 30s Quality Motion Comic</button><button class="secondary" onclick="renderGraphicMovie('fast')">Render Fast Test</button><a href="/api/graphic-demo/\${current.id}/manifest">Panel Manifest</a></div><div id="graphicMovieStatus" class="renderbox muted"></div>\`;out.prepend(card)}
async function renderGraphicMovie(profile='quality'){let box=document.getElementById('graphicMovieStatus');box.textContent='Starting panel illustration and motion-comic assembly…';let r=await fetch(\`/api/graphic-demo/\${current.id}/render?profile=\${encodeURIComponent(profile)}\`,{method:'POST'});let j=await r.json();if(!r.ok){box.innerHTML='<span class="bad">'+esc(j.detail||JSON.stringify(j))+'</span>';return}let t=setInterval(async()=>{let q=await fetch(\`/api/graphic-demo/\${current.id}/status\`),x=await q.json();box.textContent=\`\${x.status}: \${x.step||''} (\${x.progress||0}%)\`;if(x.status==='complete'){clearInterval(t);box.innerHTML=\`<span class="good">Motion comic complete.</span> <a href="/api/graphic-demo/\${current.id}/video?profile=\${encodeURIComponent(profile)}">Open final 30s MP4</a>\`}else if(x.status==='failed'){clearInterval(t);box.innerHTML='<span class="bad">'+esc(x.error||'Graphic-novel pipeline failed')+'</span>'}},1500)}

async function createDemo(){fill.style.width='40%';status.textContent='Creating LAST SIGNAL — six 5-second scenes…';out.innerHTML='';let r=await fetch('/api/demo/create',{method:'POST'});let j=await r.json();if(!r.ok){status.textContent='Demo error: '+(j.detail||JSON.stringify(j));return}current=j.project;fill.style.width='100%';status.textContent='LAST SIGNAL ready: 6 scenes, 30 seconds, voices/music/SFX plan included.';render(current);let card=document.createElement('div');card.className='card';card.innerHTML=`<h2>30-second movie test</h2><p><b>LAST SIGNAL</b> is six separate ~5-second renders, then local voice/music/SFX mixing and final stitching.</p><div class="actions"><button onclick="renderDemoMovie('quality')">Render Full 30s Quality Movie</button><button class="secondary" onclick="renderDemoMovie('fast')">Render Full 30s Fast Test</button><a href="/api/demo/${current.id}/manifest">Story/Audio Manifest</a></div><div id="demoMovieStatus" class="renderbox muted"></div>`;out.prepend(card)}
async function renderDemoMovie(profile='quality'){let box=document.getElementById('demoMovieStatus');box.textContent='Starting complete movie pipeline…';let r=await fetch(`/api/demo/${current.id}/render?profile=${encodeURIComponent(profile)}`,{method:'POST'});let j=await r.json();if(!r.ok){box.innerHTML='<span class="bad">'+esc(j.detail||JSON.stringify(j))+'</span>';return}let t=setInterval(async()=>{let q=await fetch(`/api/demo/${current.id}/status`),s=await q.json();box.textContent=`${s.status}: ${s.step||''} (${s.progress||0}%)`;if(s.status==='complete'){clearInterval(t);box.innerHTML=`<span class="good">30-second movie complete.</span> <a href="/api/demo/${current.id}/video">Open LAST SIGNAL MP4</a>`}else if(s.status==='failed'){clearInterval(t);box.innerHTML='<span class="bad">'+esc(s.error||'Demo pipeline failed')+'</span>'}},2000)}
async function systemTest(){let box=document.getElementById('systemtest');box.style.display='block';box.textContent='Running Python/Blender/video/tiny-render diagnostics…';let r=await fetch('/api/system-test',{method:'POST'});let j=await r.json();let rows=(j.checks||[]).map(x=>`<div><b class="${x.ok?'good':'bad'}">${x.ok?'PASS':'FAIL'}</b> ${esc(x.name)}${x.detail?' — '+esc(x.detail):''}</div>`).join('');box.innerHTML=`<b>System test: ${j.ok?'PASS':'NEEDS ATTENTION'}</b><div style="margin-top:8px">${rows}</div>${j.recommended_engine?'<div style="margin-top:8px">Recommended renderer: <b>'+esc(j.recommended_engine)+'</b></div>':''}`}
async function prepare(id){let box=document.getElementById('r_'+id);box.style.display='block';box.textContent='Building Blender script…';let r=await fetch(`/api/project/${current.id}/scene/${id}/prepare`,{method:'POST'});let j=await r.json();box.textContent=r.ok?'Scene prepared: '+j.script:'Error: '+(j.detail||JSON.stringify(j))}
async function render3d(id,profile='quality'){let box=document.getElementById('r_'+id);box.style.display='block';box.textContent='Starting '+profile+' render…';let r=await fetch(`/api/project/${current.id}/scene/${id}/render?profile=${encodeURIComponent(profile)}`,{method:'POST'});let j=await r.json();if(!r.ok){box.innerHTML='<span class="bad">'+esc(j.detail||JSON.stringify(j))+'</span>';return}poll(id,profile)}
async function poll(id,profile){let box=document.getElementById('r_'+id),timer=setInterval(async()=>{let r=await fetch(`/api/project/${current.id}/scene/${id}/render/status`),j=await r.json();box.textContent='Render status: '+j.status;if(j.status==='complete'){clearInterval(timer);box.innerHTML=`<span class="good">Render complete.</span> <a href="/api/project/${current.id}/scene/${id}/video?profile=${encodeURIComponent(profile)}">Open ${esc(profile)} MP4</a>`}else if(j.status==='failed'){clearInterval(timer);box.innerHTML='<span class="bad">Render failed: '+esc(j.error||'Unknown error')+'</span>'+(j.log_tail?'<pre style="white-space:pre-wrap;max-height:260px;overflow:auto">'+esc(j.log_tail)+'</pre>':'')}},2000)}
</script></body></html>'''

@app.get('/',response_class=HTMLResponse)
def home(): return INDEX

@app.post('/api/system-test')
def system_test():
    return JSONResponse(run_system_test(ROOT))

@app.get('/api/blender/status')
def blender_status():
    p=find_blender(); return {'detected':bool(p),'path':p}

@app.post('/api/project')
async def create_project(file:UploadFile=File(...),title:str=Form(''),style:str=Form('Cinematic 3D')):
    filename=safe_name(file.filename or 'manuscript.txt'); path=UPLOADS/filename
    with path.open('wb') as f: shutil.copyfileobj(file.file,f)
    try: text=extract_text(path)
    except Exception as e: raise HTTPException(400,str(e))
    if len(text.strip())<100: raise HTTPException(400,'The manuscript did not contain enough readable text.')
    try:
        p=analyze(text,title.strip() or path.stem.replace('_',' ').title(),filename)
        p.style=style
        save_project(p)
        return JSONResponse(p.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        (ROOT/'book3d_error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise HTTPException(500, f'Project creation failed: {type(e).__name__}: {e}')

@app.get('/api/project/{project_id}/json')
def project_json(project_id:str):
    p,folder=load_project(project_id); return PlainTextResponse((folder/'project.json').read_text(encoding='utf-8'),media_type='application/json')

@app.get('/api/project/{project_id}/blender')
def project_blender(project_id:str):
    p,folder=load_project(project_id); return PlainTextResponse((folder/'build_scene.py').read_text(encoding='utf-8'),media_type='text/x-python')

@app.post('/api/project/{project_id}/scene/{scene_id}/prepare')
def scene_prepare(project_id:str,scene_id:str,profile:str='quality'):
    p,folder=load_project(project_id)
    try: rd,script,out=prepare_scene(p,folder,scene_id,profile)
    except ValueError as e: raise HTTPException(404,str(e))
    return {'ok':True,'scene_id':scene_id,'script':str(script),'output':str(out)}

@app.post('/api/project/{project_id}/scene/{scene_id}/render')
def scene_render(project_id:str,scene_id:str,profile:str='quality'):
    p,folder=load_project(project_id)
    try: return start_render(p,folder,scene_id,profile)
    except FileNotFoundError as e: raise HTTPException(409,str(e))
    except ValueError as e: raise HTTPException(404,str(e))

@app.get('/api/project/{project_id}/scene/{scene_id}/render/status')
def scene_render_status(project_id:str,scene_id:str):
    p,folder=load_project(project_id); return render_status(folder,scene_id)

@app.get('/api/project/{project_id}/scene/{scene_id}/video')
def scene_video(project_id:str,scene_id:str,profile:str='quality'):
    profile=profile if profile in ('fast','quality','main') else 'quality'
    p,folder=load_project(project_id); v=folder/'renders'/safe_name(scene_id)/f'{profile}.mp4'
    if not v.exists(): raise HTTPException(404,'Preview not rendered yet')
    return FileResponse(v,media_type='video/mp4',filename=f'{scene_id}_{profile}.mp4')

@app.post('/api/demo/create')
def demo_create():
    p=create_demo_project(); save_project(p)
    return {'ok':True,'project':p.model_dump(),'manifest':story_manifest(p)}

@app.get('/api/demo/{project_id}/manifest')
def demo_manifest(project_id:str):
    p,folder=load_project(project_id)
    return JSONResponse(story_manifest(p))

@app.post('/api/demo/{project_id}/render')
def demo_render(project_id:str,profile:str='quality'):
    p,folder=load_project(project_id)
    return JSONResponse(start_demo_movie(p,folder,profile))

@app.get('/api/demo/{project_id}/status')
def demo_movie_status(project_id:str):
    p,folder=load_project(project_id)
    return JSONResponse(demo_status(folder))

@app.get('/api/demo/{project_id}/video')
def demo_movie_video(project_id:str):
    p,folder=load_project(project_id)
    v=folder/'demo_movie'/'LAST_SIGNAL_30s.mp4'
    if not v.exists(): raise HTTPException(404,'Demo movie not rendered yet')
    return FileResponse(v,media_type='video/mp4',filename='LAST_SIGNAL_30s.mp4')


@app.post('/api/graphic-demo/create')
def graphic_demo_create():
    p=create_graphic_demo_project(); save_project(p)
    return {'ok':True,'project':p.model_dump(),'manifest':graphic_manifest(p)}

@app.get('/api/graphic-demo/{project_id}/manifest')
def graphic_demo_manifest(project_id:str):
    p,folder=load_project(project_id)
    return JSONResponse(graphic_manifest(p))

@app.post('/api/graphic-demo/{project_id}/render')
def graphic_demo_render(project_id:str,profile:str='quality'):
    p,folder=load_project(project_id)
    return JSONResponse(start_graphic_novel_movie(p,folder,profile))

@app.get('/api/graphic-demo/{project_id}/status')
def graphic_demo_status(project_id:str):
    p,folder=load_project(project_id)
    return JSONResponse(graphic_status(folder))

@app.get('/api/graphic-demo/{project_id}/video')
def graphic_demo_video(project_id:str,profile:str='quality'):
    profile=profile if profile in ('fast','quality','main') else 'quality'
    p,folder=load_project(project_id)
    v=folder/'graphic_novel'/f'LAST_SIGNAL_graphic_novel_{profile}.mp4'
    if not v.exists(): raise HTTPException(404,'Graphic-novel movie not rendered yet')
    return FileResponse(v,media_type='video/mp4',filename=v.name)

@app.get('/api/graphic-demo/{project_id}/panel/{scene_id}')
def graphic_demo_panel(project_id:str,scene_id:str,profile:str='quality'):
    profile=profile if profile in ('fast','quality','main') else 'quality'
    p,folder=load_project(project_id)
    scene=next((s for s in p.scenes if s.id==scene_id),None)
    if not scene: raise HTTPException(404,'Scene not found')
    path=folder/'graphic_novel'/f'{scene_id}_{profile}.png'
    if not path.exists(): render_panel(scene,path,profile)
    return FileResponse(path,media_type='image/png',filename=path.name)

@app.get('/api/health')
def health(): return {'ok':True,'version':'0.7.0','login':False,'blender':bool(find_blender())}
