# Gölge Zincir Replay'i — Faz 0–5 Raporu

**Tarih:** 2026-11-09/10 · **Durum:** Tamamlandı · **Kapı kararı: GEÇMEDİ (6/7 eşik)**
**Bağlantı:** [5 Fazlı Kodlama Planı](../tasarim/5_FAZLI_KODLAMA_PLANI_2026-11-09.md) · [Senaryo Motoru Brifing Sözleşmesi](../tasarim/SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md) · [Domain Çıktı Sözlüğü](../tasarim/DOMAIN_CIKTI_SOZLUGU_2026-11-09.md)

> **Kırmızı çizgi8:** Bu rapor bir **kanıt**tır, sinyal değil. Kapı `GEÇMEDİ` →
> canlıya bağlantı **yoktur**, plan çıkışı her zaman **plandır** (komut değildir).

---

## 1. Özet

Tam replay zinciri (Faz 0–5) kuruldu ve **704 seri × 0 hata** ile koşuldu:
arşiv verisinden katman katman bildirim → hüküm → tetik → geometrik plan →
bar-bar yarış → sonuç, ardından önceden kayıtlı eşiklerin değerlendirilmesi.

| Kapı | Eşik | Değer | Karar |
|---|---|---|---|
| K1 doğrulamada UYGUN plan n | ≥ 50 | **566** | ✅ |
| K2 UYGUN − kör koşullu hedef | ≥ +5.0 puan | **−0.67** | ❌ |
| K3 doğrulama beklentisi (maliyet 0) | > 0 | **+0.1107 ATR** | ✅ |
| K4 G1 kapalıyken plan oranı | ≤ %5 | **%0.0** | ✅ |
| K5 RET sonrası plan ihlali | = 0 | **0** | ✅ |
| K6a keşif beklentisi | > 0 | **+0.3595 ATR** | ✅ |
| K6b doğrulama beklentisi | > 0 | **+0.1107 ATR** | ✅ |

**Sonuç:** 7 eşikten6'sı geçti; **K2 başarısız → kapı GEÇMEDİ**. Sistem canlıya
bağlanmaz. K2'nin yakaladığı şey tam olarak şudur: **geometri + zamanlama
(bant ∩ tepki onayı) değer üretiyor (K3, K6 ✓); TYR hüküm katmanı
(BEKLE/UYGUN ayrımı) koşullu hedef oranına katkı yapmıyor (−0.67 puan).**

---

## 2. Fazlar ve taahhütler

| Faz | İçerik | Commit | Test |
|---|---|---|---|
| 0 | Bağlam: domain sözlüğü + stop/sermaye replay'i (18.352 yol,5 Faz temeli) | `3014268` | mevcut478+35 yeşil |
| 1 | `senaryo/modeller.py`, `zaman.py`, `defter.py` — olay zamanı, ekle-kaydet defteri | `44a6341` |17 |
| 2 | `senaryo/zincir.py`, `tyr.py` —6 katman sıralı zincir, RET/BEKLE/UYGUN hükmü | `6e305f1` |45 |
| 3 | `senaryo/plan_karti.py` + `research/golge_zincir.py` — geometri, bar-bar yarış, koşucu | `b814f9a` |56 |
| 4 | `senaryo/kurallar.py`, `yaris.py` + `research/golge_olcum.py` — T2 ölçümü, kör baz, kapı girdisi | `e3710af` |71 |
| 5 | `research/golge_kapi.py` — önceden kayıtlı eşikler + bu rapor | bu commit |79 |

Toplam yeni test: **79** (`test_senaryo_*.py`, `test_golge_*.py`); hepsi yeşil.
Ana sistem koduna dokunulmadı — tüm değişiklikler `senaryo/`, `research/golge_*`,
`test_senaryo_*`, `test_golge_*` ve `docs/` içinde.

---

## 3. Mimari (kısa)

```
arşiv (176 sembol ×4 TF,365 gün,994.142 bar)
  │ her bar,4 TF kronolojik döngü (gelecek bar okunmaz)
  ├─ stabilize olaylar → bildirim (append-only defter, sessizlik de yazılır)
  ├─ stabil/blok/ms/formasyon katmanları → aktif bildirim tablosu
  ├─ TYR (sadece değişince yazar): RET / BEKLE / UYGUN + gerekçe
  ├─ tetik: G5 bandı ∩ tepki onayı — hüküm ne olursa olsun kaydedilir
  ├─ plan: tetik ∧ UYGUN ∧ geometri (R≥1.2, stop bandı0.5–2.5 ATR) ∧ son plandan ≥20 bar
  └─ yarış: girişten itibaren her barın kapanışı; çift dokunuş→stop, H=10→zaman, veri biterse sansür
ölçüm (golge_olcum.py): plan sonuçları + KÖR BAZ (hüküm yok sayılarak tüm
  geometrik tetiklerden20-bar açgözłü aynı yarış) + maliyet0/0.05/0.10 + kapı girdisi
kapı (golge_kapi.py): eşikler koşumdan ÖNCE plan belgesine yazıldı; değişmez
```

Anti-lookahead sözleşmeye uygundur: `event_bar`, tamamlanmış bar kapanışları,
yalnız doğrulama amaçlı `as_of`/dönem etiketleri, defter ekle-kaydet.

---

## 4. Koşu özeti

| | |
|---|---|
| Kapsam | **704 seri** (176×4),365 gün, **0 hata**,22.648 s (≈6,3 sa) |
| Defter | `docs/arastirma/sonuclar/golge_zincir/golge_defter.jsonl` (334 MB, gitignore'lu) |
| Bildirim | **567.077** (sessizlik/bitış: **152.744**) |
| Hüküm yazımı (değişim) | **87.832** · bar-bazlı dağılım: BEKLE506.930 / UYGUN397.290 / RET224.813 |
| Tetik (bant ∩ onay) | **291.041** · geçerli geometri: **9.700** (%3,3) |
| Plan | **2.771** (geometri ∧ UYGUN ∧ ≥20 bar boşluk) |
| Sonuç | **hedef872 / stop951 / zaman942 / sansür6** (çözülen2.765) |

Çözünme: medyan **7 bar** (p75=10=H), R medyan **1,70**, MAE p50 **−0,54 ATR**
(p90=0: işlemlerin ≥%10'u girişin altına hiç inmedi).

## 5. Plan sonuçları (maliyet hariç, ATR)

| Dilim | n | Koşullu hedef | Beklenti |
|---|---|---|---|
| **Genel** |2.771 | %47,83 | **+0,3091** |
| Keşif (%70) |2.205 | %50,49 | **+0,3595** |
| Doğrulama (%30) |566 | %38,40 | **+0,1107** |
| TF1d |416 | — | +0,2795 |
| TF1h |1.002 | — | +0,2812 |
| TF2h |836 | — | **+0,3523** |
| TF4h |517 | — | +0,3172 |

**Maliyet ızgarası (doğrulama):**0,0 → **+0,1107** ·0,05 → **+0,0607** ·0,10 → **+0,0107**
(keşif: +0,3595 / +0,3095 / +0,2595). Doğrulama, gerçekçi maliyette (0,10) **kenarda**
(+0,0107); keşif–doğrulama farkı (%50,5 → %38,4 koşullu hedef) seçicilik aşımına işaret.

## 6. Kör baz ve K2 teşhisi

Kör baz = **hüküm yok sayılan** aynı geometri ve aynı yarış,20-bar açgözlü
örtüşmezlikle: **4.858 işlem**, koşullu hedef **%48,43**, beklenti **+0,3243**.

| Kör dilimi | n | Koşullu hedef | Beklenti |
|---|---|---|---|
| kör × BEKLE |2.493 | %48,78 | +0,3351 |
| kör × UYGUN |2.236 | %48,36 | +0,3184 |
| kör × RET |129 | %43,81 | +0,2173 |

**Teşhis:** Aynı geometri üzerinde hüküm sınıfları koşullu hedefi ayrıştırmıyor
(BEKLE %48,78 ≈ UYGUN %48,36). K2 = UYGUN(%38,40, plan koşullu) − kör(%39,07,
doğrulama kör koşullu) = **−0,67 puan < +5 eşik**. Yani zincirin **zamanlama
katmanı** (bant ∩ tepki onayı + geometri + boşluk) çalışıyor; **hüküm katmanı**
giriş kalitesine ek katmıyor. K2, tam olarak bu yüzden önceden kayıtlıydı.

## 7. Sermaye kuralları etkileri (ölçüm katmanında; ham kayıt değişmez)

| Kural | Etki |
|---|---|
| **Streak** (sembol×TF,3 üst üste stop → sıradaki atla) | **23 atlandı** /2.765; atlananların toplam etkisi **+0,905 ATR** (neredeyse nötr); serilerin %8,28'inde streak≥3 oluştu, maks3 |
| **Gün durdurma** (aynı gün2 stop → gün sonu dur; eski kural) | **0 tetik** (0 gün) — önceki stop replay'iyle tutarlı |
| **Eşzamanlı tavan3** | **2.373/2.765 atlandı** → toplam PnL854,66 → **59,93 ATR** — çok bağlayıcı: planlar piyasa olaylarında kümelendiği için eşzamanlılık sürekli ≥3. Kural önceden kayıtlıydı; etkisi olduğu gibi raporlanır. |

## 8. Geliştirme boyunca bulunan ve düzeltilen hatalar

1. **Fall-through (koşucu):** `acik_plan` yokken yarış bloğuna düşme → TypeError. Düzeltme: tetik bloğu **dış** `if acik_plan is None: continue` ile kapandı; tetik bloğu zaten plan açıkken çalışmıyor, yarış her bar koşuyor (yeniden doğrulandı).
2. **Uzak destek stopu:** `zemin = min(destek, band_lo)` stopu >2,5 ATR'ye şişiriyordu (AEFES/4h geometri hatalarının %71'i `stop_genis`). Düzeltme: **`max(destek, band_lo)`** — geçersizleştirme çizgisi girişin en yakını; plan sayısı seri başına3→9'a çıktı.
3. **Tetik kıtlığı:** 20 bar zorlaması tetikleri kesiyordu → tetik **boşluksuz** kaydedildi, örtüşmezlik **ölçümde** uygulandı (kör baz + plan aynı kural).
4. **Eksik bağımlılık:** `exchange-calendars==4.13.2` (requirements'ta ilanlı) kurulu değildi; `bist_calendar` UNKNOWN → `chart_bridge` `_UnsafeSource` → **son haftalık trend** eksik kalıyordu. Kurulum sonrası koşu temiz veriyle yeniden yapıldı.
5. **Ölçüm kusurları (duman):** sansür sayımları ve G1-kapalı plan kümesi düzeltilip duman defteri üzerinde doğrulandı.
6. **Ortam:** tam koşu bir kez platform tarafından yeniden başlatıldı (taze defter, aynı sonuç bütünlüğü); log saat sapması yalnız göstergeyi etkiledi, veri etkilenmedi.

Düzeltmelerin tümü testlerle kilitlendi (79 yeşil); hiçbirinde kapı eşiği
**sonuç okunduktan sonra** değiştirilmedi (anti-lookahead).

## 9. Felsefe uyumu (kırmızı çizgiler)

- **Canlı yayın yok** — kapı `GEÇMEDİ`, çıktı yalnız rapor/JSON. ✅
- **Çıktı her zaman plandır, sinyal değil** (plan kartı, `uyari_metni` boş). ✅
- **Formasyon hedef değil bağlam** — G2 aktifken üst sınır bilinmeyen olarak yazıldı. ✅
- **Blok işlemi bloklamaz, yalnız giriş daraltır** — G5 bandı + tepki onayı. ✅
- **Katmanlar sıralı, sessizlik deftere yazılır** —152.744 `sessizlik/bitiş` kaydı. ✅
- **Hedef ölçülü yapıdan, R ≥1,2** — geçersiz geometri plana dönüşmedi (9.700→2.771). ✅
- **Durum tek aktif bildirim** (kim başına), ekle-kaydet, ham kayıt değişmez. ✅

## 10. Sonraki adımlar (kapı GEÇMEDİ çıktısına göre)

1. **K2 onarımı (öncelikli):** TYR hüküm katmanı giriş kalitesine ek yapmıyor.
   Yönler: (a) BEKLE'i "giriş değil, bağlam" olarak yeniden tanımla ve K2'yi
   **hüküm-kör koşullu hedef** yerine ayrı bir ayrıştırma testiyle ölç (kapı
   eşiği değişmez; yeni koşu yeni planla); (b) tepki onayı tazelemesini hükmün
   kendisine taşı (BEKLE → taze onayla UYGUN); (c) RET sonrası "ne zaman yeniden
   izin verilir" kuralını ölç.
2. **Seçicilik:** doğrulama koşullu hedefi %38,4 — keşif %50,5. Aşırı uyum
   şüphesi: doğrulama diliminde daha katı filtre (ör. yalnız2h/4h, yalnız onaylı G1).
3. **Tavan3:** eşzamanlılık kümelendiği için86% eliyor; portföy ölçeğinde
   yeniden düşünülmeli (sembol başına değil gün başına…), ama **önce** K2.
4. Kapı yeniden çalıştırılacaksa eşikler **yeni bir plan belgesinde** önceden
   yazılmalıdır; mevcut eşikler aynen kalır (sonuç okunmadan önce sabitlendi).

## 11. Üretim ve tekrar

```bash
# birim/entegrasyon testleri (79)
python3 -m pytest test_senaryo_zaman.py test_senaryo_defter.py \
  test_senaryo_zincir.py test_senaryo_tyr.py test_senaryo_plan.py \
  test_senaryo_kurallar.py test_senaryo_yaris.py test_golge_kapi.py \
  test_golge_zincir_smoke.py -q

# duman koşu (~15 sn)
python3 research/golge_zincir.py --limit 3 --tf 4h \
  --cikti docs/arastirma/sonuclar/golge_zincir_duman

# tam koşu (~6 sa) → ölçüm (~17 sn) → kapı
python3 research/golge_zincir.py
python3 research/golge_olcum.py
python3 research/golge_kapi.py        # çıkış:0=GEÇTİ,2=GEÇMEDİ (şimdi:2)

# Faz0 bağlamı (14 sn)
python3 scripts/stop_sermaye_replay.py
```

Çıktılar: `docs/arastirma/sonuclar/golge_zincir/{golge_defter.jsonl, ozet.json,
plan_sonuc.csv, kor_baz.csv, olcum_ozet.json, kapi_karari.json}`.
