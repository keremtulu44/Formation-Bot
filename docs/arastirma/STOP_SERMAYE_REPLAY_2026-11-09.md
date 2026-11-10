# Stop & Sermaye Koruma Replay'i — Ölçüm Raporu (2026-11-09)

**Yer:** `docs/arastirma/sonuclar/stop_sermaye/` · **Betik:** `scripts/stop_sermaye_replay.py`
**Reprodüksiyon:** `python scripts/stop_sermaye_replay.py` (≈14 sn) · **Manifest:** `stop_sermaye/manifest.json` (girdi SHA256 dahil)
**Tür:** Salt ölçüm (araştırma); canlı sistem kararı değildir, hiçbir kârlılık iddiası içermez.

---

## 0. Özet — beş ana bulgu

1. **Ham giriş popülasyonu maliyetin altında:** teyitli kırılım girişlerinde baz hücre
   (stop 1,0 ATR / hedef 1,5 ATR / 10 bar) maliyetsiz beklenti **+0,090 ATR/işlem**;
   varsayımsal tur-başı maliyet 0,10 ATR'de **−0,010'a** düşüyor. Ham "her teyitli
   kırılım" işleminin tek başına sürdürülebilirliği yok; değer TYR/blok seçiciliğinden
   gelmek zorunda.
2. **"Günde 2 stop → dur" kuralı bu veride hiç tetiklenmiyor** (sembol başına günlük
   maksimum 1 stop; örtüşmesiz pencere 20 bar günlük işlemleri zaten seyreltiyor).
   Risk asıl olarak **üst üste stop serilerinde**: serilerin %60,7'si ≥3, %16,2'si ≥5
   üst üste stop görüyor; maks seri 10 (BEGYO/1h). Kural sembol-günü yerine
   **streak/portföy bazlı** kurulmalı.
3. **Dar-stop pişmanlığı düşük:** S=1,0 ile stop yiyenlerin yalnız **%4,05'i** (10 bar)
   / **%8,58'i** (20 bar) S=1,5 ile hedefe varabiliyor; %82'si genişletilmiş stopla da
   aynı şekilde duruyor. Derin dalıp hedefe gidenlerin oranı düşük → 1,0 ATR
   "tez ölümü" stopu bu popülasyonla **tutarlı**.
4. **Gürültü toleransı gerçek:** 20 barda +1,5'e varanların önceki geri çekilmesi
   p50=0,17 / p75=0,74 / **p90=1,48 ATR**; %18,1'i 1,0 ATR'den, %9,75'i 1,5 ATR'den
   derine inip hedefe varıyor (kısmi "shake-out" payı). Buna karşılık bu payın çoğu
   genişletilmiş stopla da kazanca dönüşmüyor (bkz. 3).
5. **Dönem kararlı, TF farkı büyük:** keşif +0,0918 ↔ doğrulama +0,0870 (yakın);
   TF bazında **4h en güçlü (+0,125), 1d en zayıf (+0,025)** — günlük TF'de ham giriş
   popülasyonu tek başına neredeyse kârsız.

---

## 1. Metodoloji

| Öğe | Değer |
|---|---|
| Girdi | `sonuclar/teyit_sonrasi/teyit_sonrasi_olaylar.csv.gz` — teyitli kırılım girişleri (174 sembol × 4 TF) |
| Olay | 18.495 satır → 18.352 geçerli yol (0 eşleşmeyen, 143 sağdan sansürlü) |
| Giriş | teyit barının kapanışı; birim = teyit anındaki ATR (o an dondurulur) |
| Yol | teyit barından sonraki **kapanmış barlar** yalnız (geleceğe bakma yok); 2h/4h seansa hizalı resample, 1d native |
| Yarış | ilk dokunuş: hedef ≥T vs stop ≤ −S; **aynı barda çift dokunuş → stop** (muhafazakâr) |
| Izgara | S ∈ {0,5; 0,75; 1,0; 1,25; 1,5} × T ∈ {1,0; 1,5; 2,0} × H ∈ {10; 20} |
| Otokorelasyon | sembol×TF kronolojik, 20 bar örtüşmesiz seçme → **15.808 işlem** |
| Dönem | keşif/doğrulama (girdideki periyot etiketi) — keşif 11.086 / doğrulama 4.722 |
| Eşik | n≥30 yeterli (tüm ızgara hücresi n≥1.166) |
| Sansür | eksik pencere sonuç sayılmaz ("yok" olarak raporlanır) |

---

## 2. Stop ızgarası (ideal, maliyetsiz; beklenti = (hedef×T − stop×S)/n)

### 2.1 Ufuk 10 bar (`stop_grid.csv`)

| S | T | n | stop % | hedef % | yok % | koşullu hedef % | **beklenti ATR** | ort. çözüm |
|---|---|---|---|---|---|---|---|---|
| 0,50 | 1,0 | 15.808 | 55,0 | 39,7 | 5,3 | 42,0 | **+0,123** | 3 |
| 0,50 | 1,5 | 15.808 | 58,5 | 30,0 | 11,5 | 33,9 | **+0,158** | 3 |
| 0,50 | 2,0 | 15.808 | 60,1 | 22,0 | 17,9 | 26,8 | +0,139 | 3 |
| 0,75 | 1,5 | 15.808 | 50,2 | 32,7 | 17,0 | 39,5 | +0,114 | 4 |
| **1,00** | **1,5** | **15.808** | **42,8** | **34,6** | **22,7** | **44,7** | **+0,090** | **4** |
| 1,00 | 2,0 | 15.808 | 43,9 | 25,3 | 30,7 | 36,6 | +0,067 | 5 |
| 1,25 | 1,5 | 15.808 | 36,5 | 35,6 | 27,9 | 49,4 | +0,078 | 5 |
| 1,50 | 1,5 | 15.808 | 31,1 | 36,3 | 32,7 | 53,9 | +0,078 | 5 |
| 1,50 | 2,0 | 15.808 | 31,8 | 26,5 | 41,7 | 45,4 | +0,052 | 5 |

(Kalan hücreler dosyada: 15 hücrenin tamamı.)

### 2.2 Ufuk 20 bar — seçilmiş hücreler

| S | T | stop % | hedef % | yok % | beklenti ATR |
|---|---|---|---|---|---|
| 0,50 | 1,5 | 63,2 | 35,0 | 1,8 | +0,209 |
| 0,50 | 2,0 | 66,8 | 29,2 | 4,1 | **+0,250** |
| **1,00** | **1,5** | 51,4 | 43,1 | 5,5 | **+0,133** |
| 1,50 | 1,0 | 37,7 | 56,8 | 5,5 | +0,002 |

**Okuma:** ideal koşullarda dar stop + geniş hedef (0,5/2,0) beklentiyi maksimize
ediyor — ama durdurma oranı %60–67'e çıkıyor ve bu sıralama maliyetle tersine
dönmekte (bkz. §4). Baz hücre (1,0/1,5) denge noktası olarak korunabilir.

### 2.3 Dönem ve TF kırılımı

| Dilim | n | stop % | hedef % | beklenti ATR |
|---|---|---|---|---|
| keşif (discovery) | 11.086 | 42,7 | 34,6 | +0,0918 |
| doğrulama (validation) | 4.722 | 43,0 | 34,5 | +0,0870 |

| TF (S=1,0/T=1,5/H=10) | n | stop % | beklenti ATR |
|---|---|---|---|
| 1h | 7.746 | 42,3 | +0,074 |
| 2h | 4.260 | 42,3 | +0,117 |
| **4h** | **2.636** | **42,6** | **+0,125** |
| **1d** | **1.166** | **48,3** | **+0,025** |

1d'de S=0,5/T=1,0 hücresi daha iyi (+0,102) — günlük TF'de dar stop/erken hedef
daha uygun görünüyor (ama maliyet duyarlılığı yüksek, §4).

---

## 3. Gürültü toleransı ve dar-stop pişmanlığı

### 3.1 Kısıtsız MAE — +1,5'e VARDIĞI halde ne kadar geri çekildi (`kisitsiz_mae.csv`, 20 bar)

| Grup | n | p50 | p75 | p90 | p95 | >1,0 ATR | >1,5 ATR |
|---|---|---|---|---|---|---|---|
| tümü | 8.326 | 0,169 | 0,743 | 1,482 | 2,077 | %18,1 | %9,75 |
| 1d | 621 | 0,163 | 0,902 | 1,696 | 2,319 | %22,9 | %12,7 |
| 4h | 1.408 | 0,149 | 0,752 | 1,464 | 1,940 | %17,8 | %9,8 |

→ Hedefe gidenlerin beşte biri 1 ATR'den derine iniyor: **stop=1,0 bazı iyi
işlemleri kesebilir**. Ama…

### 3.2 …ve kesilenler geri gelmiyor (`dar_stop_pismanligi*.csv`)

| Senaryo | n | sonra hedefe varan | yine stop | yok |
|---|---|---|---|---|
| S=1,0'da stop yiyenler → S=1,5 ile, H=10 | 6.764 | **%4,05** | %72,6 | %23,4 |
| aynı, H=20 | 8.125 | **%8,58** | %81,9 | %9,5 |

→ Derin dalışların %73–82'si genişletilmiş stopla da sonuçlanmıyor. **1,0 ATR
"tez ölümü" stopu bu popülasyon için savunulabilir**; 0,5 ATR'ye inmek ideal
beklentiyi yükseltiyor ama durdurma oranını %55–60'a çıkarıp maliyete duyarlı
hale getiriyor.

### 3.3 Zaman (`mae_ve_zaman.csv`)

- Çözüm süresi (baz hücre): medyan 4 bar; **%63,7'si 5 bar içinde**, %40,5'i 3 bar içinde.
- Hedefe gidenlerin ortalama bekleme H=10'da 4–5 bar → 10-bar ufuk makul.

---

## 4. Maliyet duyarlılığı (`maliyet_duyarlilik.csv`) — VARSAYIMSAL

Tur-başı maliyet varsayımları (spread+komisyon+kayma, ATR cinsinden; **ölçülmedi**):
0 / 0,05 / 0,10 / 0,20.

**H=10, maliyet 0,10 ATR'de net pozitif kalan hücreler:**

| S | T | maliyetsiz | net (0,10) |
|---|---|---|---|
| 0,50 | 1,5 | +0,158 | **+0,058** |
| 0,50 | 2,0 | +0,139 | +0,039 |
| 0,50 | 1,0 | +0,123 | +0,023 |
| 0,75 | 1,5 | +0,114 | +0,014 |
| **1,00** | **1,5 (karne)** | +0,090 | **−0,010** |

→ **Sonuç:** ham popülasyon tek başına 0,10 ATR maliyeti kaldırmıyor. Karne varsayılanı
(1,0/1,5) ancak giriş kalitesi (blok/TYR seçiciliği) veya daha düşük maliyetle
(kayda değer: 0,05'te +0,040) yaşar. Bu, senaryo motoru tezinin kanıt yükünü
**artırır**: seçicilik zorunluluktur, süs değildir.

---

## 5. Sermaye koruma (`sermaye_sim.csv`, `sermaye_ozet.json`, `seri_kural_ozet.json`)

Baz hücre, 692 sembol×TF serisi, 15.808 işlem (kural-dışı toplam **+1.429 ATR**).

| Ölçüm | Değer |
|---|---|
| üst üste stop serisi (medyan maks) | **3** |
| üst üste stop serisi (maks) | **10** (BEGYO/1h: −5,5 ATR; BERA/1d: −9 ATR; ESCAR/1h DD 14,5) |
| ≥3 üst üste stop gören seri oranı | **%60,7** |
| ≥5 üst üste stop gören seri oranı | **%16,2** |
| maks düşüş (medyan) | **4,0 ATR** (≈ 4R) |
| maks düşüş (maks) | **17,5 ATR** |
| aynı günde 2+ stop (sembol×TF) | **hiç yok** (maks 1/gün) |

### Kural testleri

| Kural | Etki |
|---|---|
| "aynı günde 2 stop → gün sonu dur" (sembol-günü) | **hiç tetiklenmedi**; atılan işlem 0, toplam etki 0 ATR |
| "sembol×TF'de 3 üst üste stop → sıradakini atla" | 655 işlem atlandı; toplam +1.429 → **+1.404,5 ATR (−%1,7)** |

**Yorum:** amaç beklentiyi büyütmek değil derinlik kesmektir; seri kuralının toplam
beklentiye maliyeti küçük (%1,7) ama düşüşü ne kadar kesiği **gölge defterde**
ölçülecek (bu replay sembol-bazlıdır; portföy-birleşik-DD etkisi ayrı gölge
defter işidir). Kural metriği streak tabanlı kurulmalı; "günde 2 stop" bu veri
yapısında anlamsız.

---

## 6. Bu replay'den çıkan yeni sorunlu noktalar

| # | Bulgu | Etki | Öneri |
|---|---|---|---|
| 1 | Ham teyitli-kırılım popülasyonu maliyetle (0,10 ATR) sıfırın altında | "Her teyitli kırılım = işlem" sürdürülemez | TYR RET/uygun eşikleri ve blok girişi bu bulguya bağlanır; Faz 2'de maliyet modeli zorunlu |
| 2 | "Günde 2 stop" kuralı hiç tetiklenmiyor; gerçek risk streak (%60,7 seri ≥3) | Mevcut kural tasarımı etkisiz | Kuralı streak/portföy bazlı yenile (senaryo motoru §3 kural metni) |
| 3 | 1d'de ham giriş neredeyse kârsız (+0,025) | Günlük TF'de ayrı giriş standardı gerekebilir | TF-bazlı stop/hedef varsayılanına izin ver (tek küresel varsayım değil) |
| 4 | Hedefe gidenlerin %18'i 1,0 ATR altına iniyor ama %73–82'i geniş stopla da kazanca dönüşmüyor | 1,0 ATR stopu tutarlı; aşırı genişletme gereksiz | Stop = tez ölümü 1,0 ATR'de kal (daraltma 0,5'e yalnız düşük maliyetle tartışılır) |
| 5 | 143 olay sağdan sansürlü, 0 eşleşmeyen — veri bütün | — | — (kayıt) |
| 6 | `grafik_uret.py:649` `stabil_direncleri(..., yukari_kirildi=None, asagi_kirildi=None)` sabit None; `:1052` 2/5/7 eşikleri yerel tekrar | kararlar tek noktada toplanmıyor | Faz 1'de yalnız yeni pakette çözümle (ana sisteme dokunma) |
| 7 | `signals.py` `multi_bar_recovery` + `weak_reclaim` reclaim türleri — karne sözlüğünde yalnız `intrabar_sweep_reclaim`/`break` var (s2) | karne açıklaması eksik | s2 bekliyor; domain sözlüğüne işlendi |

---

## 7. Plan güncellemesi (senaryo motoru belgesine işlenmiştir)

- **Faz 0 (ölçüm): TAMAM** — domain sözlüğü + bu replay + MAE/kural/maliyet ölçümleri.
- **Sıradaki adım — Faz 1: gölge defter** (yeni `senaryo/` paketi, ana sisteme dokunmadan):
  varsayımlar sözlüğünü bu rapordan türet (S=1,0/T=1,5/H=10 doğrulamalı;
  1d için 0,5/1,0 alternatifi; streak kuralı; maliyet 0,05–0,10 varsayımı).
- **Faz 2:** TYR kararları + maliyetli net beklenti; **Faz 3:** kâr/kayıp;
  **Faz 4:** psikoloji (streak kuralı burada devreye girer); **Faz 5:** B4 ön
  koşulları. Karne varsayılanları değişmez (§4 belge): yalnız senaryo motoru
  gölge varsayımları.

## 8. Dosya indeksi

| Dosya | İçerik |
|---|---|
| `stop_grid.csv` | 15 hücre × 2 ufuk, tam ızgara |
| `stop_grid_tf.csv` | TF kırılımı (5 hücre × TF × ufuk) |
| `stop_grid_donem.csv` | keşif/doğrulama (baz hücre) |
| `kisitsiz_mae.csv` | kısıtsız gürültü toleransı (TF'li) |
| `dar_stop_pismanligi.csv` / `_ufuk20.csv` | dar stop regresyonu |
| `mae_ve_zaman.csv` | kazanç MAE'si + çözüm süresi |
| `maliyet_duyarlilik.csv` | 4 maliyet senaryosu × tüm hücreler |
| `sermaye_sim.csv` | 692 seri, kural-dışı/kural-lı metrikler |
| `sermaye_ozet.json` / `seri_kural_ozet.json` | sermaye özeti, streak kuralı |
| `manifest.json` | girdi SHA256, parametreler, kurallar |

**Yasak ihlali yok:** yalnız ileri barlar; sansür sonuç sayılmadı; otokorelasyon
için örtüşmesiz seçme uygulandı; keşif/doğrulama bölünmesi korundu; maliyetler
açıkça varsayımsal etiketlendi.
