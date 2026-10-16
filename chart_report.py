"""Self-contained, read-only chart detail export. No SaaS server or live fetch."""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from chart_experience import date_text, finite
from reporting.format import sayi


def esc(value):
    return html.escape(str(value if value is not None else "—"), quote=True)


def number(value):
    value = finite(value)
    return sayi(value) if value is not None else "—"


def render_report(meta, images):
    """Escaped data-only tables; no native engine object or filesystem paths."""
    detail = meta.get("ayrinti") or {}
    trust = detail.get("guven") or {}
    zones = []
    for z in detail.get("bolgeler", []):
        history = bool(z.get("tamamlandi")) or z.get("durum") in {
            "REACTION", "FULL_FILL", "INVALID", "SUPERSEDED", "EXPIRED", "CONTINUATION_CONFIRMED"}
        zones.append('<tr data-history="' + str(history).lower() + '">' + ''.join('<td>' + esc(v) + '</td>' for v in (
            str(z.get("tip", "")).upper() + (" ↑" if z.get("yon", 0) > 0 else " ↓"),
            number(z.get("alt")) + "–" + number(z.get("ust")),
            z.get("durum_etiketi"), date_text(z.get("zaman")),
            z.get("konum"), number(z.get("sinir_mesafe_atr")),
            number(z.get("merkez_mesafe_atr")), number(z.get("mitigated_percentage")),
            z.get("gorunum_nedeni"), z.get("kayit_kaynagi"))) + '</tr>')
    translations = {"BOS": "BOS · yapı kırılımı", "CHOCH": "CHoCH · karakter değişimi",
                    "SWEEP": "likidite süpürmesi", "FALSE_BREAK": "başarısız kırılım",
                    "TRANSITION_FAIL": "geçiş başarısız", "CONFIRMED": "teyitli",
                    "PENDING": "bekliyor", "VALID": "geçerli", "INVALID": "geçersiz",
                    "CURRENT": "güncel kayıt", "SUPERSEDED": "yerini yenisi aldı"}
    timeline = []
    for e in detail.get("olaylar", []):
        timeline.append('<tr>' + ''.join('<td>' + esc(v) + '</td>' for v in (
            date_text(e.get("zaman")), translations.get(str(e.get("tur")), e.get("tur")),
            {"UP": "yukarı", "DOWN": "aşağı", "ust": "yukarı", "alt": "aşağı"}.get(e.get("yon"), e.get("yon")),
            number(e.get("seviye")), str(e.get("yas")) + " mum" if e.get("yas") is not None else "bilinmiyor",
            translations.get(e.get("teyit"), e.get("teyit")),
            translations.get(e.get("gecerlilik"), e.get("gecerlilik")),
            translations.get(e.get("guncellik"), e.get("guncellik")))) + '</tr>')
    levels = []
    roles = {"PROTECTED_HIGH": "korunan tepe", "PROTECTED_LOW": "korunan dip",
             "WEAK_HIGH": "zayıf tepe", "WEAK_LOW": "zayıf dip"}
    for level in detail.get("seviyeler", []):
        levels.append('<tr>' + ''.join('<td>' + esc(v) + '</td>' for v in (
            level.get("etiket"), roles.get(level.get("rol"), level.get("rol")),
            number(level.get("fiyat")), date_text(level.get("zaman")),
            "gösteriliyor" if level.get("gorunur") else "odak dışında / bağlamda")) + '</tr>')
    motor = ''.join('<li><strong>' + esc(d.get('ad')) + ':</strong> ' + esc(d.get('etiket')) + '</li>'
                    for d in (trust.get('motorlar') or {}).values())
    tabs, figures = [], []
    for index, (label, png) in enumerate(images.items()):
        tabs.append(f'<button type="button" data-view="{index}" aria-pressed="{str(index == 0).lower()}">{esc(label)}</button>')
        figures.append(f'<figure id="view-{index}"' + (' hidden' if index else '') + '><a download="grafik.png" href="data:image/png;base64,'
                       + base64.b64encode(png).decode() + '"><img alt="' + esc(label) + '" src="data:image/png;base64,'
                       + base64.b64encode(png).decode() + '"></a><figcaption>Özgün PNG’yi indirmek için grafiğe dokunun. Küçük ekranda yatay kaydırabilir veya Mobil görünümü açabilirsiniz.</figcaption></figure>')
    def table(headers, rows, empty):
        return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + esc(h) + '</th>' for h in headers) + '</tr></thead><tbody>' + (''.join(rows) if rows else '<tr><td colspan="' + str(len(headers)) + '">' + esc(empty) + '</td></tr>') + '</tbody></table></div>'
    payload = json.dumps(detail, ensure_ascii=False, indent=2, allow_nan=False)
    return '''<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Grafik ayrıntısı</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#0f151c;color:#e9eef5;font:16px/1.65 system-ui,sans-serif}main{max-width:1250px;margin:auto;padding:28px 20px}h1{font-size:32px;line-height:1.3}h2{margin-top:38px}p,li{color:#b7c5d3}.trust{padding:16px;border-left:4px solid #e0b96a;background:#1b2430}.trust strong{color:#f3d694}nav{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}button,input,select{font:inherit;color:inherit;border:1px solid #415063;border-radius:7px;background:#1c2a38;padding:9px 14px}button{cursor:pointer}button[aria-pressed=true]{border-color:#42cba6;background:#20443e}figure{margin:0;overflow:auto}figure img{display:block;width:100%;height:auto;min-width:720px}figure figcaption{font-size:13px;color:#93a1b1}figure:last-of-type img{min-width:0;max-width:780px;margin:auto}a{color:#62cbb6}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #344152;padding:11px;text-align:left;vertical-align:top;min-width:100px}th{background:#1c2a38}tr[hidden]{display:none}details{margin:24px 0}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}ul{padding-left:22px}.filters{display:flex;gap:12px;flex-wrap:wrap;align-items:center}small{color:#93a1b1}section{scroll-margin-top:20px}@media(max-width:600px){main{padding:18px 12px}h1{font-size:25px}input{width:100%}}
</style></head><body><main><h1>''' + esc(detail.get('sembol')) + ' · ' + esc(detail.get('tf')) + ''' — grafik ayrıntısı</h1><div class="trust"><strong>''' + esc(trust.get('etiket', 'Güncellik bilinmiyor')) + '''</strong><p>Analiz zamanı: ''' + esc(date_text(trust.get('analiz_zamani'))) + '<br>Son mum etiketi: ' + esc(date_text(trust.get('son_mum_etiketi'), daily=detail.get('tf') in {'1d', '1g'})) + '<br>Kaynak: ' + esc(trust.get('kaynak', 'bilinmiyor')) + ' · ' + esc(trust.get('mum_sayisi')) + ''' mum</p><small>Bu dosya sabit bir analiz anını gösterir; kendiliğinden güncellenmez. Yeni render yeni piyasa verisi demek değildir.</small></div><ul>''' + motor + '''</ul><nav><a href="#zones">Bölge ayrıntıları</a><a href="#timeline">Dış olay zaman çizelgesi</a></nav><nav>''' + ''.join(tabs) + '</nav>' + ''.join(figures) + '''<section id="zones"><h2>Bölge ayrıntıları</h2><p>Fiyatın bölge içinde olduğu durumda sınıra uzaklık 0 ATR’dir. Merkez uzaklığı ayrı ölçümdür. Dolum yüzdesi başarı ihtimali değildir. Gizlenen bölgeler aşağıda korunur.</p><div class="filters"><label>Bölgeler <select id="zone-state"><option value="all">Tümü</option><option value="active">Aktif / aday</option><option value="history">Geçmiş / tamamlanmış</option></select></label><input id="zone-search" type="search" placeholder="Bölge ara: FVG, geçersiz, tarih…" aria-label="Bölge ara"></div><div id="zone-table">''' + table(
        ['Tür / oluşum yönü', 'Tam fiyat aralığı', 'Durum', 'Oluşum', 'Fiyat bölgeye göre', 'Sınır uzaklığı / ATR', 'Merkez uzaklığı / ATR', 'OB dolum %', 'Görünüm nedeni', 'Kayıt kaynağı'], zones, 'Bu snapshot’ta kullanılabilir bölge kaydı yok.') + '''</div></section><section id="timeline"><h2>Dış olay zaman çizelgesi</h2><p>Yalnız dış yapı olayları. Teyit, geçerlilik ve güncellik ayrı alanlardır; eski olaylar güncel alarm değildir. Kritik seviye son seçilen dış BOS/CHoCH referansıdır; otomatik stop veya hedef değildir.</p>''' + table(
        ['Olay zamanı', 'Olay', 'Yön', 'Referans fiyat', 'Yaş', 'Teyit', 'Geçerlilik', 'Güncellik'], timeline, 'Bu snapshot’ta dış olay geçmişi yok.') + '''</section><section><h2>Dış yapı seviyeleri</h2><p>Odak görünümünde ölçeği sıkıştırmamak için gizlenen uzak seviyeler de burada korunur.</p>''' + table(['Etiket', 'Rol', 'Tam fiyat', 'Kaynak zamanı', 'Görünüm'], levels, 'Dış yapı seviye kaydı yok.') + '''</section><h2>Nasıl okunur?</h2><ul>''' + ''.join('<li>' + esc(v) + '</li>' for v in (detail.get('sozluk') or {}).values()) + '''</ul><details><summary>Taşınabilir analiz verisi (JSON)</summary><pre>''' + esc(payload) + '''</pre></details><p><small>Yalnız sunum katmanı. Motorlar yeniden yorumlanmaz; kalibre edilmiş başarı olasılığı üretilmez. Eski snapshot’larda kaydedilmemiş ayrıntılar bilinmiyor olarak kalır.</small></p></main><script>
document.querySelectorAll('button[data-view]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('figure[id^="view-"]').forEach(fig=>{fig.hidden=fig.id!=='view-'+button.dataset.view;});document.querySelectorAll('button[data-view]').forEach(other=>other.setAttribute('aria-pressed',String(other===button)));}));
function filterZones(){const state=document.getElementById('zone-state').value;const query=document.getElementById('zone-search').value.toLocaleLowerCase('tr');document.querySelectorAll('#zone-table tbody tr[data-history]').forEach(row=>{const history=row.dataset.history==='true';row.hidden=(state==='active'&&history)||(state==='history'&&!history)||!row.textContent.toLocaleLowerCase('tr').includes(query);});}
document.getElementById('zone-state').addEventListener('change',filterZones);document.getElementById('zone-search').addEventListener('input',filterZones);
</script></body></html>'''


def write_report(path, snapshot, tf, options, current_path, current_meta):
    """Render alternate view/mobile from SAME snapshot, embed and clean temp PNGs."""
    import grafik
    images = {str((current_meta.get('gorunum') or {}).get('mod', 'odak')).capitalize(): Path(current_path).read_bytes()}
    temporary = []
    try:
        mode = (current_meta.get('gorunum') or {}).get('mod', 'odak')
        for label, overrides in [('Bağlam' if mode in {'odak', 'sade'} else 'Odak', {'gorunum': 'baglam' if mode in {'odak', 'sade'} else 'odak'}),
                                 ('Mobil', {'mobil': True, 'gorunum': 'odak'})]:
            target = grafik.kare_yolu(snapshot.get('sembol'), tf)
            temporary.append(target)
            png, _ = grafik.ciz(snapshot, tf, {**options, **overrides, 'sade': False, 'cikti': target})
            if png:
                images[label] = Path(png).read_bytes()
        target = Path(path)
        grafik._atom_yaz(str(target), render_report(current_meta, images).encode('utf-8'))
    finally:
        for target in temporary:
            Path(target).unlink(missing_ok=True)
    return str(path)
