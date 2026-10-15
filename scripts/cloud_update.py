#!/usr/bin/env python3
"""Rehydrate the self-contained atlas, refresh in isolation, then build Pages."""
import argparse, base64, gzip, html, json, os, re, shutil, sys, tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'updater'))
from update_data import Updater, atomic_json, read_json

WORKFLOW='https://github.com/csy-hub/dont-starve-cookbook/actions/workflows/update-cookbook.yml'

def embedded(document, name):
    marker='window.'+name+'='
    start=document.index(marker)+len(marker)
    return json.JSONDecoder().raw_decode(document[start:])[0]

def unpack(root, target):
    document=(root/'index.html').read_text(encoding='utf-8')
    images=embedded(document,'IMAGE_ASSETS');recipes=embedded(document,'RECIPES')
    (target/'assets').mkdir(parents=True);(target/'updater').mkdir()
    for name,uri in images.items():
        if not re.fullmatch(r'assets/[^/\\]+\.(png|svg)',name):raise ValueError('Unsafe asset path')
        (target/name).write_bytes(base64.b64decode(uri.split(',',1)[1],validate=True))
    atomic_json(target/'recipes.json',recipes)
    (target/'data.js').write_text('window.RECIPES='+json.dumps(recipes,ensure_ascii=False)+';',encoding='utf-8')
    for name in ['labels.json','overrides.json','initial_status.json']:
        shutil.copyfile(root/'updater'/name,target/'updater'/name)
    for name in ['source_baseline.json','item_catalog.json']:
        payload=gzip.decompress(base64.b64decode((root/'updater'/(name+'.gz.b64')).read_text()))
        (target/'updater'/name).write_bytes(payload)
    if (root/'update-status.json').exists():atomic_json(target/'.updates/status.json',read_json(root/'update-status.json'))
    return document

def stamp(value):
    return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')+'（北京时间）' if value else '尚无数据变更记录（初始资料：2026-10-14）'

def build(root, target, document, status):
    recipes=read_json(target/'recipes.json');images={}
    if len(recipes)<139 or len({r['path'] for r in recipes})!=len(recipes):raise ValueError('Incomplete or duplicate recipes')
    def verify(value):
        if isinstance(value,dict):
            if 'file' in value and not (target/value['file']).is_file():raise ValueError('Missing recipe image')
            for item in value.values():verify(item)
        elif isinstance(value,list):
            for item in value:verify(item)
    verify(recipes)
    for p in sorted((target/'assets').iterdir()):
        images['assets/'+p.name]='data:'+('image/svg+xml' if p.suffix=='.svg' else 'image/png')+';base64,'+base64.b64encode(p.read_bytes()).decode()
    prefix=document[:document.index('<script>window.IMAGE_ASSETS=')]
    prefix=re.sub(r'<section id="update-panel".*?</section>','',prefix,flags=re.S)
    dst=sum('DST' in r['version'] for r in recipes);count=len(recipes)
    prefix=re.sub(r'默认展示 \d+ 条联机版记录',f'默认展示 {dst} 条联机版记录',prefix)
    prefix=re.sub(r'资料整理于 [\d-]+', '资料整理于 '+status.get('dataDate','2026-10-14'),prefix)
    prefix=re.sub(r'数据抓取：[\d-]+', '数据抓取：'+status.get('dataDate','2026-10-14'),prefix)
    prefix=re.sub(r'\d+ 条联机版 / \d+ 条单机及 DLC 记录',f'<span id="versionCounts">{dst} 条联机版 / {count-dst} 条单机及 DLC 记录</span>',prefix) if 'id="versionCounts"' not in prefix else prefix
    prefix=re.sub(r'共 \d+ 个英文成品名称、\d+ 条版本化记录', '共 <span id="coverageCounts"></span>',prefix) if 'id="coverageCounts"' not in prefix else prefix
    details=status.get('lastResult',{});pending=len(details.get('translationPending',[]))
    panel=f'''<section id="update-panel" aria-label="资料更新" style="margin:20px 0;padding:18px;border:1px solid #746747;border-radius:12px;line-height:1.9;overflow-wrap:anywhere">
<a id="update-source" class="jump-link" href="{WORKFLOW}" target="_blank" rel="noopener">检查并更新资料 ↗</a>
<p style="margin:8px 0">管理员入口：在 GitHub 页面点击 Run workflow，再次点击绿色 Run workflow。需要登录仓库维护者账号；普通访客无需登录查询。</p>
<div>最近成功检查：<time id="last-checked">{html.escape(stamp(status.get('lastCheckedAt')))}</time></div>
<div>最近数据更新：<time id="last-updated">{html.escape(stamp(status.get('lastUpdatedAt')))}</time></div>
<div id="update-result">{html.escape(status.get('message','尚未执行云端检查'))}；中文条件待核对 {pending} 条。</div>
<p style="margin:8px 0 0"><a href="{html.escape(status.get('runUrl') or WORKFLOW)}" target="_blank" rel="noopener">查看执行状态与日志 ↗</a> · <a href="update-history.json" target="_blank">更新历史 ↗</a> · 完成后刷新本页查看结果；失败时保留已发布版本。</p></section>'''
    prefix=prefix.replace('<section class="toolbar">',panel+'<section class="toolbar">')
    app=(root/'scripts/app.js').read_text(encoding='utf-8')
    app='const asset=path=>window.IMAGE_ASSETS[path]||path;\n'+app
    app=app.replace('esc(image.file)','esc(asset(image.file))')
    app=app.replace('src="assets/${key}.png"',"src=\"${esc(asset('assets/'+key+'.png'))}\"")
    app=app.replace('src="assets/crockpot.png"',"src=\"${esc(asset('assets/crockpot.png'))}\"")
    app=app.replace('<a href="${esc(r.image.file)}" target="_blank">打开原图 ↗</a>','<a href="${esc(asset(r.image.file))}" download="${esc(r.name)}.png">下载原图 ↗</a>')
    data='window.RECIPES='+json.dumps(recipes,ensure_ascii=False,separators=(',',':'))+';window.DATA_UPDATED_AT='+json.dumps(status.get('lastUpdatedAt') or status.get('dataDate','2026-10-14'))+';'
    safe=lambda s:s.replace('</script','<\\/script')
    output=prefix+'<script>window.IMAGE_ASSETS='+json.dumps(images,separators=(',',':'))+';</script><script>'+safe(data)+'</script><script>'+safe(app)+'</script></body></html>'
    # Only validated output is copied into the repository; nothing is deployed here.
    (root/'index.html').write_text(output,encoding='utf-8')
    atomic_json(root/'update-status.json',status)
    history=read_json(root/'update-history.json',[])
    if status.get('runId') and (not history or history[-1].get('runId')!=status['runId']):
        history.append({k:status.get(k) for k in ['runId','lastCheckedAt','lastUpdatedAt','message','runUrl','lastResult']})
    atomic_json(root/'update-history.json',history[-30:])
    for name in ['source_baseline.json','item_catalog.json']:
        (root/'updater'/(name+'.gz.b64')).write_text(base64.b64encode(gzip.compress((target/'updater'/name).read_bytes(),mtime=0)).decode())
    site=root/'_site';site.mkdir(exist_ok=True)
    for name in ['index.html','README.txt','IMAGE_LICENSE.txt','image_sources.json','.nojekyll','update-status.json','update-history.json']:
        if (root/name).exists():shutil.copyfile(root/name,site/name)
    return details

def run(root=ROOT, fetch=None, prepare_only=False):
    with tempfile.TemporaryDirectory() as tmp:
        target=Path(tmp);document=unpack(root,target)
        status=Updater(target,fetch=fetch,progress=lambda s:print(s,flush=True)).status() if prepare_only else Updater(target,fetch=fetch,progress=lambda s:print(s,flush=True)).run()
        if not prepare_only:
            status['runUrl']='https://github.com/'+os.environ.get('GITHUB_REPOSITORY','csy-hub/dont-starve-cookbook')+'/actions/runs/'+os.environ.get('GITHUB_RUN_ID','local')
        details=build(root,target,document,status)
        summary='## 食谱资料检查结果\n\n'+status['message']+'\n\n成功检查：'+stamp(status.get('lastCheckedAt'))+'\n\n数据更新：'+stamp(status.get('lastUpdatedAt'))+'\n\n'+json.dumps(details,ensure_ascii=False,indent=2)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write(summary)
        print(summary)
        return status

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare-only',action='store_true');args=parser.parse_args()
    run(prepare_only=args.prepare_only)
