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
| 200 bar | 49 | **0** | **13 (%27)** | 12,1 – 44,7 px | 0 / 12 kare |
| 120 bar | 32 | **0** | **7 (%22)** | 12,1 – 56,6 px | **7 / 7 günlük karede 1 çift** (4s'te 0) |

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

### P1 — Lejant çizileni anlatmıyor (repo'nun kendi kuralı §0.12v)

Karede ok olan bir grafik için üretilen tek lejant satırı **birebir** şu:

```
kapanmış mum · yeşil boş = yükselen · kırmızı dolu = düşen · ┄ Stabil destek (yeşil)
· ▼ dönüş = sinyal · ▲ geri alım = yapı · boş = momentum
```

Lejantta **olmayan** üç şey var ve bunlar tam da bu turda eklenen katmanlar:
`○` halka (güçlü), `◎` çift halka (çok güçlü), soluk/silik ok (zayıf) + boyut
farkı (süpürme 34 vs rebase 62). Yani kullanıcı "neden bu okun etrafında halka var,
neden bu ok silik" sorusunun cevabını karede/kartta bulamıyor.

**Küçük onarım (S):** `grafik/panels.py::_lejant_satirlar`'a tek cümle:
`○ halka = güçlü bağlam · ◎ = çok güçlü · silik = zayıf` — yalnız o işaret
gerçekten çizildiyse (mevcut `iptal_cizildi` deseninin aynısı). Lejant bütçesi
1 satır + ~55 karakter; bütçe aşımı `lejant_atlanan`da görünür, sessiz düşmez.

### P1 — `zayif` kademesi oku fiilen siliyor (doküman "ok silinmez" diyor)

`grafik/render.py:1352-1358` zayıf okun **üstüne** zemin renginde (`PALET["zemin"]`,
α 0,55) daha **büyük** (s=62 > 34/48) bir üçgen basıyor. 0,55 alfa koyu zeminde
okun kontrastını ~%45'e indiriyor; halka/kademe bilgisi de bu örtünün altında
kalıyor. `docs/denetim/OK_BAGLAM_DOGRULAMA_VE_UYGULAMA_2026-11-15.md` ise
"zemin rengi yarı saydam örtü; **ok silinmez**" diyor — kod ile doküman çelişiyor.
`VAKBN_1G_kademeler_ve_halkalar.png`'de zayıf barlar (56/64) leke gibi görünüyor.

**Küçük onarım (S):** örtüyü kaldır, soluklaştırmayı okun kendi üstünde yap
(`alpha=0.35`, `linewidths/edgecolors` aynı kalsın) veya örtüyü s=40'a küçült.
Davranış değişmez, yalnız görünürlük.

### P2 — İşaret–mum çakışması ölçülmüyor; yeni halka kademesi ölçüsüz kaldı

Sayılar: komşu muma değme **%27** (200 bar) / **%22** (120 bar); çift halka ±2–3 bar.
Sebep: kapı yalnız yazıları ölçüyor (`grafik/indicators.py::_mum_cakisma_say`,
`for t in ax.texts`), işaretleri değil. Yani 2026-11-15'te eklenen en iri işaret
(s=300) hiçbir ölçüme girmiyor; ileride "halkalar birbirine değiyor" türü bir
şikâyet yine ölçümsüz kalır.

**Küçük onarım (M):** `_mum_cakisma_say`'a `PathCollection` (gid `grafik-stabil-*`)
kontrolü ekle → `meta["kalite"]["isaret_cakisan"]`; eşik testte 0 tutulmaz, mevcut
durum (13/49) taban olarak yazılır. Ölçüm betiği bunun referans uygulaması.

### P2 — Eski snapshot'ta tüm oklar "en güçlü" görünüyor (ters varsayılan)

`grafik/render.py:1244` ve `1254`: tür sözlüğü yoksa (`reclaim_turleri` boş)
**bütün** reclaim okları dolu, `momentum_turleri` boşsa **bütün** momentum okları
büyük-içi-boş çiziliyor — yani süpürme (en zayıf tür) en güçlü gibi görünüyor.
Bugün üretim her zaman bu sözlükleri yazdığı için canlıda görülmüyor; ama
sürüm düşürmesi / eski `bot_data` snapshot'ı / Supabase'ten dönen eski kayıt
senaryosunda **aşırı iddia** yönünde yanlış varsayılan.

**Küçük onarım (S):** tür bilinmiyorken nötr kademe (dolu-normal) kullan; süpürme
küçültmesi yalnız tür **bilinirken** uygulanır (fail-soft, iddia büyütmez).

### P2 — Dikey ofset volatiliteden bağımsız

Yerleşim `y_pos = min(destek, dip) − 0,018 × y_span`. `y_span` kadrajın fiyat
aralığı olduğu için ölçülen mesafe 12,1 – 56,6 px arasında değişiyor; sakin
pencerede ok mumun dibine yapışıyor, sert pencerede 50+ px uzakta "havada" duruyor
(`ULKER`, `AKBNK` 1G). Ayrıca destek fiyattan uzaksa ok desteğe, mumdan kopuk
çiziliyor (demo karede 49,0 desteğine 3 ok, mumlar 50–52'de).

**Onarım (M, istenirse):** ofseti ATR tabanlı yap (`0,15 × ATR`, alt sınır 8 px)
ve desteğe değil **mumun dibine** sabitle; desteğe uzaklık yalnız stepline'da kalsın.

### P3 — 120 barlık günlük karelerde tarih etiketi çakışması

Ölçülen 7 günlük karenin **7'sinde** sol kenarda iki etiket üst üste (`TURSG_1G_eksen_etiketi_cakismasi.png`:
"27 Nis" ile "03 May"). Sebep `grafik/markers.py::_tik_etiketleri`: adaylar **ay
başı** barlarından geliyor ama seyreltme **eşit aralık** varsayıyor (`j % adim`);
pencere ay sonuna denk gelirse ilk aday (0. bar) ile ay başı adayı 4–6 bar arayla
düşüyor. Piksel bütçesi (etiket genişliği × 1,35 + 8) bunu yakalıyor ama seyreltme
sonrası komşuluk kontrolü yok.

**Küçük onarım (S):** seyreltmeyi soldan sağa "önceki korunan etiketten en az
`genişlik × 1,35 + 8 px` uzakta" kuralıyla yap (10 satır). Ölçüm betiği bunu
`--pencere 120` ile tekrar doğrular.

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
| İşaret çakışması | **Ölçümsüz** | bkz. P2 — sayaçlar var, geometri kapısı yok |
| Renk / erişilebilirlik | **İyi** | Renk körü paleti + "renk tek başına bilgi taşımaz" kuralı (§0.4.1) tutarlı uygulanmış; 8 literal renk istisna |
| Lejant | **Eksik** | bkz. P1 — kademeler anlatılmıyor |
| Eksen | **Küçük kusur** | bkz. P3 — 120 barlık günlük karede sol kenarda çakışma |
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
| 1 | Lejant satırı (halka/çift halka/silik) | S | "Bu halka ne?" sorusunu kapatır |
| 2 | `zayif` örtüsünü kaldır, soluklaştırmayı oka uygula | S | Zayıf ok "leke" olmaktan çıkar |
| 3 | Tür bilinmiyorken nötr kademe (fail-soft) | S | Eski snapshot'ta aşırı iddia biter |
| 4 | Eksen etiketi seyreltmesini piksel komşuluğuna çevir | S | 120 barlık 1G karelerde bitişik tarih biter |
| 5 | `kalite["isaret_cakisan"]` kapısı (işaret geometrisi) | M | Yeni kademe ölçülebilir olur |
| 6 | Ok ofsetini ATR'ye bağla | M | Ok muma daha yakın/dengeli durur |
| 7 | `zorder` tablosu + `_kare_ciz` bölünmesi | L | Bakım; görsel çıktı değişmez |

1–4 tek turda, davranış değiştirmeden yapılabilir; 5–6 görsel ölçüm ister, 7 ayrı iş.
