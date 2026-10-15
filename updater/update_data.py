#!/usr/bin/env python3
"""Manual, fail-closed wiki refresh. Run from any directory; never executes source code."""
from __future__ import annotations
import argparse, copy, hashlib, io, json, math, os, re, shutil, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
import urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from lxml import html
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://dontstarve.wiki.gg'
DIRECTORIES = ['/wiki/Dishes', '/wiki/Portable_Crock_Pot', '/wiki/Portable_Crock_Pot/DST']
FIELDS = {'hunger':'hungerRestored','health':'hpRestored','sanity':'sanityRestored',
          'cook':'cooktime','perish':'spoil','priority':'priority'}
class UpdateError(Exception): pass

def now(): return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else copy.deepcopy(default)
def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,path)
def stable_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def text(el): return ' '.join(' '.join(el.itertext()).split())
def rich(el):
    el=html.fromstring(html.tostring(el))
    for im in el.xpath('.//img'):
        a=im.getparent();label=a.get('title') or im.get('alt','').removesuffix('.png')
        span=html.Element('span');span.text=' '+label+' ';span.tail=im.tail;a.replace(im,span)
    return text(el)
def norm(s): return re.sub(r'[^a-z0-9]','',s.lower())
def source_path(url):
    u=urllib.parse.urlsplit(urllib.parse.urljoin(BASE,url))
    if u.scheme!='https' or u.netloc!='dontstarve.wiki.gg' or not u.path.startswith('/wiki/'):
        raise UpdateError('资料链接不在允许的 Wiki 域名内')
    return urllib.parse.quote(urllib.parse.unquote(u.path),safe='/')
def original(src):
    u=urllib.parse.urlsplit(urllib.parse.urljoin(BASE,src))
    if u.netloc!='dontstarve.wiki.gg' or not u.path.startswith('/images/'):
        raise UpdateError('图片地址不在 Wiki 图片目录内')
    path=u.path
    if '/thumb/' in path:path=path.replace('/thumb/','/').rsplit('/',1)[0]
    return urllib.parse.urlunsplit(('https',u.netloc,path,u.query,''))
def grid(table):
    out=[];spans={}
    for tr in table.xpath('.//tr'):
        row=[];col=0
        def occupied():
            nonlocal col
            while col in spans:
                el,left=spans[col];row.append(el)
                if left>1:spans[col]=(el,left-1)
                else:del spans[col]
                col+=1
        for cell in tr.xpath('./td|./th'):
            occupied()
            for _ in range(int(cell.get('colspan',1))):
                row.append(cell)
                if int(cell.get('rowspan',1))>1:spans[col]=(cell,int(cell.get('rowspan'))-1)
                col+=1
        occupied();out.append(row)
    return out

def parse_directory(raw, path):
    doc=html.fromstring(raw);result={}
    for table in doc.xpath('//table'):
        rows=grid(table)
        if not rows or not any('Dish' in text(c) for c in rows[0]):continue
        for cells in rows[1:]:
            if len(cells)<9:continue
            links=cells[1].xpath('.//a[starts-with(@href,"/wiki/")]')
            if not links:continue
            p=source_path(links[0].get('href'));v=rich(cells[2]) if path=='/wiki/Dishes' else ''
            result[p]={'pot':'普通烹饪锅' if path=='/wiki/Dishes' else '沃利便携锅',
                       'version':'DST 联机版' if path.endswith('/DST') or ('Together' in v and not any(x in v for x in ['Shipwrecked','Hamlet','Reign'])) else 'DS 单机 / DLC（版本待核对）'}
    if not result:raise UpdateError('目录结构发生变化或页面无有效食谱：'+path)
    return result

def parse_page(raw, path):
    doc=html.fromstring(raw)
    boxes=doc.xpath('//aside[contains(@class,"portable-infobox")]')
    contents=doc.xpath('//div[@id="mw-content-text"]')
    if not boxes or not contents:raise UpdateError('食谱页面结构无法识别：'+path)
    box=boxes[0];content=contents[0]
    def value(key):
        nodes=box.xpath('.//*[@data-source=$key]',key=key)
        vals=[n for n in nodes if 'pi-data-value' in n.get('class','')]
        if not vals:
            vals=[v for n in nodes for v in n.xpath('.//*[contains(@class,"pi-data-value")]')]
        return rich(vals[0]) if vals else ''
    names=box.xpath('.//*[@data-source="Box title"]')
    if not names:raise UpdateError('食谱名称缺失：'+path)
    name=text(names[0]).removesuffix('Normal').strip()
    def tables(section):
        found=content.xpath('.//*[@id=$sec]',sec=section)
        if not found:return []
        node=found[0]
        if node.tag not in ['h2','h3']:node=node.getparent()
        node=node.getnext();out=[]
        while node is not None and node.tag not in ['h2','h3']:
            out.extend([node] if node.tag=='table' else node.xpath('.//table'));node=node.getnext()
        return out
    def item(im):
        return {'en':im.getparent().get('title') or im.get('alt','').removesuffix('.png'),'url':original(im.get('src',''))}
    rule_tables=tables('Recipe');rule=' '.join(rich(t) for t in rule_tables)
    ingredients=[]
    for t in rule_tables:
        for tr in t.xpath('.//tr'):
            for c in tr.xpath('./td'):
                if c.xpath('.//a[contains(@href,"Crock_Pot")]'):break
                ingredients.extend(item(im) for im in c.xpath('.//img'))
    if not rule:rule=value('foodRecipe')
    examples=[]
    for t in tables('Examples'):
        for tr in t.xpath('.//tr'):
            cells=tr.xpath('./td');split=next((i for i,c in enumerate(cells) if c.xpath('.//a[contains(@href,"Crock_Pot")]')),None)
            if split is None:continue
            items=[]
            for c in cells[:split]:
                ims=c.xpath('.//img')
                if ims:items.extend(item(im) for im in ims)
                elif items:
                    q=re.search(r'[×x]\s*(\d+)',text(c))
                    if q:items.extend([dict(items[-1]) for _ in range(int(q.group(1))-1)])
            if len(items)==4:examples.append({'items':items,'note_en':' '.join(rich(c) for c in cells[split+2:])})
    leads=[]
    for p in content.xpath('./div/p|./p'):
        z=rich(p)
        if len(z)>60 and any(x in z.lower() for x in ['recipe','cooked','made','requires','ingredient']):leads.append(z)
        if len(leads)==4:break
    icons=box.xpath('.//*[@data-source="icon"]//img/@src')
    if not icons:raise UpdateError('成品图标缺失：'+path)
    variants=[]
    for href in content.xpath('.//a/@href'):
        if href.startswith(path+'/') and href.rsplit('/',1)[-1] in ['DST','RoG','SW','Hamlet','Ham']:variants.append(source_path(href))
    revision=re.search(r'"wgRevisionId"\s*:\s*(\d+)',raw.decode('utf-8',errors='replace') if isinstance(raw,bytes) else raw)
    return {'name':name,'stats':{key:value(src) for key,src in FIELDS.items()},'type':value('foodType'),
            'rule':rule,'lead':leads,'ingredients':ingredients,'examples':examples,'icon':original(icons[0]),
            'revision':revision.group(1) if revision else '', 'variants':sorted(set(variants))}

def numeric(raw, field):
    z=raw.replace('−','-').replace(',','')
    if re.match(r'\s*(?:N/?A|Never|None|Not applicable|Does not spoil|Not edible|—|∞)',z,re.I):return None
    m=re.match(r'\s*([+-]?\d+(?:\.\d+)?)',z)
    if not m:raise UpdateError('无法可靠解析参数 '+field+'：'+raw)
    n=float(m.group(1))
    if not math.isfinite(n):raise UpdateError('非有限数值')
    if field=='perish' and 'second' in z.lower():n/=480
    elif field=='perish' and re.search(r'\bmin(?:ute)?s?\b',z,re.I):n=n*60/480
    return n

class Network:
    def __init__(self, delay=0.5):self.delay=delay;self.guard=threading.Lock();self.next_request=0
    def __call__(self, url, image=False):
        u=urllib.parse.urlsplit(url)
        if u.scheme!='https' or u.netloc!='dontstarve.wiki.gg':raise UpdateError('不允许抓取该域名')
        with self.guard:
            wait=max(0,self.next_request-time.monotonic())
            if wait:time.sleep(wait)
            self.next_request=time.monotonic()+self.delay
        req=urllib.request.Request(url,headers={'User-Agent':'PersonalCrockPotAtlas/2.0 (manual refresh; low request rate)','Accept':'image/*' if image else 'text/html'})
        try:
            with urllib.request.urlopen(req,timeout=35) as res:
                if urllib.parse.urlsplit(res.url).netloc!='dontstarve.wiki.gg':raise UpdateError('资料源跳转到非允许域名')
                data=res.read(12*1024*1024+1)
                if len(data)>12*1024*1024:raise UpdateError('响应过大')
        except (OSError,urllib.error.HTTPError,urllib.error.URLError) as e:
            raise UpdateError('资料源访问失败，可能为网络故障或访问限制：'+str(e)) from e
        if not image and b'mw-content-text' not in data:raise UpdateError('资料源未返回 Wiki 正文，可能是验证页面')
        return data

class Updater:
    def __init__(self, root=ROOT, fetch=None, progress=None):
        self.root=Path(root);self.private=self.root/'.updates';self.fetch=fetch or Network();self.progress=progress or (lambda s:None)
    def status(self):return read_json(self.private/'status.json',read_json(self.root/'updater/initial_status.json',{'lastUpdatedAt':None,'lastCheckedAt':None,'lastSuccessfulRunAt':None,'dataDate':'2026-10-14'}))
    def run(self):
        self.private.mkdir(exist_ok=True)
        lock=self.private/'update.lock'
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:raise UpdateError('另一个更新任务正在运行；若上次被强制关闭，请确认无任务后删除 .updates/update.lock')
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        status=self.status();status.update(runId=str(time.time_ns()),lastAttemptAt=now(),state='running',message='正在检查资料源');atomic_json(self.private/'status.json',status)
        try:
            result=self._run(status)
            status.update(lastSuccessfulRunId=status['runId'],state='success',lastCheckedAt=now(),lastSuccessfulRunAt=now(),message=result['message'],lastResult=result)
            if result['changed']:status.update(lastUpdatedAt=now(),dataDate=now()[:10])
            atomic_json(self.private/'status.json',status)
            self._log({'time':now(),'success':True,**result})
            return status
        except Exception as e:
            status.update(state='failed',message=str(e));atomic_json(self.private/'status.json',status)
            self._log({'time':now(),'success':False,'error':str(e)})
            raise
        finally:lock.unlink(missing_ok=True)
    def _log(self, result):
        with (self.private/'history.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(result,ensure_ascii=False)+'\n')
    def _run(self,status):
        old=read_json(self.root/'recipes.json');base=read_json(self.root/'updater/source_baseline.json',{})
        labels=read_json(self.root/'updater/labels.json',{});catalog=read_json(self.root/'updater/item_catalog.json',{})
        overrides=read_json(self.root/'updater/overrides.json',{});by_path={r['path']:r for r in old}
        found={};live={};warnings=[]
        for path in DIRECTORIES:
            self.progress('读取食谱目录：'+path);found.update(parse_directory(self.fetch(BASE+path),path))
        # Never silently remove existing entries; require each existing page to remain readable.
        queue=list(dict.fromkeys(list(by_path)+list(found)))
        with ThreadPoolExecutor(max_workers=3) as pool:
            def get_page(path):
                return parse_page(self.fetch(BASE+path),path)
            while queue:
                batch=[]
                while queue and len(batch)<3:
                    path=queue.pop(0)
                    if path not in live:batch.append(path)
                futures=[pool.submit(get_page,path) for path in batch]
                for path,future in zip(batch,futures):
                    self.progress(f'读取食谱详情 {len(live)+1}：{path}')
                    snapshot=future.result();live[path]=snapshot
                    for variant in snapshot['variants']:
                        if variant not in live and variant not in queue and variant not in batch:
                            queue.append(variant);found.setdefault(variant,{'pot':found.get(path,{}).get('pot','普通烹饪锅'),'version':'DST 联机版' if variant.endswith('/DST') else 'DS 单机 / DLC（版本待核对）'})
                    if len(live)>600:raise UpdateError('目录条目异常增多，停止更新以保护现有数据')
        if len(live)<len(by_path):raise UpdateError('抓取不完整，保留旧数据')
        stage=self.private/('staging-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'));stage.mkdir()
        images={};new_catalog=copy.deepcopy(catalog)
        old_item_urls={}
        for snapshot in base.values():
            for it in snapshot['ingredients']+[i for e in snapshot['examples'] for i in e['items']]:
                old_item_urls.setdefault(it['en'],set()).add(it['url'])
        def image_file(url, previous=None, force=False):
            # For existing unchanged icon identity, preserve a verified local original asset.
            if previous and not force and (self.root/previous['file']).is_file():return previous
            if url in images:return images[url]
            payload=self.fetch(url,image=True)
            try:
                im=Image.open(io.BytesIO(payload));im.load()
                if im.width<16 or im.height<16 or im.width>4096 or im.height>4096:raise ValueError('图片尺寸异常')
                name='assets/wiki_'+hashlib.sha256(payload).hexdigest()[:24]+'.png'
                target=stage/name;target.parent.mkdir(exist_ok=True);im.save(target,format='PNG')
                value={'file':name,'width':im.width,'height':im.height,'source':url}
            except Exception as e:raise UpdateError('图片下载或校验失败：'+url+' '+str(e)) from e
            images[url]=value;return value
        def translate_item(it):
            en=it['en'];known=catalog.get(en)
            if not known:
                known=next((v for k,v in catalog.items() if norm(k)==norm(en)),None)
            if known and (self.root/known['image']['file']).is_file():
                out=copy.deepcopy(known);out.update(en=en,url=it['url'],zh=labels.get(en,known['zh']))
                if en in old_item_urls and it['url'] not in old_item_urls[en]:out['image']=image_file(it['url'])
                return out
            zh=labels.get(en,'待译：'+en)
            if en not in labels:warnings.append('材料中文名待核对：'+en)
            out={**it,'zh':zh,'image':image_file(it['url'])};new_catalog[en]=out;return out
        changed=[];added=[];pending=[];result=[]
        try:
            for path,s in live.items():
                previous=by_path.get(path);before=base.get(path)
                if previous and before and stable_hash({k:v for k,v in s.items() if k not in ['revision','variants']})==stable_hash({k:v for k,v in before.items() if k not in ['revision','variants']}):
                    r=copy.deepcopy(previous);r['revision']=s['revision'] or r.get('revision','')
                else:
                    r=copy.deepcopy(previous) if previous else {'id':len(old)+len(added),'path':path,'source':BASE+path,'name':s['name'],
                      'zh':labels.get(s['name'],'待译：'+s['name']),**found.get(path,{'pot':'普通烹饪锅','version':'DS 单机 / DLC（版本待核对）'}),
                      'healthDelayed':0,'sanityDelayed':0,'hungerDelayed':0,'effect':'','characterNote':'','targetStats':''}
                    if not previous:
                        added.append(path)
                        if s['name'] not in labels:warnings.append('料理中文名待核对：'+s['name'])
                    for key in FIELDS:
                        raw=s['stats'][key]
                        if raw:r[key]=numeric(raw,key)
                        elif previous and key in previous:r[key]=previous[key]
                        else:raise UpdateError('缺少关键参数 '+key+'：'+path)
                    for stat in ['health','sanity','hunger']:
                        delayed=re.search(r'\+\s*([0-9]+(?:\.[0-9]+)?)\s+over\s+',s['stats'][stat],re.I)
                        r[stat+'Delayed']=float(delayed.group(1)) if delayed else 0
                    r['sourceStats']=s['stats']
                    if r['name']=='Milkmade Hat':r['perish']=None
                    if r['name'] in ['Amberosia','Beefalo Treats','Steamed Twigs','Milkmade Hat']:
                        r['hunger']=r['health']=r['sanity']=None
                    r['type']=s['type'] or r.get('type','');r['meat']=bool(re.search(r'\bMeat\b',r['type']))
                    r['edible']=r['name'] not in ['Amberosia','Beefalo Treats','Steamed Twigs','Milkmade Hat']
                    r['typeZh']='肉类' if r['meat'] else '非角色食物' if not r['edible'] else '点心' if 'Goodies' in r['type'] else '素食' if 'Veggie' in r['type'] else '一般食物'
                    r['healthTotal']=None if r['health'] is None else r['health']+r.get('healthDelayed',0)
                    r['sanityTotal']=None if r['sanity'] is None else r['sanity']+r.get('sanityDelayed',0)
                    recipe_changed=not previous or not before or any(s[k]!=before.get(k) for k in ['rule','lead','ingredients','examples'])
                    if recipe_changed:
                        if not s['rule'] or not s['ingredients']:raise UpdateError('缺少配方或材料，停止更新：'+path)
                        r['ingredients']=[translate_item(i) for i in s['ingredients']]
                        if s['examples']:
                            r['examples']=[{'items':[translate_item(i) for i in e['items']],'note':e['note_en'],'risk':bool(re.search(r'chance|probability|random|[0-9]+%',e['note_en'],re.I))} for e in s['examples']]
                        else:r['examples']=[]
                        # Visual recipes alone cannot express all priority/exclusion rules. Do not pretend the old translation is current.
                        r['rule']='来源配方已更新，中文条件待核对；请打开详情查看最新原文。'
                        r['restriction']='以下为资料源原文；图示食物度不等同于完整逻辑条件。'
                        r['sourceRule']=s['rule'];r['sourceLead']='\n\n'.join(s['lead']);r['translationPending']=True
                        r['effect']='效果说明已变动，请核对下方来源原文。';r['characterNote']='角色加成以来源原文为准'
                        pending.append(path)
                    icon_changed=bool(before and s['icon']!=before.get('icon'))
                    r['image']=image_file(s['icon'],previous.get('image') if previous else None,force=icon_changed)
                    r['revision']=s['revision']
                if r['zh'].startswith('待译：') and r['name'] in labels:r['zh']=labels[r['name']]
                for it in r.get('ingredients',[])+[i for e in r.get('examples',[]) for i in e['items']]:
                    if it['en'] in labels:it['zh']=labels[it['en']]
                if path in overrides:
                    allowed={'zh','rule','restriction','effect','healthDelayed','sanityDelayed','hungerDelayed','version','pot','characterNote','targetStats'}
                    patch=overrides[path]
                    if set(patch)-allowed:raise UpdateError('人工修正含不允许字段：'+path)
                    r.update(patch)
                    if 'rule' in patch:r['translationPending']=False
                    r['healthTotal']=None if r['health'] is None else r['health']+r.get('healthDelayed',0)
                    r['sanityTotal']=None if r['sanity'] is None else r['sanity']+r.get('sanityDelayed',0)
                if previous and stable_hash({k:v for k,v in r.items() if k!='revision'})!=stable_hash({k:v for k,v in previous.items() if k!='revision'}):changed.append(path)
                if not r.get('image') or any(len(e['items'])!=4 for e in r.get('examples',[])):raise UpdateError('输出校验失败：'+path)
                result.append(r)
            for i,r in enumerate(result):r['id']=i
            pending=[r['path'] for r in result if r.get('translationPending')]
            meaningful=bool(changed or added)
            if meaningful:
                self.progress('校验通过，备份并替换数据文件')
                backup=self.private/'backups'/stage.name.removeprefix('staging-');backup.mkdir(parents=True)
                names=['data.js','recipes.json','updater/source_baseline.json','updater/item_catalog.json']
                for name in names:
                    p=self.root/name
                    if p.exists():q=backup/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
                (stage/'recipes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                (stage/'data.js').write_text('window.RECIPES='+json.dumps(result,ensure_ascii=False,separators=(',',':'))+';\nwindow.DATA_UPDATED_AT='+json.dumps(now())+';\n',encoding='utf-8')
                try:
                    for f in (stage/'assets').glob('*') if (stage/'assets').exists() else []:os.replace(f,self.root/'assets'/f.name)
                    # Data.js is the only runtime data file and is replaced atomically, last.
                    os.replace(stage/'recipes.json',self.root/'recipes.json')
                    atomic_json(self.root/'updater/source_baseline.json',live)
                    atomic_json(self.root/'updater/item_catalog.json',new_catalog)
                    os.replace(stage/'data.js',self.root/'data.js')
                except Exception:
                    for name in names:
                        p=backup/name
                        if p.exists():shutil.copyfile(p,self.root/name)
                    raise
            else:atomic_json(self.root/'updater/source_baseline.json',live)
            return {'changed':meaningful,'updated':changed,'added':added,'translationPending':pending,'warnings':sorted(set(warnings)),
                    'recipeCount':len(result),'sourcePages':len(live),'message':f'更新完成：新增 {len(added)} 条，变更 {len(changed)} 条，中文条件待核对 {len(pending)} 条' if meaningful else '检查完成，食谱数据没有变化'}
        finally:shutil.rmtree(stage,ignore_errors=True)

def main():
    parser=argparse.ArgumentParser(description='重新抓取 Wiki，校验后更新本地食谱；失败保留旧数据')
    parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
    try:print(json.dumps(Updater(args.root,progress=lambda s:print(s,flush=True)).run(),ensure_ascii=False,indent=2));return 0
    except Exception as e:print('更新失败：'+str(e),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
