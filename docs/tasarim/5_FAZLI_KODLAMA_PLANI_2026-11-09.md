# 5 Fazlı Kodlama Planı — Gölge Zincir Replay Sistemi (2026-11-09)

**Durum:** PLAN (bu belge sonuçlardan ÖNCE yazılmıştır; kapı eşikleri burada
önceden kayıtlıdır — anti-lookahead, kendi kararıma bile güvenilmeksizin).
**Sözleşme:** [SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md](SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md)
**Ölçüm temeli:** [STOP_SERMAYE_REPLAY_2026-11-09.md](../arastirma/STOP_SERMAYE_REPLAY_2026-11-09.md) ·
[DOMAIN_CIKTI_SOZLUGU_2026-11-09.md](DOMAIN_CIKTI_SOZLUGU_2026-11-09.md)

---

## 0. Hedef ve felsefe korumaları (bozulmaz)

**Hedef:** G1→G5 katmanlarının **sırayla konuştuğu**, bildiri → toplu yorum (TYR) →
plan kartı → işlem simülasyonu → ölçüm → kapı üreten **tam bir gölge replay
sistemi**. Tek çıktı yeri gölge defter + rapordur; canlı karar yoktur.

**Kırmızı çizgiler (sözleşmeden, aynen):**
1. Ana sistem değişmez — yalnız yeni dosyalar (`senaryo/`, `research/golge_*`,
   `test_senaryo_*`, `test_golge_*`).
2. Katman çıktısı kırpılmaz; her bildiri `kim/iddia/kosul/kaynak(n)/gecerlilik`
   taşır; **uydurma yasağı** (kaynak: tarihli replay tabloları).
3. Sıfat yasak, sayı var; n<30 sayılmaz; **sessizlik varsayılandır**.
4. Formasyon hedef değildir (bağlam/yol haritası); hedef **ölçülmüş karşıt
   yapı**; R ile yazılır.
5. Blok işlem engellemez — yalnız giriş yerini güzelleştirir.
6. Derin filtre ağacı yok; kapılar az ve sığ.
7. Geleceğe bakma yok: her karar yalnız `≤ t` verisiyle; MTF'te
   `üst TF kapanışı ≤ karar anı`.
8. Plan kartı **plandır, sinyal değildir**; kapı geçse bile canlıya bağlantı
   bu planın kapsamı DIŞINDADIR.

**Felsefe özeti (iş mantığı):** motor *yan okuyucudur*; önce katmanlar kendi
dilinde bildiri bırakır, zaman olgunlaşınca TYR tek hüküm verir, UYGUN olursa
bloklar giriş yerini çizer, işlem "aç-kapat" değil **tez yaşar/ölür**; sermaye
kuralları sayıyla uygulanır; her sonuç `bilinmeyenler` satırıyla birlikte yazılır.

---

## 1. Mimari (bir bakışta)

```
backfill_data/ ──research.arsiv.tf_frame──► çerçeveler (1h/2h/4h/1d)
        │
        ▼  (sembole bir kez, causal tek-geçiş)
┌────────────────────── G1–G5 ADAPTÖRLERİ (senaryo/zincir.py) ──────────────────────┐
│ G1 stabil   : build_single_pass_history + checkpoint sorgusu (≤ t)               │
│ G2 formasyon: patterns.run_engine yaşam döngüsü → olaylar (bar damgalı)          │
│ G3 MS       : run_domain_engines(isolated) → event ledger (event_bar ≤ t)        │
│ G5 bloklar  : replay_ob_zones / replay_fvg_zones → bant durumları (available ≤ t)│
└────────────────────────────────┬──────────────────────────────────────────────────┘
                                 ▼  bildiri şeması (§3 sözleşme)
                        senaryo/defter.py  ◄── golge_defter.jsonl (atomik)
                                 │
                                 ▼
                  TYR saf fonksiyonu (senaryo/tyr.py): BEKLE | UYGUN | RET
                                 │ UYGUN + onaylı tepki
                                 ▼
                  plan kartı (senaryo/plan_karti.py): giriş bandı · stop (tez
                  ölümü) · hedef (karşıt yapı) · R · zaman-stopu · bilinmeyen
                                 │
                                 ▼
         ileri yarış simülasyonu (golge_zincir.py): stop/hedef/nötr + sansür
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
   senaryo/kurallar.py                    research/golge_olcum.py (T2)
   (streak · tavan · rejim mührü)         ölçüm CSV/MD
                                              │
                                              ▼
                                 research/golge_kapi.py (T3, önceden kayıtlı)
                                 GEÇTİ / GEÇMEDİ  (canlıya bağlantı yok)
```

**Zaman disiplini (her katmanda aynı):**
- Karar anı = izleme TF'inde **kapanmış bar** `t`.
- G1: günlük/haftalık kapanışlar yalnız `≤ t` (stabil_replay kalıbı:
  `daily_close <= h4_close`); tek-geçiş O(N), O(N²) yok.
- G2/G3/G5: olay/bant kayıtları kendi bar damgalarıyla; as-of sorgu
  `available/event_bar ≤ t`.
- İleri simülasyon: yalnız `t`'den sonraki kapanışlar; eksik pencere = sansür.

**Evren ve bölme:** arşiv evreni (`arsiv_sembolleri` − `HAVUZ_DISI`), 4 TF
(1h/2h/4h/1d). Keşif/doğrulama = **sembol başına kronolojik %70/%30** (ev
stili). Örtüşmesizlik: sembol×TF başına 20 bar pencere (işlem yarışları için).

---

## 2. Fazlar

### Faz 1 — Çekirdek: modeller + zaman disiplini + gölge defter
**Dosyalar:** `senaryo/__init__.py`, `modeller.py`, `zaman.py`, `defter.py`
**İş:**
- `modeller.py`: `Bildirim`, `Hukum`, `PlanKaydi`, `IslemSonucu` dataclass'ları;
  zorunlu alanlar §3 şemasına göre (`kim, iddia, kosul, kaynak, gecerlilik`);
  `kaynak` içinde `n` zorunlu (uydurma yasağı, şemada kısıtlanır); JSON serileştirme.
- `zaman.py`: `as_of(frame, t)` (gelecek satırları keser, kopya döner),
  `kapatilmis_barlar(frame, t)`, MTF katı kuralı `ust_tf_kapandi_mi(ust, t)`.
- `defter.py`: `GolgeDefter` — JSONL append (satır atomik: tek `write` + flush),
  `oku()` okuma, sayaçlar; dosya yolu yapılandırma ile (testte tmp_path).
**Testler:** `test_senaryo_zaman.py` (gelecek kesme, kopya mühürü — asıl frame
değişmemeli), `test_senaryo_defter.py` (yaz-oku tur, zorunlu alan ihlali reddi,
bozuk satır atlanır).
**Kabul:** yeni testler yeşil; ana sisteme dokunulan dosya yok (`git status`).
**Commit:** `Faz 1 — senaryo çekirdeği: modeller, zaman disiplini, gölge defter`

### Faz 2 — G1–G5 adaptörleri + bildiri üretimi + TYR saf fonksiyonu
**Dosyalar:** `senaryo/zincir.py`, `senaryo/tyr.py`
**İş:**
- `zincir.py` adaptörleri (hepsi **yalnız mevcut motor çıktılarını okur**,
  motor değiştirmez):
  - `g1_stabil(symbol, gunluk, h4, t)` → destek/karakter durumu + olay
    (tek-geçiş önbellek sembol başına; `StabilSinglePassHistory` checkpoint
    sorgusu ≤ t);
  - `g2_formasyon(symbol, tf, snapshot)` → faz/kısmi olaylar (bar damgalı);
  - `g3_ms(symbol, tf)` → BOS/CHOCH/TRANSITION_FAIL kayıtları (event_bar);
    **tazelik filtresi** (yaş ≤ eşik) bildirime dönüşür, olayların kendisi
    kırpılmaz;
  - `g5_blok(symbol, tf)` → OB/FVG bantları (`available_at ≤ t`, temas
    barları, terminal durumlar).
- Bildiri üretici: her olay → §3 şemasında tek `Bildirim` (kaynak adları
  gerçek ölçüm tabloları: ARASTIRMA_SONUCLARI, OK sentezi, zone kovaları…).
- `tyr.py`: **saf** `tyr_hukmu(bildirimler, fiyat, atr, t) -> Hukum`:
  - `RET`: tez seviyesi öldü (onaysız destek kırılımı) veya G1 kapandı ya da
    UYGUN sonrası ters BOS iptali;
  - `UYGUN`: G1 kapısı açık + taze karşıt uyarı yok + olgunluk (fiyat izleme
    seviyesine ≤1 ATR veya daralma eşiği) + çelişki ≤ 1;
  - `BEKLE`: varsayılan (sessizlik).
  - Çıktı: `hukum · X lehte · Y çelişki` tek satır; sıfat yok.
**Testler:** `test_senaryo_ziran` → `test_senaryo_zincir.py` (as-of: gelecek
olay bildiriye girmez; kaynak `n`'siz reddedilir), `test_senaryo_tyr.py`
(elle kurulmuş 5 senaryo: varsayılan BEKLE, RET tetikleri, UYGUN koşulları,
çelişki sayacı, sessiz G1 → susma).
**Kabul:** testler yeşil; TYR hiçbir yerde fiyat/gelecek okumaz (saf kanıt:
girdi değişmezse çıktı değişmez).
**Commit:** `Faz 2 — G1–G5 adaptörleri, bildiri şeması, TYR saf fonksiyonu`

### Faz 3 — Gölge zincir koşucusu + plan kartı + işlem simülasyonu
**Dosyalar:** `senaryo/plan_karti.py`, `research/golge_zincir.py`
**İş:**
- `plan_karti.py` (saf): UYGUN + G5 bandında **onaylı tepki** → `PlanKaydi`:
  - giriş = tetik barının kapanışı; band = G5 OB/FVG kalan bant;
  - **stop = tez ölümü** (destek/formasyon alt sınırı − tampon); stop mesafesi
    0,5–2,5 ATR dışındaysa **plan yok** (aşırı dar gürültüde, aşırı geniş
    anlamsız);
  - **hedef = en yakın karşıt yapı** (stabil direnç / formasyon üst sınırı /
    PH); `R ≥ 1,2` değilse plan yok (gerçek hedef zorunlu);
  - zaman-stopu 10 bar; `bilinmeyenler` satırı zorunlu.
- `golge_zincir.py` koşucusu:
  1. sembol×tf için G1–G5 hazırlık (tek geçiş);
  2. bar bar olay akışı → bildirimler deftere (sessizlik de yazılır: özet satır);
  3. TYR tetikleri (yeni bar · seviyeye ≤1 ATR · bildirim değişimi) → hüküm;
  4. UYGUN + tepki onayı → plan kartı → **ileri yarış** (stop/hedef/nötr;
     aynı barda çift dokunuş → stop; sansür ayrı) → `IslemSonucu`;
  5. JSONL defter + `cikti/ozet.json` (ham sayaçlar).
- **Duman koşusu** (3 sembol) → hatalar düzeltilir → **tam koşu** (tüm evren,
  4 TF).
**Testler:** `test_senaryo_plan.py` (R<1,2 → None; stop bandı; bilinmeyen
zorunlu; hedef asla formasyon değil — karşıt yapı), `test_golge_zincir_smoke.py`
(200 barlık sahte seride zincir uçtan uca döner, defterde ≥1 satır, gelecek
sızıntısı yok — son bar sonucu yalnız ≤ t okumalarıyla üretilir).
**Kabul:** duman koşusu hata vermeden tamamlanır; tam koşu `ozet.json` üretir.
**Commit:** `Faz 3 — gölge zincir koşucusu, plan kartı, işlem simülasyonu`

### Faz 4 — Ölçüm (T2) + sermaye/korunma kuralları
**Dosyalar:** `senaryo/kurallar.py`, `research/golge_olcum.py`
**İş:**
- `kurallar.py`: (a) **streak**: sembol×TF 3 üst üste stop → sıradaki işlemi
  atla (önceden ölçülmüş kural, −%1,7 maliyet); (b) **eşzamanlı tavan 3**
  (portföy zaman çizelgesi); (c) **rejim mührü**: G1 kapalıyken yeni plan
  yok (zincirde zorunlu); (d) eski "günde 2 stop" kuralı da ölçülür
  (tetiklenmediği görülmüştü — teyit).
- `golge_olcum.py` (T2): defterden:
  - hüküm dağılımı (BEKLE/UYGUN/RET, sembol/TF kırılımı);
  - plan sonuçları: stop/hedef/nötr + koşullu hedef, beklenti (0/0,05/0,10
    maliyet ızgarası — **varsayımsal, etiketli**);
  - **kör baz**: aynı tetikleyicilerde hüküm yok sayılsaydı (tüm tetikler)
    yarış → UYGUN'un farkı (kapının ham maddesi);
  - R dağılımı, zaman-stopu, MAE-öncesi, çözüm barı;
  - keşif/doğrulama ayrımı; G1-sessiz negatif kontrol (G1 kapalıyken kaç plan);
  - kural etkileri (streak/tavan vs kural-yok toplamları).
- Çıktı: `docs/arastirma/sonuclar/golge_zincir/*.csv` + rapor iskeleti.
**Testler:** `test_senaryo_kurallar.py` (streak sayacı, tavan, mühür).
**Kabul:** ölçüm dosyaları üretilir; tüm sayılar defterden yeniden üretilebilir
(reprodüksiyon: `python research/golge_olcum.py`).
**Commit:** `Faz 4 — T2 ölçümü ve sermaye kuralları`

### Faz 5 — Kapı (T3) + hata düzeltme turu + nihai rapor
**Dosyalar:** `research/golge_kapi.py`, `docs/arastirma/GOLGE_ZINCIR_REPLAY_2026-11-09.md`
**İş:**
- Kapı — **eşikler bu belgede önceden kayıtlıdır (§4)**; sonuç okunduktan
  sonra değiştirilemez; `golge_kapi.py` sabitleri koddur.
- Hata düzeltme protokolü: koşumda çıkan her hata önce **sınıflanır**
  (veri / adaptör / simülasyon / test) ve yalnız yeni pakette düzeltilir;
  düzeltme → ilgili test yeşil → tekrar koşu. Ana sisteme düzeltme yok
  (bulgular rapora "ana sistem notu" olarak yazılır).
- Nihai rapor: sonuçlar, kapı kararı, kalan bilinmeyenler, Faz 0 ile
  karşılaştırma, sıradaki adım önerisi. README'ye kayıt.
**Kabul:** kapı kararı dosyası (`kapi_karari.json`) + rapor + README kaydı;
tüm yeni testler yeşil.
**Commit:** `Faz 5 — T3 kapısı, hata düzeltme turu, nihai gölge zincir raporu`

---

## 3. Şema ve sabitler (kod girmeden sabitlenenler)

| Sabit | Değer | Dayanak |
|---|---|---|
| TYR çelişki tavanı | ≤ 1 (2+ ise BEKLE) | sığ kapı (kırmızı çizgi 5) |
| Taze karşıt MS uyarısı | yaş ≤ 5 bar → BEKLE | MS "tazelik" ölçümleri (süpürme WH/WL 3 bar) |
| Seviyeye mesafe | ≤ 1,0 ATR → TYR tetiği/olgunluk | stop replay MAE p90 1,48 →1 ATR bandı sığ tutulur |
| Tepki onayı | dokunuş sonrası 3 bar içinde kapanış bandın içinde/üstünde | OK sentezi "teyidin %76'sı ilk barda" |
| Stop tamponu | 0,10 ATR (destek/formasyon altı) | ölçülmedi, sabit varsayım — raporda etiketli |
| Stop mesafesi bandı | 0,5–2,5 ATR (dışında plan yok) | stop replay ızgarası |
| R eşiği | ≥ 1,2 | hedef = karşıt yapı; 1,5 ideal,1,2 minimum (kayma payı) |
| Zaman-stopu | 10 bar | BOS %60'ı ilk 3 bar; medyan çözüm 4 bar |
| Örtüşmesizlik | 20 bar (sembol×TF) | stop replay ev stili |
| Keşif/doğrulama | kronolojik %70/%30 (sembol başına) | ev stili |
| Maliyet ızgarası | 0 / 0,05 / 0,10 ATR (varsayımsal) | stop replay §4 |

## 4. Önceden kayıtlı kapı eşikleri (T3) — sonuç okunmadan sabitlenmiştir

Kapı **yalnız planın gölge istatistiğini** değerlendirir; çıktı her durumda
plandır, sinyal değil; canlıya bağlantı yoktur.

| # | Eşik | Değer |
|---|---|---|
| K1 | Doğrulamada UYGUN plan sayısı (örtüşmesiz) | **n ≥ 50** |
| K2 | Doğrulamada UYGUN **koşullu hedef** oranı − **kör baz** (aynı tetikler, hüküm yok sayılarak) | **≥ +5 puan** |
| K3 | Doğrulama net beklentisi (maliyet 0) | **> 0** |
| K4 | G1 kapalıyken üretilen plan oranı | **≤ %5** |
| K5 | RET sonrası yeni plan (aynı tez) | **0 (mutlak)** |
| K6 | Keşif ↔ doğrulama işaret tutarlılığı | her ikisi de beklenti **> 0** |

**Karar:** 6/6 sağlanırsa `GEÇMEDİ hariç GEÇTİ`; tek ihlal = `GEÇMEDİ`.
Sonuç ne olursa olsun raporlanır; GEÇTİ bile yalnız **kanıt birikimi**
sayılır (kırmızı çizgi 8).

---

## 5. Riskler ve önden düşünülenler

| Risk | Önlem |
|---|---|
| FVG 1h'de yok (motor 2h/4h/1d) | adaptör `skipped` kabul eder; 1h G5 yalnız OB |
| 2h FVG kapalı (opt-in) | koşucuda `enable_2h_fvg=True` (offline sözleşmesi) |
| Hacim kirli (59.604 sıfır) | VP TYR'ye **girmez** (sözleşme: hacim kesinleştirmez); deftere bağlam olarak yazılır |
| Stabil tek-geçiş API'si ağır | sembol başına bir kez; checkpoint sorgusu O(log N) |
| Defter şişmesi | olay bazlı, alanlar sıkı; özet `ozet.json` |
| O(N²) prefix koşusu yasağı | yalnız tek-çalışan motor geçişleri (stabil single-pass, zone replay O(N), MS bir kez) |
| Gelecek sızıntısı | testler: son bar kararı yalnız ≤ t girdisiyle üretilmeli; as_of kesme birim testi |
| Kapıya sonradan göz kaydırma | eşikler bu belgede + koda gömülü; değişiklik = yeni belge + gerekçe (yok sayılır) |
| Python bağımlılıkları | pytz/pandas/numpy/pytest kuruldu (oturum) |

## 6. Çıktı konumu

- Kod: `senaryo/` (yeni paket), `research/golge_*.py`
- Test: `test_senaryo_*.py`, `test_golge_*.py`
- Defter/ölçüm: `docs/arastirma/sonuclar/golge_zincir/`
  (`golge_defter.jsonl`, `ozet.json`, T2 CSV'leri, `kapi_karari.json`)
- Rapor: `docs/arastirma/GOLGE_ZINCIR_REPLAY_2026-11-09.md`
- Her faz ayrı commit; her fazda yeni testler yeşil.
