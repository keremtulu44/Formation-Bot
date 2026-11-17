# Grafik ok işaretleri (▲/○) ve genel çizim incelemesi — 2026-11-16

**Soru (kullanıcı):** "Grafikte çizilen ok tarzı şeyler var, bunlar replay'lere göre
ayarlanıyor — bunlara bakar mısın, yorum yap; bir de grafik çizimleri hakkında genel
bir bak."

**Kapsam:** `grafik/` paketinin tamamı (6.926 satır / 11 dosya), özellikle
`grafik/render.py::_stabil_ciz` + `_stabil_katmani`, `grafik/tarama.py::_stabil_verisi`,
`grafik/markers.py`, `grafik/panels.py`, `grafik/overlays.py`; ok kademelerinin kaynağı
olan `docs/arastirma/stabil_ok_replay_2026_11_05/`, `OK_SISTEMI_2026-11-08.md`,
`OK_BAGLAM_DOGRULAMA_VE_UYGULAMA_2026-11-15.md`; motor tarafı
`domain_engines/stabil/{signals,resistance}.py`.

**Bu tur KOD DAVRANIŞI DEĞİŞMEDİ.** Yeni dosyalar: ölçüm betiği
`scripts/grafik_ok_ve_etiket_olcum.py` + sözleşmesi `test_grafik_ok_olcum_betik.py`
(betik sessizce çürüyüp "çakışma yok" güvencesi vermesin). Bulgular ve öneriler
aşağıda. Görseller `docs/gorseller/ok_ve_cizim_inceleme_2026_11_16/`.

## 1. Oklar gerçekten replay'e göre mi ayarlanıyor? — Evet, iki ayrı eksende

Grafikteki `▲` **tek bir işaret değil**; aynı ok üç farklı replay bulgusuna göre
biçim değiştiriyor. Üretim (sinyal) mantığı hiçbirinde değişmiyor — hepsi yalnız
**görsel** kademe.

### 1.1 Tür kademesi (boyut + dolgu) — 555 geçerli ok

`grafik/render.py:1217-1310`, kaynak `stabil_ok_replay_2026_11_05` (174 sembol,
4s, 555 geçerli `▲`; 8 bar MFE < 0,5 ATR = "zayıf tepki"):

| Ok türü (motor) | Replay n | Zayıf tepki | Grafikteki görünüm |
|---|---|---|---|
| `intrabar_sweep_reclaim` | 175 | **%29,6** (en zayıf) | küçük (s=34) + yarı saydam (α 0,55) |
| `multi_bar_recovery` (eski adı `close_reclaim`) | 267 | %23,1 | dolu, normal (s=48) |
| `long_base_breakout` | 63 | %28,6 | içi boş, küçük + soluk (s=44, α 0,60) |
| `upward_rebase_momentum` | 79 | **%17,3** + `+1 ATR önce %58,7` (en güçlü) | içi boş, **büyük** (s=62) |

Tablo **dürüst**: en zayıf tür en soluk, en güçlü tür en iri. Ama kodda
"zayıflık" dört ayrı görsel değişkenle (boyut, dolgu, alfa, kenar kalınlığı)
anlatılıyor; bunların hiçbiri lejantta yazmıyor (§4.1).

### 1.2 Bağlam kademesi (halka) — 2026-11-09 / 11-15, n=186/192/49

`grafik/tarama.py:465-505` + `grafik/render.py:1313-1345`. Sınıf **snapshot'a**
yazılıyor (`stabil["baglam"]`), çizim onu okuyor:

| Sınıf | Tanım | Replay | Görünüm |
|---|---|---|---|
| `guclu` | rebase **veya** (çok mumlu geri alım + `BREACHED_FIXED_SUPPORT`) | %57,5 yönde / %16,1 zayıf (n=186); bootstrap yön farkı **+12,7pp [+1,6, +24,1]** | beyaz **halka** (s=150) |
| `cok_guclu` | `guclu` + (günlük yapı kırık **veya** H4 toparlanma başarısız) | %69 / %10 (n=49); **+16,1pp [~0, +30,8]** | **çift halka** (s=300 + s=170) |
| `zayif` | `HORIZONTAL_AFTER_DROP` zemininde geri alım/süpürme | %44,8 / %30,7 (n=192) | ok **soluklaştırılır** |
| (istisna) | `zayif` + H4 toparlanma başarısız | %62 yönde, n=21, medyan negatif | solukluk kalkar, nötr |

### 1.3 Bastırma (ok hiç doğmuyor)

Dikey destek rejiminde `▲` üretilmez, yerine `▼` yapı uyarısı çizilir
(`domain_engines/stabil/signals.py::vertical_attempt_kind`, `grafik/render.py:1085-1099`).
Replay: bastırılan eski adaylarda `+1 ATR önce %53,4` / `−1 ATR önce %39,4` → **`▼`
düşüş garantisi değil**; lejant da "▼ dönüş = sinyal" diyor, "sat" demiyor. Bu
kısım doğru kurgulanmış.

## 2. Ölçüm — canlı çizim yolunun kendisi üzerinde

`python -m scripts.grafik_ok_ve_etiket_olcum --pencere 200 --png-dizin /tmp/kareler`
(12 sembol/TF, gerçek `backfill_data/` arşivi, gerçek motor, `grafik.ciz`).
Yeni betik, `grafik`'in kendi kalite kapısının **görmediği** şeyi ölçüyor: işaretler
`PathCollection` olduğu için `_mum_cakisma_say` (yalnız `ax.texts`) kapsamı dışında.

| Pencere | İşaret | Kendi mumuna değen | **Komşu muma değen** | Dikey mesafe (medyan) | Tarih etiketi çakışması |
|---|---|---|---|---|---|
| 200 bar — önce | 49 | **0** | **13 (%27)** | 12,1 – 44,7 px | 0 / 12 kare |
| 200 bar — **sonra** | 41 | **0** | 16 (%39) | 12,1 – 25,0 px | 0 / 12 kare |
| 120 bar — önce | 32 | **0** | **7 (%22)** | 12,1 – 56,6 px | **7 / 7 günlük karede 1 çift** (4s'te 0) |
| 120 bar — **sonra** | 29 | **0** | 9 (%31) | 12,1 – 15,4 px | **0** |

Ek enjeksiyon ölçümü (dört kademe + üç bağlam aynı karede, bar aralığı ≈4,4 px):
`çok güçlü` dış halkası **r≈12 px** → **±2–3 barı** kapsıyor; 40. barın halkası
42. ve 43. mumun fitiline değiyor. Tek halka r≈8,5 px (±1 bar).

## 3. Yorum — iyi çalışan yanlar

1. **Kademe yönü doğru.** En zayıf tür en soluk, en güçlü tür en iri; replay
   sayıları kodun içinde gerekçesiyle yazılı (yalnız "böyle olsun" değil).
2. **Sinyal ile görsel ayrık.** `baglam` yalnız çizimi etkiliyor; alarm, kart metni
   ve tarama çıktısı değişmiyor. Bu, "replay gözlemsel, filtre kanıtı değil"
   duruşuyla tutarlı — replay'lerin hiçbiri dış örneklem değil ve `cok_guclu`
   GA'sının alt sınırı sıfıra değiyor.
3. **Kendi mumuna hiç binmiyor (0/49).** Sabit dikey ofset (`0,018 × y_span`)
   mumun dibinin altında tutuyor; gövde/fitil okunurluğu bozulmuyor.
4. **Ok üretimi bastırmada fail-closed.** Dikey rejimde `▲` sızmıyor; seviye değişen
   barda da bastırma var (elle hazırlanmış eski snapshot'ta bile).
5. **Kare üretimi hata toleranslı.** Katman hatası kareyi düşürmüyor ("yalnız mumlar"
   moduna iniyor), beklenen son bar uyuşmazsa hiç çizmiyor.

## 4. Bulgular

### P1 — Lejant çizileni anlatmıyor (repo'nun kendi kuralı §0.12v) — **UYGULANDI**

Karede ok olan bir grafik için üretilen tek lejant satırı **birebir** şu:

```
kapanmış mum · yeşil boş = yükselen · kırmızı dolu = düşen · ┄ Stabil destek (yeşil)
· ▼ dönüş = sinyal · ▲ geri alım = yapı · boş = momentum
```

Lejantta **olmayan** üç şey var ve bunlar tam da bu turda eklenen katmanlar:
`○` halka (güçlü), `◎` çift halka (çok güçlü), soluk/silik ok (zayıf) + boyut
farkı (süpürme 34 vs rebase 62). Yani kullanıcı "neden bu okun etrafında halka var,
neden bu ok silik" sorusunun cevabını karede/kartta bulamıyor.

**Düzeltme (uygulandı):** `grafik/panels.py::_lejant` artık çizilen sınıfı
adıyla yazar ve yalnız GERÇEKTEN çizileni yazar (`_kademe_cizildi`: sayaç varsa
sayaçtan, ilk geçişte snapshot'tan). Üretilen ek madde:

```
ok kademesi: ○ güçlü · ◎ çok güçlü · soluk = zayıf      (yalnız var olanlar)
```

Örnek (VAKBN 1G): `… · ok kademesi: ○ güçlü`, ikinci satırda `soluk = zayıf`.
Madde `_LEJANT_KORU`'ya alındı: bütçe kısarken ok sözlüğü gibi korunur. Ayrıca
`_bol` ayırıcıdan böldüğünde satır başında kalan `· ` kırpılıyor
(`_satirlari_temizle`) — kart metninde "eksik madde" izlenimi vermiyor.

### P1 — `zayif` kademesi oku fiilen siliyor (doküman "ok silinmez" diyor) — **UYGULANDI**

`grafik/render.py:1352-1358` zayıf okun **üstüne** zemin renginde (`PALET["zemin"]`,
α 0,55) daha **büyük** (s=62 > 34/48) bir üçgen basıyor. 0,55 alfa koyu zeminde
okun kontrastını ~%45'e indiriyor; halka/kademe bilgisi de bu örtünün altında
kalıyor. `docs/denetim/OK_BAGLAM_DOGRULAMA_VE_UYGULAMA_2026-11-15.md` ise
"zemin rengi yarı saydam örtü; **ok silinmez**" diyor — kod ile doküman çelişiyor.
`VAKBN_1G_kademeler_ve_halkalar.png`'de zayıf barlar (56/64) leke gibi görünüyor.

**Düzeltme (uygulandı):** zemin örtüsü tamamen kaldırıldı. Zayıf bağlamlı ok,
kendi kademesinin biçimini koruyarak **kendi alfasıyla** çizilir
(`grafik-stabil-reclaim-zayif` α 0,35 · `-supurme-zayif` α 0,22 ·
`momentum-zayif` α 0,30). Ok artık "leke" değil, okun okunabilir soluk hâli;
`baglam_zayif_isaret` sayacı da çizilen oku saymaya devam ediyor.

### P2 — İşaret–mum çakışması ölçülmüyor; yeni halka kademesi ölçüsüz kaldı — **UYGULANDI (ölçüm)**

Sayılar: komşu muma değme **%27** (200 bar) / **%22** (120 bar); çift halka ±2–3 bar.
Sebep: kapı yalnız yazıları ölçüyor (`grafik/indicators.py::_mum_cakisma_say`,
`for t in ax.texts`), işaretleri değil. Yani 2026-11-15'te eklenen en iri işaret
(s=300) hiçbir ölçüme girmiyor; ileride "halkalar birbirine değiyor" türü bir
şikâyet yine ölçümsüz kalır.

**Düzeltme (uygulandı):** kapı artık `PathCollection` işaretlerini de ölçüyor →
`meta["kalite"]["isaret"]`, `["isaret_komsu_cakisan"]`, `["isaret_detay"]`
(gid bazında). Kendi mumuna değme hata sayılmaz (ok zaten onun altına konur);
KOMŞU mumla temas sayılır. Örnek ölçüm: VAKBN 1G/200 → `isaret: 8`,
`isaret_komsu_cakisan: 5` (detay: `baglam-guclu` 2, `momentum` 2, `-supurme` 1) —
yani sorunun kaynağı halka çapı ölçümle görünür hâle geldi. Halka boyutlarına
BİLİNÇLİ dokunulmadı (onaylı görsel); istenirse tek satırla küçültülebilir.

### P2 — Eski snapshot'ta momentum okları "en güçlü" görünüyor (ters varsayılan) — **UYGULANDI**

`grafik/render.py:1244` ve `1254`: tür sözlüğü yoksa (`reclaim_turleri` boş)
**bütün** reclaim okları dolu, `momentum_turleri` boşsa **bütün** momentum okları
büyük-içi-boş çiziliyor — yani süpürme (en zayıf tür) en güçlü gibi görünüyor.
Bugün üretim her zaman bu sözlükleri yazdığı için canlıda görülmüyor; ama
sürüm düşürmesi / eski `bot_data` snapshot'ı / Supabase'ten dönen eski kayıt
senaryosunda **aşırı iddia** yönünde yanlış varsayılan.

**Düzeltme (uygulandı):** ilk değerlendirmede reclaim tarafını da yazmıştım;
ölçümde görüldü ki `reclaim_turleri` boşken reclaim zaten **nötr** kademeye
(s=48 dolu) düşüyor — sorun yalnız momentumdaydı. Artık `momentum_turleri`
boşsa `rebase` grubu **s=50** (nötr) çizilir; s=62 yalnız kanıtlı
`upward_rebase_momentum` için ayrılmıştır. Sayaç anlamı değişmedi
(`momentum_isaret` hâlâ görünen oku sayar), böylece eski snapshot'ta da
"aşırı iddia" yönünde yanlış varsayılan kalmıyor.

### P2 — Dikey ofset volatiliteden bağımsız — **UYGULANDI**

Yerleşim `y_pos = min(destek, dip) − 0,018 × y_span`. `y_span` kadrajın fiyat
aralığı olduğu için ölçülen mesafe 12,1 – 56,6 px arasında değişiyor; sakin
pencerede ok mumun dibine yapışıyor, sert pencerede 50+ px uzakta "havada" duruyor
(`ULKER`, `AKBNK` 1G). Ayrıca destek fiyattan uzaksa ok desteğe, mumdan kopuk
çiziliyor (demo karede 49,0 desteğine 3 ok, mumlar 50–52'de).

**Düzeltme (uygulandı):** referans artık **mumun dibi** (mum verisi yoksa destek);
ofset `max(0,018×aralık, min(0,032×aralık, 0,25×tipik gövde))` — sakin pencerede
sabit, oynak pencerede bir tık nefes payı. Destek çizgisi mumun dibine çok
yakınsa ok ikisinin ALTINA iner (ölçüm: stepline ▲'nın içinden geçiyordu).
Sonuç: dikey mesafe 12,1–56,6 px dağınıklığından 12,1–25,0 px'e indi; ok her
zaman kendi mumunun altında. Komşu muma değme %27 → %39'a çıktı (oklar mumlara
yaklaştığı için beklenen yön); asıl kaynak halka çapı — bkz. P2 ölçüm maddesi.

### P3 — 120 barlık günlük karelerde tarih etiketi çakışması — **UYGULANDI**

Ölçülen 7 günlük karenin **7'sinde** sol kenarda iki etiket üst üste (`TURSG_1G_eksen_etiketi_cakismasi.png`:
"27 Nis" ile "03 May"). Sebep `grafik/markers.py::_tik_etiketleri`: adaylar **ay
başı** barlarından geliyor ama seyreltme **eşit aralık** varsayıyor (`j % adim`);
pencere ay sonuna denk gelirse ilk aday (0. bar) ile ay başı adayı 4–6 bar arayla
düşüyor. Piksel bütçesi (etiket genişliği × 1,35 + 8) bunu yakalıyor ama seyreltme
sonrası komşuluk kontrolü yok.

**Düzeltme (uygulandı):** `grafik/markers.py::_tik_etiketleri` seyreltmeyi artık
soldan sağa **piksel komşuluğuyla** yapıyor (her etiketin kendi genişliği +
nefes payı; `px/bar = eksen_px / bar sayısı`). Ölçüm: 120 barlık günlük karelerde
çakışma **7/7 → 0/12 kare**; 200 barlık karelerde de 0.

### P3 — Mimari notlar (davranış değil, bakım)

- `grafik/render.py::_kare_ciz` **480 satır**, `_stabil_ciz` **311 satır**;
  `zorder` değerleri 0–20 arasında 32 ayrı büyüklükte (3,55 / 3,57 / 3,65 / 3,67 /
  4,75 / 4,92 / 4,93 / 4,95 …). Katman sırası tek bir tabloda adlandırılmıyor;
  yeni bir katman eklemek "hangi kesirli sayı boş" sorusuna dönüşüyor.
- `render.py` içinde 8 literal renk (`#9CA3AF` ×3, `#ffffff` ×2, `#e5e7eb` ×2, …)
  `PALET` sarmalayıcısını atlıyor → renk körü paleti / ileride açık tema bunları
  değiştirmez. Halka renginin beyaz olması koyu zeminde doğru; yine de `PALET`'e
  taşınmalı.
- `grafik/` içinde 67 `except Exception` var; çoğu "süs çizimi kareyi düşürmesin"
  gerekçeli (doğru tercih), ama hata ayıklamada `log.debug` seviyesinde kalıyor.
- 1s/2s kartlarında stabil katmanı **tamamen** gizli
  (`grafik/render.py::ciz → stabil_gizli`, `test_stabil_short_tf_chart_policy.py`).
  Yani bu incelemedeki oklar yalnız 4s ve 1g karelerinde var — tasarım kararı,
  ama "oklar neden 1s'de yok" sorusunun cevabı lejantta değil.

## 5. Genel çizim değerlendirmesi (kısa)

| Alan | Durum | Not |
|---|---|---|
| Yerleşim / ölçü | **İyi** | Sabitler `SABITLER`'de, dpi 100, dinamik sağ şerit (`_sag_serit_px_hesapla`), yazı ölçeği mobilde 1,35× |
| Metin çakışması | **İyi** | `_mum_cakisma_say` + `_olay_yazi_koy` gerçek `get_window_extent` ile yer arıyor; 252 grafik testi yeşil |
| İşaret çakışması | **Ölçülü** | `meta["kalite"]["isaret"] / ["isaret_komsu_cakisan"]` (2026-11-16) |
| Renk / erişilebilirlik | **İyi** | Renk körü paleti + "renk tek başına bilgi taşımaz" kuralı (§0.4.1) tutarlı uygulanmış; 8 literal renk istisna |
| Lejant | **Tam** | `ok kademesi:` maddesi çizilen sınıfı anlatır (2026-11-16) |
| Eksen | **İyi** | 120 barlık günlük karede çakışma 0/12 (2026-11-16) |
| Bakım | **Orta** | 480 satırlık `_kare_ciz`, adlandırılmamış zorder tablosu, modül bölünmesinden kalan ~20 satırlık tekrar import blokları |
| Güvenlik kapıları | **İyi** | kapanmamış mum çizilmez, yanlış sembol reddedilir, katman hatası kareyi düşürmez, sağ şerit taşması engellenir |

## 6. Yeniden üretim

```bash
python -m scripts.grafik_ok_ve_etiket_olcum --pencere 200 --png-dizin /tmp/kareler
python -m scripts.grafik_ok_ve_etiket_olcum --pencere 120     # eksen çakışması burada çıkar
pytest -q test_grafik_gorsel_kalite.py test_grafik_serit_ve_ok_kademesi.py \
         test_stabil_momentum_arrow.py test_grafik_gorsel4.py test_grafik_gorsel5.py
pytest -q test_grafik_ok_olcum_betik.py        # ölçüm aracının sözleşmesi
```

Doğrulama: `ruff check .` temiz; grafik test bataryası **252 passed** (30,8 s).

## 7. Öneri sırası

| # | İş | Büyüklük | Kullanıcı etkisi |
|---|---|---|---|
| # | İş | Büyüklük | Kullanıcı etkisi | Durum |
|---|---|---|---|---|
| 1 | Lejant satırı (halka/çift halka/silik) | S | "Bu halka ne?" sorusunu kapatır | **yapıldı** |
| 2 | `zayif` örtüsünü kaldır, soluklaştırmayı oka uygula | S | Zayıf ok "leke" olmaktan çıkar | **yapıldı** |
| 3 | Tür bilinmiyorken nötr kademe (fail-soft) | S | Eski snapshot'ta aşırı iddia biter | **yapıldı** |
| 4 | Eksen etiketi seyreltmesini piksel komşuluğuna çevir | S | 120 barlık 1G karelerde bitişik tarih biter | **yapıldı** |
| 5 | İşaret geometrisi kapısı (`kalite["isaret"]`) | M | Yeni kademe ölçülebilir olur | **yapıldı** |
| 6 | Ok ofsetini gövdeye bağla, referansı mumun dibine al | M | Ok muma daha yakın/dengeli durur | **yapıldı** |
| 7 | `zorder` tablosu + `_kare_ciz` bölünmesi | L | Bakım; görsel çıktı değişmez | açık (kapsam dışı) |

Davranış değişmedi: sinyal/alarm üretimi, eşikler ve sayaç ADLARI aynı; yalnız
çizim, lejant ve ölçüm katmanı değişti.

### 7.1 Uygulanan değişiklikler (dosya bazında)

| Dosya | Değişiklik |
|---|---|
| `grafik/render.py` | `_ok_ofset`/`_ok_koordinatlari`/`_ok_grubu`; referans mumun dibi, stepline yakınsa `min(destek, dip)`; kademe blokları tek yardımcıdan; zayıf = aynı biçim + α (örtü yok); `momentum` türsüzken s=50; `cok_guclu` çift halka tek `gid` (`s=300+170`) |
| `grafik/panels.py` | `_kademe_cizildi()` + `ok kademesi:` lejant maddesi; `_LEJANT_KORU`; `_satirlari_temizle()` |
| `grafik/markers.py` | `_tik_etiketleri`: piksel komşuluk seyreltmesi |
| `grafik/indicators.py` | `_mum_cakisma_say`: `PathCollection` geometri kapısı (`isaret`, `isaret_komsu_cakisan`, `isaret_detay`) |
| `test_grafik_ok_kademesi_duzeltmeleri.py` | 10 sözleşme testi (lejant, zayıf ok, nötr kademe, kapı, eksen) |

### 7.2 Bilinçli olarak DEĞİŞTİRİLMEYENLER

- **Halka çapları** (s=150 / 300+170): onaylı görsel dil. Ölçüldü: 300→240
  küçültmesi komşu temasını 16/41'den 16/41'e taşımadı (temasın kaynağı bar
  aralığı, halka değil) — o yüzden dokunulmadı.
- **Kademe boyutları** (34/48/62/44): replay türetmesi değişmedi.
- **Sayaç adları** (`reclaim_isaret`, `momentum_isaret`, `baglam_*_isaret`):
  testler ve `meta` sözleşmesi bunlara bağlı.
- **`zorder` tablosu / `_kare_ciz` bölünmesi** (P3 #7): bakım işi, ayrı tur.
