"""Python dosyalarının yerel, yönlü import dizinini üretir (harici servis yok)."""
import argparse
import ast
import json
import subprocess
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def index(root):
    paths = sorted(set(subprocess.check_output(
        ['git','ls-files','-z','--cached','--others','--exclude-standard','--','*.py'],cwd=root
    ).decode().split('\0')) - {''})
    paths = [p for p in paths if (root/p).is_file()]; names = {}
    for p in paths:
        m=p[:-3].replace('/','.'); names[m.removesuffix('.__init__')]=p
    edges = {p:{} for p in paths}
    for p in paths:
        with tokenize.open(root/p) as f: tree=ast.parse(f.read(),filename=p)
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): mods=[a.name for a in n.names]
            elif isinstance(n,ast.ImportFrom):
                pkg=p.split('/')[:-1];base=n.module or ''
                if n.level: base='.'.join(filter(None,[*pkg[:len(pkg)-n.level+1], base]))
                mods=[f'{base}.{a.name}' if f'{base}.{a.name}' in names else base for a in n.names]
            else: continue
            for mod in mods:
                target=names.get(mod)
                if target and p!=target: edges[p].setdefault(target,set()).add(n.lineno)
    return {p:{q:sorted(nums) for q,nums in sorted(refs.items())} for p,refs in edges.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Yazmadan, kayıtlı gezginin güncelliğini doğrula.')
    args = parser.parse_args()
    data = index(ROOT)
    target = ROOT / 'docs/mimari/DOSYA_HARITASI.html'
    page='''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Formation-Bot · Dosya haritası</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f5f6f3;color:#163236;font:16px system-ui}main{max-width:1100px;margin:auto;padding:24px}h1{font-size:2rem}header,p{max-width:76ch}select,input{font:inherit;padding:.6em;max-width:100%;margin:.2em 0}input{width:25em}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}section{background:white;border:1px solid #ccd8d4;border-radius:8px;padding:16px;min-width:0}button{display:block;overflow-wrap:anywhere;text-align:left;background:none;border:0;color:#046b63;padding:4px 0;cursor:pointer;font:inherit}button:hover{text-decoration:underline}small{color:#506365}h2{overflow-wrap:anywhere}@media(max-width:650px){.grid{grid-template-columns:1fr}}</style>
<main><header><small>MİMARİ DİZİN · OFFLINE</small><h1>Bu dosya neye bağlı?</h1><p>PATHCOUNT Python dosyası · EDGECOUNT yönlü yerel import bağı. Dosya adını arayın; bir komşuya tıklayarak iz sürün. Satır numarası importun yazıldığı dosyaya aittir. Test ve araştırma dosyaları dahildir. Import, çalışma anındaki çağrı veya Telegram teslimi demek değildir.</p></header>
<label>Dosya ara<br><input id="q" placeholder="örn. domain_alarm, runner, notifier"></label><br><select aria-label="Eşleşen dosyalar" id="files"></select><h2 id="title"></h2><div class="grid"><section><h3>Kullandığı dosyalar →</h3><div id="outgoing"></div></section><section><h3>← Bu dosyayı kullananlar</h3><div id="incoming"></div></section></div></main>
<script>const graph=PAYLOAD,paths=Object.keys(graph);const by=id=>document.getElementById(id);function options(){let list=paths.filter(p=>p.toLowerCase().includes(by('q').value.toLowerCase()));by('files').replaceChildren(...list.map(p=>new Option(p,p)));return list}function links(id,entries){let el=by(id);el.replaceChildren();if(!entries.length)el.textContent='Yerel, statik import bulunmadı.';for(let [p,lines] of entries){let b=document.createElement('button');b.textContent=p+' · L'+lines.join(', ');b.onclick=()=>jump(p);el.append(b)}}function show(p){by('title').textContent=p||'Eşleşme yok';links('outgoing',Object.entries(graph[p]||{}));links('incoming',p?paths.filter(x=>graph[x][p]).map(x=>[x,graph[x][p]]):[])}function jump(p){by('q').value='';options();by('files').value=p;show(p)}by('q').oninput=()=>show(options()[0]);by('files').onchange=e=>show(e.target.value);jump('bot/domain_alarm_service.py');</script></html>'''
    page=page.replace('PATHCOUNT',str(len(data))).replace('EDGECOUNT',str(sum(map(len,data.values())))).replace('PAYLOAD',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c'))
    if args.check:
        if not target.is_file() or target.read_text(encoding='utf8') != page:
            raise SystemExit('Dosya gezgini eksik veya eski. Yenile: python scripts/dosya_haritasi.py')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page, encoding='utf8')
    print(f'{len(data)} Python dosyası · {sum(map(len, data.values()))} yerel import bağı · {target.name}')


if __name__=='__main__': main()
