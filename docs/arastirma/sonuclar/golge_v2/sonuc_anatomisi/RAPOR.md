# Gölge v2 — Sonuç Anatomisi: Kim Kazandı, Kim Kaybetti, Nasıl Kaybetti

> Üretici: `python -m research.golge_v2_sonuc_anatomisi`. Bu dosya elle düzenlenmez.

- Kapsam: `4h + 1d` birincil işlemler (sansürsüz, veri karantinası dışı), Mod 0, `2.0 ATR` hedef, 10 mum ufuk, `30 bps` masraf. İşlem: `4233`.
- Yarış yeniden koşulmadı: sonuçlar ana CSV'den okundu, yol fiyat arşivinden çözüldü. Arşivden yürütülen yol `4233` işlemin hepsinde CSV'deki çıkış nedeni, çıkış mumu ve MFE ile aynı; stop sonrası alanlar CSV'nin ufuk kapanışı ve 10 mumluk saf yol MFE'siyle tutarlı.
- Ana raporla eşitlik (N ve net ortalama): D7 `637` / `+0.1147 R`; D6 `1124` / `+0.0611 R`; D1 `4233` / `+0.0100 R` — aynı.
- Saat çözünürlüğü: `4h` AYNI `2820`, KAPSAM_DISI `2`, ONCE_HEDEF `3`; `1d` AYNI `1160`, KAPSAM_DISI `2`, ONCE_HEDEF `1`, TUTARSIZ `15`, VERI_YOK `230`. `AYNI`: saatlik yol aynı mumda aynı sonucu veriyor. `ONCE_HEDEF`: aynı mumda saatlik veride önce hedef görülüyor. `VERI_YOK`: o tarihlerde saatlik arşiv yok. `TUTARSIZ`: günlük ve saatlik arşiv uyuşmuyor. `KAPSAM_DISI`: tez iptaliyle kapanan işlem (yapı kararı; fiyat yolundan türetilemez). Saatlik tablolara yalnız `AYNI` girer.

**Okuma kılavuzu.** `R`: işlemin başlangıç riski (giriş ile stop arası). `Net`: 30 bps masraf düşülmüş. `Mum`: işlemin kendi zaman dilimindeki mum (4s işlemde 4 saatlik, günlükte günlük). Mum çözünürlüğünde stop mumunun içindeki sıra bilinmez; o yüzden "stoptan önce görülen kâr" stop mumunu saymaz ve alt sınırdır. Saat çözünürlüğü stop mumunun içini saat saat açar; stop saatinin kendi içi yine bilinmez.

**Sınırlar.** Bu rapor betimleyicidir: olanı sayar, bir kuralın değerini ölçmez. "Stopların şu kadarı önce kâr gördü" stopu taşımanın kazandırdığı anlamına gelmez (ölçümü: `../surec_olcum/RAPOR.md`). Piyasa tablosu işlem bittikten sonra bilinen bir büyüklüğe bakar. Giriş koşulu tabloları ilişki gösterir; çok sayıda kesit sınandı ve çoklu karşılaştırma düzeltmesi yok. Kümeler iç içedir (D7 ⊂ D6 ⊂ D1).

## Kısa özet (D7)

- **Sonuç:** `637` işlem; kâr eden `323 (50.7%)`, zarar eden `314 (49.3%)`. Kazanan ortalama `+1.266 R`, kaybeden `-1.070 R`; işlem başına net `+0.115 R`.
- **Zarar edenler:** stop olan `280 (89.2%)`; stop olmadan, süre dolunca zararda kapanan `34 (10.8%)` (ortalama `-0.345 R`).
- **Stopun hızı:** girişten sonraki ilk mumda `48 (17.1%)`; açılış boşluğuyla `25 (8.9%)` (boşluk, stop başına ortalama `0.327 R` fazladan kayıp).
- **Önce kâr, sonra stop:** stop olanların `110 (39.3%)` kadarı stoptan önce en az `+0.5 R`, `45 (16.1%)` kadarı en az `+1 R` görmüştü (mum çözünürlüğü, alt sınır; saat çözünürlüğünde `43.7%` ve `18.1%`).
- **Uyarısız stop:** stopların `205 (73.2%)` kadarında stoptan önce tez seviyesinin ters tarafında tek bir kapanış yoktu (ilk mumda stop `48` + son kapanışı hâlâ doğru tarafta olan `157`).
- **Stoptan sonra:** stop olanların `41 (14.6%)` kadarı stoptan sonra özgün hedefe ulaştı; `129 (46.1%)` kadarı ufuk sonunda stopun da ötesindeydi.
- **Piyasa:** stop olanların `53.5%` kadarında endeks işlem süresince en az `%0.5` ters gitti; hedefe ulaşanlarda bu oran `16.3%`, endeksin lehte gittiği pay `57.8%`.
- **Stop mesafesi:** stopu `1 ATR` ya da daha yakın olan `192` işlemin `62.5%` kadarı stop oldu (net `+0.056 R`); daha geniş stoplu `445` işlemde `36.0%` (net `+0.140 R`).
- **Haftalar:** `90` haftanın en iyi `5` tanesi `+67.4 R` üretti; onlar olmadan toplam net `+5.7 R` (hepsiyle `+73.1 R`).
- **Masraf:** brüt toplam `+147.2 R`, masraf `74.1 R` (brütün `50.4%` kadarı), net `+73.1 R`.

## Üç kümede aynı oranlar

| Oran | D7 | D6 | D1 |
|---|---:|---:|---:|
| İşlem | 637 | 1124 | 4233 |
| Kâr eden | 50.7% | 48.5% | 42.9% |
| İşlem başına net R | +0.115 | +0.061 | +0.010 |
| İşlem başına masraf R | 0.116 | 0.111 | 0.131 |
| Stop olan (işlemlerin payı) | 44.0% | 44.8% | 51.0% |
| Hedefe ulaşan (işlemlerin payı) | 41.1% | 39.8% | 33.9% |
| Süre dolan (işlemlerin payı) | 14.9% | 15.4% | 15.0% |
| Stopların: ilk mumda | 17.1% | 13.9% | 20.5% |
| Stopların: açılış boşluğuyla | 8.9% | 7.1% | 7.4% |
| Stopların: önce ≥ +0.5 R gördü (mum) | 39.3% | 38.7% | 37.8% |
| Stopların: önce ≥ +1 R gördü (mum) | 16.1% | 14.3% | 17.7% |
| Stopların: uyarı kapanışı yoktu | 73.2% | 73.0% | 71.9% |
| Stopların: sonra hedefe gitti | 14.6% | 12.1% | 13.4% |
| Stopların: ufuk sonunda stopun ötesinde | 46.1% | 50.2% | 49.0% |
| Stopların: endeks ≥ %0.5 ters | 53.5% | 56.4% | 54.6% |
| Hedeflerin: endeks ≥ %0.5 ters | 16.3% | 17.3% | 14.9% |

## D7_A_Arti — 637 işlem

### 1. Genel tablo

| | İşlem | Pay | Ortalama net R | Toplam net R |
|---|---:|---:|---:|---:|
| Kâr eden | 323 | 50.7% | +1.266 | +409.0 |
| Zarar eden | 314 | 49.3% | -1.070 | -335.9 |
| Tümü | 637 | 100.0% | +0.115 | +73.1 |

- Brüt toplam `+147.2 R`; masraf `74.1 R` (işlem başına `0.116 R`, brütün `50.4%` kadarı); net `+73.1 R`.
- Ortalama kazancın ortalama kayba oranı `1.18`. Bu oranla sıfır beklenti için işlemlerin `45.8%` kadarının kâr etmesi gerekir; gerçekleşen `50.7%`.
- Brütte artıda olup masraf yüzünden zarara düşen işlem: `3`.
- Medyan stop mesafesi `1.29 ATR`; hedef `2.0 ATR`, yani medyan işlemde `1.55 R`.

| Dönem | İşlem | Kâr eden | Stop | Hedef | Net R |
|---|---:|---:|---:|---:|---:|
| kesif | 414 | 47.8% | 45.9% | 39.1% | +0.054 |
| dogrulama | 223 | 56.1% | 40.4% | 44.8% | +0.227 |

### 2. İşlemler nasıl kapandı

| Çıkış | İşlem | Pay | Kârda | Zararda | Ortalama net R | Toplam net R | Medyan mum |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hedefe ulaştı | 262 | 41.1% | 262 | 0 | +1.431 | +374.9 | 3 |
| Stop oldu | 255 | 40.0% | 0 | 255 | -1.131 | -288.3 | 3 |
| Açılış boşluğuyla stop oldu | 25 | 3.9% | 0 | 25 | -1.436 | -35.9 | 3 |
| Süre doldu (ne stop ne hedef) | 95 | 14.9% | 61 | 34 | +0.235 | +22.4 | 10 |

### 3. Zarar edenler nasıl kaybetti

Her zarar eden işlem tek satırdadır; paylar %100'e toplanır. Sıra önceliktir: boşlukla stop olan işlem, öncesinde ne görmüş olursa olsun `Açılış boşluğu` satırındadır. Kâr eşikleri stop mumundan ÖNCE görülen en iyi andır.

| Kayıp yolu | İşlem | Zarar edenlerin payı | Tüm işlemlerin payı | Ortalama net R | Toplam net R | Toplam zarardaki pay |
|---|---:|---:|---:|---:|---:|---:|
| Stop olmadı; süre doldu, zararda kapandı | 34 | 10.8% | 5.3% | -0.345 | -11.7 | 3.5% |
| Açılış boşluğu stopu atladı | 25 | 8.0% | 3.9% | -1.436 | -35.9 | 10.7% |
| Girişten sonraki ilk mumda stop | 47 | 15.0% | 7.4% | -1.152 | -54.1 | 16.1% |
| 2+ mum yaşadı, +0.25 R'yi hiç görmedi | 58 | 18.5% | 9.1% | -1.121 | -65.0 | 19.4% |
| +0.25–0.5 R gördü, döndü | 51 | 16.2% | 8.0% | -1.106 | -56.4 | 16.8% |
| +0.5–1 R gördü, geri verdi | 60 | 19.1% | 9.4% | -1.131 | -67.9 | 20.2% |
| +1 R ve üstünü gördü, geri verdi | 39 | 12.4% | 6.1% | -1.151 | -44.9 | 13.4% |

### 4. Stop olanlar stoptan önce ne kadar kâr gördü

Stop olan işlem: `280 (44.0%)` (zarar edenlerin `89.2%` kadarı). Saat çözünürlüğünde çözülen stop: `254`.

| Stoptan önce en az | Mum çözünürlüğü (280 stop) | Saat çözünürlüğü (254 stop) | Aynı 254 stopta mum |
|---|---:|---:|---:|
| +0.25 R | 162 (57.9%) | 161 (63.4%) | 148 (58.3%) |
| +0.5 R | 110 (39.3%) | 111 (43.7%) | 100 (39.4%) |
| +1 R | 45 (16.1%) | 46 (18.1%) | 41 (16.1%) |
| +1.5 R | 18 (6.4%) | 16 (6.3%) | 15 (5.9%) |

- Kaçıncı mumda stop: 1. mum `48 (17.1%)`; 2–3. mum `108 (38.6%)`; 4–6. mum `82 (29.3%)`; 7–10. mum `42 (15.0%)`. Medyan `3`. mum.
- Stop mumundan önce girişin kâr tarafında tek bir fiyat görmeyen: `66 (23.6%)` (ilk mumda stop olanlar dahil).
- Hedefe ne kadar yaklaşıp döndüler: hedef yolunun en az %50 kadarı `58 (20.7%)`; hedef yolunun en az %75 kadarı `23 (8.2%)`; hedef yolunun en az %90 kadarı `8 (2.9%)`.
- Stop ile hedef aynı mumda görülen (sıra bilinmediği için stop sayılan) işlem: `2`. Saatlik veride önce hedefin görüldüğü stop: `0`.

### 5. Girişten sonraki ilk mumda stop olanlar

- İşlem: `48` — stopların `17.1%`, bütün işlemlerin `7.5%` kadarı. Açılış boşluğuyla olan: `1`.
- Stop mesafesi `1 ATR` ya da daha yakın olan: `35 (72.9%)`. Dar stoplu işlemlerin `18.2%` kadarı ilk mumda stop oldu; daha geniş stoplularda `2.9%`.
- Saat çözünürlüğünde çözülen: `40`. Mumun ilk saatinde stop `12`, ilk iki saatinde `19`.
- Aynı `40` işlemde stoptan önce `+0.25 R`'yi hiç görmeyen (doğrudan stop): `31 (77.5%)`. Önce kâr görüp aynı mumda dönen: ≥ +0.25 R `9`; ≥ +0.5 R `7`; ≥ +1 R `2`.

| Giriş (zaman dilimi, olay mumunun kapanış saati) | İşlem | İlk mumda stop | Oran |
|---|---:|---:|---:|
| 1d 18:30 | 203 | 23 | 11.3% |
| 4h 13:30 | 262 | 21 | 8.0% |
| 4h 17:30 | 153 | 1 | 0.7% |
| 4h 18:00 | 18 | 2 | 11.1% |

### 6. Açılış boşluğuyla stop olanlar

- İşlem: `25 (8.9%)` (stopların payı). Zaman dilimi: 4h `16`, 1d `9`.
- İşlem gününün ilk mumunda (gece boşluğu) olan: `25`. Girişten sonraki ilk mumda olan: `1`.
- Ortalama brüt sonuç `-1.327 R`, en kötü `-2.912 R`. Stop fiyatı yerine açılıştan dolmanın ek kaybı ortalama `0.327 R`, toplam `8.2 R`.
- Boşluktan önce en az `+0.5 R` görmüş olan: `11`.

### 7. En az +0.5 R görüp stop olanlar

- İşlem: `110 (39.3%)` (stopların payı); bunların `45` kadarı en az `+1 R` gördü. Gördükleri en iyi anın medyanı `+0.94 R`.
- En iyi andan stopa kaç mum geçti: 1 mum `34 (30.9%)`; 2 mum `32 (29.1%)`; 3 mum `19 (17.3%)`; 4+ mum `25 (22.7%)`. Medyan `2` mum.
- Hedefe ne kadar yaklaşmışlardı: hedef yolunun en az %50 kadarı `57 (51.8%)`; hedef yolunun en az %75 kadarı `23 (20.9%)`; hedef yolunun en az %90 kadarı `8 (7.3%)`.

### 8. Stoptan önce uyarı var mıydı

Stop, tez seviyesinin 0.5 ATR ötesindedir. Kapanışa bakan bir kural ancak stoptan önce seviyenin ters tarafında bir kapanış varsa devreye girebilir.

- Hiç kapanış görülmeden (ilk mumda) stop: `48 (17.1%)`.
- Son kapanış hâlâ seviyenin doğru tarafındayken, tek mumda seviyeyi ve tamponu geçip stop: `157 (56.1%)`.
- Son kapanış seviyenin ters tarafındayken stop: `75 (26.8%)`. (Stoptan önce herhangi bir kapanışta seviyenin ters tarafını gören: `89`.)
- Stop mumu başlarken fiyatın stopa uzaklığı: medyan `0.81 ATR`; `187 (66.8%)` stopta 1 ATR ya da daha az, `75 (26.8%)` stopta 0.5 ATR ya da daha az. Yani stopların çoğu için sıradan büyüklükte tek bir ters mum yetti.
- Stop mumundan önceki son kapanışta işlemin açık sonucu: medyan `-0.21 R`; kârda olan `62 (22.1%)`, en az `+0.5 R` kârda olan `12 (4.3%)` (ilk mumda stop olanlar için giriş anı, yani 0 R).

| Stoptan önceki son tez durumu | Stop | Stopların payı | Aynı durumdan hedefe giden |
|---|---:|---:|---:|
| Hiç kapanış görülmedi (ilk mumda çıkış) | 48 | 17.1% | 39 |
| Tez henüz teyit almamıştı | 25 | 8.9% | 29 |
| Tez teyitliydi | 127 | 45.4% | 192 |
| Tez sınanıyordu | 58 | 20.7% | 2 |
| Tez bozulmuştu | 22 | 7.9% | 0 |

İşlem açıkken en az bir kapanışta görülen etiketler — en az bir kapanış görmüş `232` stop ve `284` kazanan:

| Görülen | Stop olanlarda | Kâr edenlerde |
|---|---:|---:|
| Kapanış tez seviyesinin ters tarafında | 89 (38.4%) | 9 (3.2%) |
| Formasyon retest ediliyor | 49 (21.1%) | 5 (1.8%) |
| Formasyon: başarısız kırılım | 6 (2.6%) | 0 (0.0%) |
| Kapanış girişin zarar tarafında | 189 (81.5%) | 118 (41.5%) |
| Ters yönlü kapanış | 208 (89.7%) | 190 (66.9%) |
| Karşı Stabil çizgisinde ret | 55 (23.7%) | 41 (14.4%) |
| Karşı OB/FVG bandında ret | 55 (23.7%) | 108 (38.0%) |
| Ters hacim baskısı | 47 (20.3%) | 49 (17.3%) |
| Ters yönlü yapı olayı (iç/dış; sweep dahil) | 57 (24.6%) | 43 (15.1%) |
| Sistemin kendi karşı yön adayı | 25 (10.8%) | 12 (4.2%) |
| Formasyon kırılımı teyit aldı (lehte) | 178 (76.7%) | 247 (87.0%) |

Bu tablo sonuç-koşulludur: stopa giden yol zaten zarardan ve çoğu kez seviyenin içinden geçer. Bir etiketin stop olanlarda sık görülmesi, o etikette çıkmanın kazandırdığını göstermez; onu `surec_olcum/RAPOR.md` ölçer.

### 9. Stop olduktan sonra fiyat ne yaptı

İşlemin özgün ufku (10 mum) bitene kadar, stop mumundan SONRAKİ mumlara bakılır. Stop mumunun kendi içindeki dönüş sayılmaz.

| Stoptan sonra | Tüm stoplar (280) | İlk mumda stop (48) | +0.5 R görmeden stop (122) | +0.5 R görüp stop (110) |
|---|---:|---:|---:|---:|
| Stoptan sonra özgün hedefe ulaştı | 41 (14.6%) | 9 (18.8%) | 17 (13.9%) | 15 (13.6%) |
| Hedefe ulaşmadı ama ufuk sonunda girişin kâr tarafında | 42 (15.0%) | 6 (12.5%) | 15 (12.3%) | 21 (19.1%) |
| Ufuk sonunda giriş ile stop arasında | 64 (22.9%) | 5 (10.4%) | 34 (27.9%) | 25 (22.7%) |
| Ufuk sonunda stopun da ötesinde | 129 (46.1%) | 28 (58.3%) | 56 (45.9%) | 45 (40.9%) |
| Stop ufkun son mumunda; sonrası yok | 4 (1.4%) | 0 (0.0%) | 0 (0.0%) | 4 (3.6%) |

### 10. Stop olmadan kapananlar (süre doldu)

- İşlem: `95 (14.9%)`; toplam net `+22.4 R`.
- Kârda kapanan `61` (ortalama `+0.559 R`); zararda kapanan `34` (ortalama `-0.345 R`).
- Zararda kapananların `17` kadarı yol boyunca en az `+0.5 R`, `3` kadarı en az `+1 R` görmüştü; `3` kadarı brütte artıdaydı, masraf zarara çevirdi.
- Kârda kapananlar hedef yolunun medyan `%75` kadarını görmüştü; `29` kadarı yol boyunca en az `0.5 R` aleyhte kalmıştı.
- İki yöne de `0.5 R` oynamadan süresi dolan: `4`.

### 11. Zora girip kurtaranlar

İşlem aleyhte şu kadar R gördükten sonra nasıl bitti? (Çıkış mumunun geri kalanı sayılmaz; stop olan her işlem tanım gereği 1 R görür.)

| Aleyhte en az | Gören işlem | Stop oldu | Kârla kapandı | Bunlardan hedefe giden | Stop olmadan zararda kapandı |
|---|---:|---:|---:|---:|---:|
| 0.25 R | 472 | 280 (59.3%) | 158 (33.5%) | 115 | 34 |
| 0.5 R | 392 | 280 (71.4%) | 83 (21.2%) | 54 | 29 |
| 0.75 R | 323 | 280 (86.7%) | 32 (9.9%) | 18 | 11 |

### 12. Kâr edenler nasıl kazandı

- Kâr eden `323` işlemin `262` kadarı hedefe ulaştı (ortalama `+1.431 R`; hedef ortalama `1.54 R` uzaktaydı), `61` kadarı süre dolunca kârda kapandı (ortalama `+0.559 R`).
- Hedefe kaçıncı mumda ulaşıldı: 1. mum `39 (14.9%)`; 2–3. mum `104 (39.7%)`; 4–6. mum `70 (26.7%)`; 7–10. mum `49 (18.7%)`. Medyan `3`. mum.
- Hedefe ulaşanların hedeften önce aleyhte gördüğü: ≥ 0.25 R `115 (43.9%)`; ≥ 0.5 R `54 (20.6%)`; ≥ 0.75 R `18 (6.9%)`.

### 13. Piyasa işlem açıkken ne yaptı

`XU100`, giriş anından çıkış mumunun kapanışına kadar, işlemin YÖNÜNE göre (short işlemde endeksin düşmesi lehtedir). `±%0.5` içi yatay sayılır. Endeks sembollerinin kendi işlemleri ölçülmez. Bu, giriş anında BİLİNMEYEN bir büyüklüktür.

| Çıkış | Ölçülen işlem | Endeks ters | Endeks yatay | Endeks lehte | Endeksin ortalama hareketi |
|---|---:|---:|---:|---:|---:|
| Stop oldu | 275 | 147 (53.5%) | 71 (25.8%) | 57 (20.7%) | -0.99% |
| Hedefe ulaştı | 258 | 42 (16.3%) | 67 (26.0%) | 149 (57.8%) | +1.14% |
| Süre doldu | 94 | 24 (25.5%) | 18 (19.1%) | 52 (55.3%) | +0.53% |

İşlem süresince endeksin hareketine göre:

| İşlem süresince endeks | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| %2'den fazla ters | 86 | 72.1% | 9.3% | 12.8% | 25.6% | -0.551 | [-0.795, -0.298] | -0.474 (61) | -0.738 (25) | 1.72 | 0.087 |
| %0.5–2 ters | 127 | 66.9% | 12.6% | 24.4% | 26.8% | -0.466 | [-0.684, -0.232] | -0.610 (84) | -0.185 (43) | 1.68 | 0.114 |
| yatay (±%0.5) | 156 | 45.5% | 10.3% | 42.9% | 52.6% | +0.057 | [-0.158, +0.272] | +0.092 (101) | -0.009 (55) | 1.72 | 0.129 |
| %0.5–2 lehte | 143 | 27.3% | 4.2% | 51.7% | 64.3% | +0.464 | [+0.235, +0.695] | +0.309 (93) | +0.752 (50) | 1.62 | 0.119 |
| %2'den fazla lehte | 115 | 15.7% | 0.9% | 65.2% | 76.5% | +0.908 | [+0.668, +1.183] | +0.957 (68) | +0.838 (47) | 1.64 | 0.102 |

Tabloda yok: ölçülemeyen `10` işlem.

Girişten ÖNCEKİ 5 mumda endeksin hareketine göre (giriş anında bilinir):

| Girişten önce endeks | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| %2'den fazla ters | 24 | 45.8% | 20.8% | 37.5% | 54.2% | +0.228 | [-0.335, +0.818] | +0.513 (13) | -0.108 (11) | 1.74 | 0.088 |
| %0–2 ters | 97 | 43.3% | 7.2% | 44.3% | 54.6% | +0.124 | [-0.176, +0.414] | +0.118 (68) | +0.137 (29) | 1.64 | 0.121 |
| %0–2 lehte | 238 | 44.1% | 5.0% | 40.3% | 48.3% | +0.133 | [-0.068, +0.338] | +0.019 (152) | +0.334 (86) | 1.73 | 0.132 |
| %2'den fazla lehte | 268 | 43.7% | 8.6% | 41.0% | 51.1% | +0.089 | [-0.101, +0.270] | +0.031 (174) | +0.198 (94) | 1.63 | 0.095 |

Tabloda yok: ölçülemeyen `10` işlem.

### 14. Zarar hangi giriş koşullarında yoğunlaşıyor

`En kötü GA`: net R ortalamasının sembol / gün / hafta / ay kümeli %95 aralıklarının en düşük alt ve en yüksek üst sınırı. Bu tablolar ilişki gösterir; çok sayıda kesit olduğu için tek bir satır kural gerekçesi değildir.

**Stop mesafesi** (giriş ile stop arası; kırılım mumunun seviyeden ne kadar uzakta kapandığı + 0.5 ATR tampon). Hedef sabit `2.0 ATR` olduğu için dar stopta hedef R olarak uzak, geniş stopta yakındır:

- Stop mesafesi `1 ATR` ya da daha yakın `192` işlem: stop `62.5%`, ilk mumda stop `18.2%`, kâr eden `36.5%`, net `+0.056 R` (hedef ortalama `2.62 R` uzakta, masraf `0.181 R`).
- Daha geniş stoplu `445` işlem: stop `36.0%`, ilk mumda stop `2.9%`, kâr eden `56.9%`, net `+0.140 R` (hedef ortalama `1.27 R` uzakta, masraf `0.088 R`).

| Stop mesafesi | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| ≤ 0.8 ATR | 112 | 63.4% | 21.4% | 31.2% | 35.7% | +0.087 | [-0.260, +0.459] | -0.045 (79) | +0.405 (33) | 2.89 | 0.211 |
| 0.8–1.0 ATR | 80 | 61.3% | 13.8% | 33.8% | 37.5% | +0.013 | [-0.347, +0.385] | -0.191 (47) | +0.302 (33) | 2.24 | 0.140 |
| 1.0–1.3 ATR | 133 | 47.4% | 6.8% | 36.8% | 52.6% | +0.190 | [-0.050, +0.463] | +0.211 (85) | +0.153 (48) | 1.74 | 0.119 |
| 1.3–1.7 ATR | 126 | 41.3% | 2.4% | 46.8% | 54.8% | +0.136 | [-0.155, +0.418] | +0.082 (87) | +0.257 (39) | 1.35 | 0.095 |
| 1.7–2.2 ATR | 90 | 33.3% | 1.1% | 41.1% | 55.6% | +0.032 | [-0.170, +0.222] | +0.022 (56) | +0.048 (34) | 1.04 | 0.074 |
| > 2.2 ATR | 96 | 15.6% | 0.0% | 57.3% | 66.7% | +0.177 | [+0.030, +0.311] | +0.146 (60) | +0.230 (36) | 0.72 | 0.051 |

**Dönem / yön:**

| Dönem / yön | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| dogrulama / long | 99 | 40.4% | 7.1% | 41.4% | 52.5% | +0.144 | [-0.287, +0.387] | 1.50 | 0.097 |
| dogrulama / short | 124 | 40.3% | 4.8% | 47.6% | 58.9% | +0.293 | [-0.009, +0.596] | 1.76 | 0.122 |
| kesif / long | 248 | 39.9% | 8.9% | 47.6% | 51.6% | +0.142 | [-0.066, +0.341] | 1.56 | 0.120 |
| kesif / short | 166 | 54.8% | 7.8% | 26.5% | 42.2% | -0.076 | [-0.320, +0.182] | 1.89 | 0.119 |

**Zaman dilimi ve olay mumunun kapanış saati:**

| Giriş | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1d 18:30 | 203 | 47.8% | 11.3% | 39.9% | 49.8% | +0.100 | [-0.099, +0.299] | +0.028 (143) | +0.270 (60) | 1.79 | 0.076 |
| 4h 13:30 | 262 | 39.3% | 8.0% | 41.6% | 51.9% | +0.083 | [-0.083, +0.255] | +0.010 (161) | +0.200 (101) | 1.49 | 0.124 |
| 4h 17:30 | 153 | 48.4% | 0.7% | 39.2% | 47.7% | +0.126 | [-0.122, +0.383] | +0.107 (97) | +0.158 (56) | 1.86 | 0.156 |
| 4h 18:00 | 18 | 27.8% | 11.1% | 66.7% | 72.2% | +0.721 | [+0.049, +1.315] | +0.633 (12) | +0.898 (6) | 1.66 | 0.123 |

Tabloda yok: küçük kovalarda kalan `1` işlem.

**Aynı gün, aynı yönde, bu işlemin girişine kadar açılmış birincil işlem sayısı** (kendisi dahil; `4h + 1d` birincil işlemler içinde):

| Aynı gün aynı yön | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 (yalnız) | 45 | 51.1% | 13.3% | 28.9% | 44.4% | -0.059 | [-0.459, +0.369] | -0.044 (33) | -0.100 (12) | 1.83 | 0.111 |
| 2–3 | 119 | 48.7% | 7.6% | 38.7% | 44.5% | +0.013 | [-0.268, +0.271] | +0.117 (78) | -0.185 (41) | 1.62 | 0.116 |
| 4–8 | 258 | 43.8% | 7.8% | 44.2% | 51.9% | +0.132 | [-0.057, +0.333] | -0.034 (170) | +0.452 (88) | 1.71 | 0.124 |
| 9+ | 215 | 40.0% | 6.0% | 41.4% | 54.0% | +0.187 | [-0.059, +0.436] | +0.155 (133) | +0.240 (82) | 1.64 | 0.109 |

**Formasyon tipi** (en az 30 işlem):

| Formasyon | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Alçalan Kama | 85 | 47.1% | 9.4% | 40.0% | 47.1% | +0.023 | [-0.258, +0.271] | -0.099 (48) | +0.182 (37) | 1.80 | 0.124 |
| Alçalan Üçgen | 222 | 45.5% | 5.9% | 38.3% | 50.5% | +0.115 | [-0.113, +0.315] | -0.029 (123) | +0.293 (99) | 1.73 | 0.111 |
| Simetrik Üçgen | 54 | 35.2% | 3.7% | 44.4% | 61.1% | +0.224 | [-0.107, +0.531] | +0.250 (37) | +0.167 (17) | 1.38 | 0.100 |
| Yükselen Kama | 105 | 37.1% | 3.8% | 47.6% | 54.3% | +0.319 | [+0.032, +0.602] | +0.281 (79) | +0.435 (26) | 1.76 | 0.132 |
| Yükselen Üçgen | 165 | 47.9% | 12.7% | 40.6% | 47.3% | +0.001 | [-0.264, +0.221] | -0.009 (122) | +0.029 (43) | 1.60 | 0.116 |

Tabloda yok: küçük kovalarda kalan `6` işlem.

### 15. Sonuç haftalara ne kadar yığılmış

İşlemler açıldıkları takvim haftasına göre toplanır.

- Hafta: `90`; net artıda biten `51` (toplam `+162.3 R`), ekside biten `39` (toplam `-89.2 R`).
- En iyi `5` hafta toplam `+67.4 R`; bütün işlemlerin neti `+73.1 R`. Bu `5` hafta çıkarılınca kalan `+5.7 R`.
- En kötü `5` hafta toplam `-30.0 R`; bunlar çıkarılınca kalan `+103.1 R`.
- Bütün işlemleri aynı yönde olan hafta: `35` (bu haftalardaki işlem: `195`).

| Hafta | İşlem | Long / short | Stop | Toplam net R |
|---|---:|---:|---:|---:|
| 2026-H38 | 29 | 0 / 29 | 7 | +18.8 |
| 2026-H07 | 16 | 16 / 0 | 2 | +13.8 |
| 2025-H30 | 14 | 14 / 0 | 2 | +12.7 |
| 2025-H34 | 13 | 12 / 1 | 2 | +11.3 |
| 2026-H03 | 9 | 9 / 0 | 0 | +10.9 |
| 2026-H01 | 7 | 1 / 6 | 5 | -4.3 |
| 2026-H37 | 8 | 6 / 2 | 6 | -4.8 |
| 2025-H33 | 8 | 7 / 1 | 6 | -5.2 |
| 2025-H06 | 8 | 1 / 7 | 6 | -6.0 |
| 2025-H25 | 11 | 0 / 11 | 10 | -9.8 |

Tablo en iyi `5` ve en kötü `5` haftayı gösterir.

## D6_A_Cekirdek_Veya_Arti — 1124 işlem

### 1. Genel tablo

| | İşlem | Pay | Ortalama net R | Toplam net R |
|---|---:|---:|---:|---:|
| Kâr eden | 545 | 48.5% | +1.237 | +674.4 |
| Zarar eden | 579 | 51.5% | -1.046 | -605.7 |
| Tümü | 1124 | 100.0% | +0.061 | +68.7 |

- Brüt toplam `+193.6 R`; masraf `124.9 R` (işlem başına `0.111 R`, brütün `64.5%` kadarı); net `+68.7 R`.
- Ortalama kazancın ortalama kayba oranı `1.18`. Bu oranla sıfır beklenti için işlemlerin `45.8%` kadarının kâr etmesi gerekir; gerçekleşen `48.5%`.
- Brütte artıda olup masraf yüzünden zarara düşen işlem: `10`.
- Medyan stop mesafesi `1.29 ATR`; hedef `2.0 ATR`, yani medyan işlemde `1.55 R`.

| Dönem | İşlem | Kâr eden | Stop | Hedef | Net R |
|---|---:|---:|---:|---:|---:|
| kesif | 738 | 47.0% | 46.1% | 38.1% | +0.021 |
| dogrulama | 386 | 51.3% | 42.5% | 43.0% | +0.138 |

### 2. İşlemler nasıl kapandı

| Çıkış | İşlem | Pay | Kârda | Zararda | Ortalama net R | Toplam net R | Medyan mum |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hedefe ulaştı | 447 | 39.8% | 447 | 0 | +1.392 | +622.1 | 3 |
| Stop oldu | 468 | 41.6% | 0 | 468 | -1.123 | -525.4 | 3 |
| Açılış boşluğuyla stop oldu | 36 | 3.2% | 0 | 36 | -1.460 | -52.6 | 3 |
| Süre doldu (ne stop ne hedef) | 173 | 15.4% | 98 | 75 | +0.142 | +24.5 | 10 |

### 3. Zarar edenler nasıl kaybetti

Her zarar eden işlem tek satırdadır; paylar %100'e toplanır. Sıra önceliktir: boşlukla stop olan işlem, öncesinde ne görmüş olursa olsun `Açılış boşluğu` satırındadır. Kâr eşikleri stop mumundan ÖNCE görülen en iyi andır.

| Kayıp yolu | İşlem | Zarar edenlerin payı | Tüm işlemlerin payı | Ortalama net R | Toplam net R | Toplam zarardaki pay |
|---|---:|---:|---:|---:|---:|---:|
| Stop olmadı; süre doldu, zararda kapandı | 75 | 13.0% | 6.7% | -0.369 | -27.7 | 4.6% |
| Açılış boşluğu stopu atladı | 36 | 6.2% | 3.2% | -1.460 | -52.6 | 8.7% |
| Girişten sonraki ilk mumda stop | 68 | 11.7% | 6.0% | -1.141 | -77.6 | 12.8% |
| 2+ mum yaşadı, +0.25 R'yi hiç görmedi | 123 | 21.2% | 10.9% | -1.119 | -137.7 | 22.7% |
| +0.25–0.5 R gördü, döndü | 98 | 16.9% | 8.7% | -1.107 | -108.5 | 17.9% |
| +0.5–1 R gördü, geri verdi | 114 | 19.7% | 10.1% | -1.120 | -127.7 | 21.1% |
| +1 R ve üstünü gördü, geri verdi | 65 | 11.2% | 5.8% | -1.137 | -73.9 | 12.2% |

### 4. Stop olanlar stoptan önce ne kadar kâr gördü

Stop olan işlem: `504 (44.8%)` (zarar edenlerin `87.0%` kadarı). Saat çözünürlüğünde çözülen stop: `464`.

| Stoptan önce en az | Mum çözünürlüğü (504 stop) | Saat çözünürlüğü (464 stop) | Aynı 464 stopta mum |
|---|---:|---:|---:|
| +0.25 R | 295 (58.5%) | 297 (64.0%) | 274 (59.1%) |
| +0.5 R | 195 (38.7%) | 197 (42.5%) | 181 (39.0%) |
| +1 R | 72 (14.3%) | 73 (15.7%) | 68 (14.7%) |
| +1.5 R | 23 (4.6%) | 21 (4.5%) | 20 (4.3%) |

- Kaçıncı mumda stop: 1. mum `70 (13.9%)`; 2–3. mum `189 (37.5%)`; 4–6. mum `163 (32.3%)`; 7–10. mum `82 (16.3%)`. Medyan `3`. mum.
- Stop mumundan önce girişin kâr tarafında tek bir fiyat görmeyen: `102 (20.2%)` (ilk mumda stop olanlar dahil).
- Hedefe ne kadar yaklaşıp döndüler: hedef yolunun en az %50 kadarı `104 (20.6%)`; hedef yolunun en az %75 kadarı `39 (7.7%)`; hedef yolunun en az %90 kadarı `10 (2.0%)`.
- Stop ile hedef aynı mumda görülen (sıra bilinmediği için stop sayılan) işlem: `4`. Saatlik veride önce hedefin görüldüğü stop: `2`.

### 5. Girişten sonraki ilk mumda stop olanlar

- İşlem: `70` — stopların `13.9%`, bütün işlemlerin `6.2%` kadarı. Açılış boşluğuyla olan: `2`.
- Stop mesafesi `1 ATR` ya da daha yakın olan: `43 (61.4%)`. Dar stoplu işlemlerin `16.1%` kadarı ilk mumda stop oldu; daha geniş stoplularda `3.2%`.
- Saat çözünürlüğünde çözülen: `59`. Mumun ilk saatinde stop `16`, ilk iki saatinde `26`.
- Aynı `59` işlemde stoptan önce `+0.25 R`'yi hiç görmeyen (doğrudan stop): `44 (74.6%)`. Önce kâr görüp aynı mumda dönen: ≥ +0.25 R `15`; ≥ +0.5 R `8`; ≥ +1 R `2`.

| Giriş (zaman dilimi, olay mumunun kapanış saati) | İşlem | İlk mumda stop | Oran |
|---|---:|---:|---:|
| 1d 18:30 | 348 | 31 | 8.9% |
| 4h 13:30 | 458 | 30 | 6.6% |
| 4h 17:30 | 287 | 4 | 1.4% |
| 4h 18:00 | 27 | 4 | 14.8% |

### 6. Açılış boşluğuyla stop olanlar

- İşlem: `36 (7.1%)` (stopların payı). Zaman dilimi: 4h `22`, 1d `14`.
- İşlem gününün ilk mumunda (gece boşluğu) olan: `36`. Girişten sonraki ilk mumda olan: `2`.
- Ortalama brüt sonuç `-1.355 R`, en kötü `-2.912 R`. Stop fiyatı yerine açılıştan dolmanın ek kaybı ortalama `0.355 R`, toplam `12.8 R`.
- Boşluktan önce en az `+0.5 R` görmüş olan: `16`.

### 7. En az +0.5 R görüp stop olanlar

- İşlem: `195 (38.7%)` (stopların payı); bunların `72` kadarı en az `+1 R` gördü. Gördükleri en iyi anın medyanı `+0.90 R`.
- En iyi andan stopa kaç mum geçti: 1 mum `51 (26.2%)`; 2 mum `49 (25.1%)`; 3 mum `37 (19.0%)`; 4+ mum `58 (29.7%)`. Medyan `2` mum.
- Hedefe ne kadar yaklaşmışlardı: hedef yolunun en az %50 kadarı `102 (52.3%)`; hedef yolunun en az %75 kadarı `39 (20.0%)`; hedef yolunun en az %90 kadarı `10 (5.1%)`.

### 8. Stoptan önce uyarı var mıydı

Stop, tez seviyesinin 0.5 ATR ötesindedir. Kapanışa bakan bir kural ancak stoptan önce seviyenin ters tarafında bir kapanış varsa devreye girebilir.

- Hiç kapanış görülmeden (ilk mumda) stop: `70 (13.9%)`.
- Son kapanış hâlâ seviyenin doğru tarafındayken, tek mumda seviyeyi ve tamponu geçip stop: `298 (59.1%)`.
- Son kapanış seviyenin ters tarafındayken stop: `136 (27.0%)`. (Stoptan önce herhangi bir kapanışta seviyenin ters tarafını gören: `164`.)
- Stop mumu başlarken fiyatın stopa uzaklığı: medyan `0.82 ATR`; `333 (66.1%)` stopta 1 ATR ya da daha az, `137 (27.2%)` stopta 0.5 ATR ya da daha az. Yani stopların çoğu için sıradan büyüklükte tek bir ters mum yetti.
- Stop mumundan önceki son kapanışta işlemin açık sonucu: medyan `-0.26 R`; kârda olan `97 (19.2%)`, en az `+0.5 R` kârda olan `22 (4.4%)` (ilk mumda stop olanlar için giriş anı, yani 0 R).

| Stoptan önceki son tez durumu | Stop | Stopların payı | Aynı durumdan hedefe giden |
|---|---:|---:|---:|
| Hiç kapanış görülmedi (ilk mumda çıkış) | 70 | 13.9% | 67 |
| Tez henüz teyit almamıştı | 63 | 12.5% | 55 |
| Tez teyitliydi | 217 | 43.1% | 319 |
| Tez sınanıyordu | 116 | 23.0% | 3 |
| Tez bozulmuştu | 38 | 7.5% | 3 |

İşlem açıkken en az bir kapanışta görülen etiketler — en az bir kapanış görmüş `434` stop ve `478` kazanan:

| Görülen | Stop olanlarda | Kâr edenlerde |
|---|---:|---:|
| Kapanış tez seviyesinin ters tarafında | 164 (37.8%) | 18 (3.8%) |
| Formasyon retest ediliyor | 76 (17.5%) | 10 (2.1%) |
| Formasyon: başarısız kırılım | 9 (2.1%) | 2 (0.4%) |
| Kapanış girişin zarar tarafında | 367 (84.6%) | 222 (46.4%) |
| Ters yönlü kapanış | 394 (90.8%) | 336 (70.3%) |
| Karşı Stabil çizgisinde ret | 109 (25.1%) | 84 (17.6%) |
| Karşı OB/FVG bandında ret | 110 (25.3%) | 208 (43.5%) |
| Ters hacim baskısı | 93 (21.4%) | 84 (17.6%) |
| Ters yönlü yapı olayı (iç/dış; sweep dahil) | 118 (27.2%) | 95 (19.9%) |
| Sistemin kendi karşı yön adayı | 55 (12.7%) | 23 (4.8%) |
| Formasyon kırılımı teyit aldı (lehte) | 314 (72.4%) | 396 (82.8%) |

Bu tablo sonuç-koşulludur: stopa giden yol zaten zarardan ve çoğu kez seviyenin içinden geçer. Bir etiketin stop olanlarda sık görülmesi, o etikette çıkmanın kazandırdığını göstermez; onu `surec_olcum/RAPOR.md` ölçer.

### 9. Stop olduktan sonra fiyat ne yaptı

İşlemin özgün ufku (10 mum) bitene kadar, stop mumundan SONRAKİ mumlara bakılır. Stop mumunun kendi içindeki dönüş sayılmaz.

| Stoptan sonra | Tüm stoplar (504) | İlk mumda stop (70) | +0.5 R görmeden stop (239) | +0.5 R görüp stop (195) |
|---|---:|---:|---:|---:|
| Stoptan sonra özgün hedefe ulaştı | 61 (12.1%) | 10 (14.3%) | 27 (11.3%) | 24 (12.3%) |
| Hedefe ulaşmadı ama ufuk sonunda girişin kâr tarafında | 63 (12.5%) | 9 (12.9%) | 25 (10.5%) | 29 (14.9%) |
| Ufuk sonunda giriş ile stop arasında | 118 (23.4%) | 7 (10.0%) | 67 (28.0%) | 44 (22.6%) |
| Ufuk sonunda stopun da ötesinde | 253 (50.2%) | 44 (62.9%) | 119 (49.8%) | 90 (46.2%) |
| Stop ufkun son mumunda; sonrası yok | 9 (1.8%) | 0 (0.0%) | 1 (0.4%) | 8 (4.1%) |

### 10. Stop olmadan kapananlar (süre doldu)

- İşlem: `173 (15.4%)`; toplam net `+24.5 R`.
- Kârda kapanan `98` (ortalama `+0.533 R`); zararda kapanan `75` (ortalama `-0.369 R`).
- Zararda kapananların `47` kadarı yol boyunca en az `+0.5 R`, `13` kadarı en az `+1 R` görmüştü; `10` kadarı brütte artıdaydı, masraf zarara çevirdi.
- Kârda kapananlar hedef yolunun medyan `%76` kadarını görmüştü; `46` kadarı yol boyunca en az `0.5 R` aleyhte kalmıştı.
- İki yöne de `0.5 R` oynamadan süresi dolan: `9`.

### 11. Zora girip kurtaranlar

İşlem aleyhte şu kadar R gördükten sonra nasıl bitti? (Çıkış mumunun geri kalanı sayılmaz; stop olan her işlem tanım gereği 1 R görür.)

| Aleyhte en az | Gören işlem | Stop oldu | Kârla kapandı | Bunlardan hedefe giden | Stop olmadan zararda kapandı |
|---|---:|---:|---:|---:|---:|
| 0.25 R | 849 | 504 (59.4%) | 271 (31.9%) | 202 | 74 |
| 0.5 R | 697 | 504 (72.3%) | 133 (19.1%) | 87 | 60 |
| 0.75 R | 583 | 504 (86.4%) | 51 (8.7%) | 27 | 28 |

### 12. Kâr edenler nasıl kazandı

- Kâr eden `545` işlemin `447` kadarı hedefe ulaştı (ortalama `+1.392 R`; hedef ortalama `1.50 R` uzaktaydı), `98` kadarı süre dolunca kârda kapandı (ortalama `+0.533 R`).
- Hedefe kaçıncı mumda ulaşıldı: 1. mum `67 (15.0%)`; 2–3. mum `167 (37.4%)`; 4–6. mum `121 (27.1%)`; 7–10. mum `92 (20.6%)`. Medyan `3`. mum.
- Hedefe ulaşanların hedeften önce aleyhte gördüğü: ≥ 0.25 R `202 (45.2%)`; ≥ 0.5 R `87 (19.5%)`; ≥ 0.75 R `27 (6.0%)`.

### 13. Piyasa işlem açıkken ne yaptı

`XU100`, giriş anından çıkış mumunun kapanışına kadar, işlemin YÖNÜNE göre (short işlemde endeksin düşmesi lehtedir). `±%0.5` içi yatay sayılır. Endeks sembollerinin kendi işlemleri ölçülmez. Bu, giriş anında BİLİNMEYEN bir büyüklüktür.

| Çıkış | Ölçülen işlem | Endeks ters | Endeks yatay | Endeks lehte | Endeksin ortalama hareketi |
|---|---:|---:|---:|---:|---:|
| Stop oldu | 495 | 279 (56.4%) | 117 (23.6%) | 99 (20.0%) | -0.94% |
| Hedefe ulaştı | 440 | 76 (17.3%) | 109 (24.8%) | 255 (58.0%) | +1.16% |
| Süre doldu | 172 | 49 (28.5%) | 30 (17.4%) | 93 (54.1%) | +0.45% |

İşlem süresince endeksin hareketine göre:

| İşlem süresince endeks | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| %2'den fazla ters | 158 | 71.5% | 7.6% | 12.7% | 24.1% | -0.603 | [-0.785, -0.417] | -0.569 (107) | -0.675 (51) | 1.62 | 0.088 |
| %0.5–2 ters | 246 | 67.5% | 9.8% | 22.8% | 26.0% | -0.501 | [-0.655, -0.361] | -0.565 (166) | -0.368 (80) | 1.61 | 0.115 |
| yatay (±%0.5) | 256 | 45.7% | 8.6% | 42.6% | 51.2% | +0.048 | [-0.112, +0.214] | +0.028 (167) | +0.087 (89) | 1.65 | 0.121 |
| %0.5–2 lehte | 252 | 26.6% | 3.6% | 50.8% | 62.3% | +0.440 | [+0.289, +0.620] | +0.357 (167) | +0.604 (85) | 1.58 | 0.112 |
| %2'den fazla lehte | 195 | 16.4% | 1.0% | 65.1% | 75.4% | +0.843 | [+0.634, +1.046] | +0.867 (122) | +0.803 (73) | 1.57 | 0.097 |

Tabloda yok: ölçülemeyen `17` işlem.

Girişten ÖNCEKİ 5 mumda endeksin hareketine göre (giriş anında bilinir):

| Girişten önce endeks | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| %2'den fazla ters | 44 | 43.2% | 11.4% | 38.6% | 52.3% | +0.196 | [-0.225, +0.629] | +0.334 (22) | +0.058 (22) | 1.63 | 0.087 |
| %0–2 ters | 193 | 44.0% | 4.7% | 43.0% | 50.8% | +0.074 | [-0.123, +0.282] | +0.069 (131) | +0.084 (62) | 1.56 | 0.113 |
| %0–2 lehte | 420 | 45.0% | 4.5% | 38.1% | 46.2% | +0.052 | [-0.106, +0.210] | -0.035 (267) | +0.205 (153) | 1.63 | 0.123 |
| %2'den fazla lehte | 450 | 44.9% | 8.0% | 40.0% | 49.3% | +0.054 | [-0.103, +0.202] | +0.027 (309) | +0.114 (141) | 1.60 | 0.095 |

Tabloda yok: ölçülemeyen `17` işlem.

### 14. Zarar hangi giriş koşullarında yoğunlaşıyor

`En kötü GA`: net R ortalamasının sembol / gün / hafta / ay kümeli %95 aralıklarının en düşük alt ve en yüksek üst sınırı. Bu tablolar ilişki gösterir; çok sayıda kesit olduğu için tek bir satır kural gerekçesi değildir.

**Stop mesafesi** (giriş ile stop arası; kırılım mumunun seviyeden ne kadar uzakta kapandığı + 0.5 ATR tampon). Hedef sabit `2.0 ATR` olduğu için dar stopta hedef R olarak uzak, geniş stopta yakındır:

- Stop mesafesi `1 ATR` ya da daha yakın `267` işlem: stop `64.0%`, ilk mumda stop `16.1%`, kâr eden `34.1%`, net `-0.048 R` (hedef ortalama `2.47 R` uzakta, masraf `0.170 R`).
- Daha geniş stoplu `857` işlem: stop `38.9%`, ilk mumda stop `3.2%`, kâr eden `53.0%`, net `+0.095 R` (hedef ortalama `1.34 R` uzakta, masraf `0.093 R`).

| Stop mesafesi | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| ≤ 0.8 ATR | 112 | 63.4% | 21.4% | 31.2% | 35.7% | +0.087 | [-0.260, +0.459] | -0.045 (79) | +0.405 (33) | 2.89 | 0.211 |
| 0.8–1.0 ATR | 155 | 64.5% | 12.3% | 28.4% | 32.9% | -0.146 | [-0.367, +0.112] | -0.260 (92) | +0.022 (63) | 2.18 | 0.141 |
| 1.0–1.3 ATR | 300 | 49.0% | 5.7% | 36.3% | 48.0% | +0.119 | [-0.028, +0.265] | +0.158 (192) | +0.051 (108) | 1.76 | 0.121 |
| 1.3–1.7 ATR | 259 | 44.4% | 3.1% | 42.9% | 49.8% | +0.044 | [-0.173, +0.253] | -0.037 (179) | +0.226 (80) | 1.37 | 0.093 |
| 1.7–2.2 ATR | 158 | 30.4% | 1.3% | 43.0% | 55.1% | +0.062 | [-0.115, +0.222] | +0.051 (108) | +0.085 (50) | 1.05 | 0.074 |
| > 2.2 ATR | 140 | 16.4% | 0.0% | 57.1% | 67.1% | +0.175 | [+0.044, +0.300] | +0.157 (88) | +0.205 (52) | 0.73 | 0.053 |

**Dönem / yön:**

| Dönem / yön | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| dogrulama / long | 190 | 44.7% | 4.7% | 38.9% | 47.4% | +0.025 | [-0.249, +0.207] | 1.50 | 0.095 |
| dogrulama / short | 196 | 40.3% | 3.6% | 46.9% | 55.1% | +0.247 | [-0.115, +0.507] | 1.72 | 0.122 |
| kesif / long | 451 | 41.7% | 7.1% | 45.5% | 50.1% | +0.102 | [-0.079, +0.262] | 1.52 | 0.111 |
| kesif / short | 287 | 53.0% | 7.7% | 26.5% | 42.2% | -0.106 | [-0.289, +0.070] | 1.76 | 0.115 |

**Zaman dilimi ve olay mumunun kapanış saati:**

| Giriş | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1d 18:30 | 348 | 47.1% | 8.9% | 38.8% | 48.3% | +0.069 | [-0.093, +0.246] | +0.032 (249) | +0.162 (99) | 1.69 | 0.073 |
| 4h 13:30 | 458 | 39.7% | 6.6% | 41.5% | 51.1% | +0.072 | [-0.066, +0.205] | +0.010 (280) | +0.169 (178) | 1.47 | 0.121 |
| 4h 17:30 | 287 | 51.9% | 1.4% | 35.5% | 42.2% | -0.026 | [-0.213, +0.158] | -0.030 (187) | -0.019 (100) | 1.74 | 0.141 |
| 4h 18:00 | 27 | 25.9% | 14.8% | 70.4% | 74.1% | +0.734 | [+0.233, +1.209] | +0.599 (18) | +1.005 (9) | 1.60 | 0.120 |

Tabloda yok: küçük kovalarda kalan `4` işlem.

**Aynı gün, aynı yönde, bu işlemin girişine kadar açılmış birincil işlem sayısı** (kendisi dahil; `4h + 1d` birincil işlemler içinde):

| Aynı gün aynı yön | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 (yalnız) | 75 | 45.3% | 9.3% | 30.7% | 45.3% | -0.070 | [-0.366, +0.222] | -0.046 (57) | -0.146 (18) | 1.61 | 0.103 |
| 2–3 | 220 | 45.9% | 5.0% | 40.0% | 46.4% | +0.048 | [-0.136, +0.238] | +0.142 (144) | -0.131 (76) | 1.57 | 0.111 |
| 4–8 | 458 | 45.2% | 6.8% | 42.4% | 49.3% | +0.080 | [-0.082, +0.251] | -0.009 (293) | +0.239 (165) | 1.63 | 0.116 |
| 9+ | 371 | 43.7% | 5.7% | 38.3% | 49.3% | +0.072 | [-0.136, +0.280] | +0.001 (244) | +0.208 (127) | 1.61 | 0.107 |

**Formasyon tipi** (en az 30 işlem):

| Formasyon | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Alçalan Kama | 153 | 46.4% | 9.2% | 37.3% | 45.1% | -0.027 | [-0.288, +0.208] | -0.193 (90) | +0.209 (63) | 1.69 | 0.111 |
| Alçalan Üçgen | 395 | 47.1% | 5.3% | 38.0% | 47.8% | +0.043 | [-0.120, +0.206] | -0.067 (233) | +0.201 (162) | 1.63 | 0.108 |
| Simetrik Üçgen | 159 | 39.0% | 3.8% | 42.1% | 53.5% | +0.148 | [-0.080, +0.337] | +0.235 (107) | -0.030 (52) | 1.50 | 0.105 |
| Yükselen Kama | 152 | 41.4% | 3.9% | 46.7% | 51.3% | +0.228 | [-0.045, +0.485] | +0.221 (114) | +0.250 (38) | 1.69 | 0.127 |
| Yükselen Üçgen | 258 | 46.5% | 8.9% | 38.8% | 46.9% | -0.006 | [-0.166, +0.169] | -0.009 (188) | +0.000 (70) | 1.56 | 0.110 |

Tabloda yok: küçük kovalarda kalan `7` işlem.

### 15. Sonuç haftalara ne kadar yığılmış

İşlemler açıldıkları takvim haftasına göre toplanır.

- Hafta: `92`; net artıda biten `45` (toplam `+216.9 R`), ekside biten `47` (toplam `-148.2 R`).
- En iyi `5` hafta toplam `+90.5 R`; bütün işlemlerin neti `+68.7 R`. Bu `5` hafta çıkarılınca kalan `-21.8 R`.
- En kötü `5` hafta toplam `-43.6 R`; bunlar çıkarılınca kalan `+112.3 R`.
- Bütün işlemleri aynı yönde olan hafta: `17` (bu haftalardaki işlem: `164`).

| Hafta | İşlem | Long / short | Stop | Toplam net R |
|---|---:|---:|---:|---:|
| 2026-H38 | 40 | 0 / 40 | 7 | +33.7 |
| 2026-H07 | 29 | 29 / 0 | 7 | +16.7 |
| 2026-H03 | 19 | 16 / 3 | 3 | +14.4 |
| 2025-H34 | 22 | 20 / 2 | 4 | +13.5 |
| 2025-H21 | 11 | 1 / 10 | 2 | +12.1 |
| 2025-H24 | 9 | 4 / 5 | 6 | -6.5 |
| 2025-H33 | 12 | 10 / 2 | 9 | -7.9 |
| 2026-H37 | 13 | 11 / 2 | 10 | -8.4 |
| 2025-H25 | 18 | 1 / 17 | 13 | -9.2 |
| 2026-H01 | 16 | 5 / 11 | 12 | -11.6 |

Tablo en iyi `5` ve en kötü `5` haftayı gösterir.

## D1_Birincil — 4233 işlem

### 1. Genel tablo

| | İşlem | Pay | Ortalama net R | Toplam net R |
|---|---:|---:|---:|---:|
| Kâr eden | 1818 | 42.9% | +1.479 | +2688.2 |
| Zarar eden | 2415 | 57.1% | -1.096 | -2645.9 |
| Tümü | 4233 | 100.0% | +0.010 | +42.3 |

- Brüt toplam `+597.2 R`; masraf `555.0 R` (işlem başına `0.131 R`, brütün `92.9%` kadarı); net `+42.3 R`.
- Ortalama kazancın ortalama kayba oranı `1.35`. Bu oranla sıfır beklenti için işlemlerin `42.6%` kadarının kâr etmesi gerekir; gerçekleşen `42.9%`.
- Brütte artıda olup masraf yüzünden zarara düşen işlem: `33`.
- Medyan stop mesafesi `1.06 ATR`; hedef `2.0 ATR`, yani medyan işlemde `1.89 R`.

| Dönem | İşlem | Kâr eden | Stop | Hedef | Net R |
|---|---:|---:|---:|---:|---:|
| kesif | 2723 | 42.2% | 52.0% | 33.1% | -0.010 |
| dogrulama | 1510 | 44.2% | 49.1% | 35.4% | +0.045 |

### 2. İşlemler nasıl kapandı

| Çıkış | İşlem | Pay | Kârda | Zararda | Ortalama net R | Toplam net R | Medyan mum |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hedefe ulaştı | 1435 | 33.9% | 1435 | 0 | +1.677 | +2407.1 | 4 |
| Stop oldu | 1998 | 47.2% | 0 | 1998 | -1.143 | -2283.8 | 3 |
| Açılış boşluğuyla stop oldu | 160 | 3.8% | 0 | 160 | -1.623 | -259.7 | 3 |
| Süre doldu (ne stop ne hedef) | 636 | 15.0% | 383 | 253 | +0.284 | +180.8 | 10 |
| Tez iptaliyle kapandı | 4 | 0.1% | 0 | 4 | -0.537 | -2.1 | 2 |

### 3. Zarar edenler nasıl kaybetti

Her zarar eden işlem tek satırdadır; paylar %100'e toplanır. Sıra önceliktir: boşlukla stop olan işlem, öncesinde ne görmüş olursa olsun `Açılış boşluğu` satırındadır. Kâr eşikleri stop mumundan ÖNCE görülen en iyi andır.

| Kayıp yolu | İşlem | Zarar edenlerin payı | Tüm işlemlerin payı | Ortalama net R | Toplam net R | Toplam zarardaki pay |
|---|---:|---:|---:|---:|---:|---:|
| Stop olmadı; süre doldu, zararda kapandı | 253 | 10.5% | 6.0% | -0.396 | -100.2 | 3.8% |
| Stop olmadı; tez iptaliyle zararda kapandı | 4 | 0.2% | 0.1% | -0.537 | -2.1 | 0.1% |
| Açılış boşluğu stopu atladı | 160 | 6.6% | 3.8% | -1.623 | -259.7 | 9.8% |
| Girişten sonraki ilk mumda stop | 411 | 17.0% | 9.7% | -1.158 | -475.9 | 18.0% |
| 2+ mum yaşadı, +0.25 R'yi hiç görmedi | 508 | 21.0% | 12.0% | -1.131 | -574.4 | 21.7% |
| +0.25–0.5 R gördü, döndü | 327 | 13.5% | 7.7% | -1.126 | -368.1 | 13.9% |
| +0.5–1 R gördü, geri verdi | 400 | 16.6% | 9.4% | -1.138 | -455.2 | 17.2% |
| +1 R ve üstünü gördü, geri verdi | 352 | 14.6% | 8.3% | -1.165 | -410.2 | 15.5% |

### 4. Stop olanlar stoptan önce ne kadar kâr gördü

Stop olan işlem: `2158 (51.0%)` (zarar edenlerin `89.4%` kadarı). Saat çözünürlüğünde çözülen stop: `2015`.

| Stoptan önce en az | Mum çözünürlüğü (2158 stop) | Saat çözünürlüğü (2015 stop) | Aynı 2015 stopta mum |
|---|---:|---:|---:|
| +0.25 R | 1168 (54.1%) | 1226 (60.8%) | 1099 (54.5%) |
| +0.5 R | 816 (37.8%) | 853 (42.3%) | 773 (38.4%) |
| +1 R | 382 (17.7%) | 385 (19.1%) | 364 (18.1%) |
| +1.5 R | 174 (8.1%) | 165 (8.2%) | 163 (8.1%) |

- Kaçıncı mumda stop: 1. mum `443 (20.5%)`; 2–3. mum `804 (37.3%)`; 4–6. mum `613 (28.4%)`; 7–10. mum `298 (13.8%)`. Medyan `3`. mum.
- Stop mumundan önce girişin kâr tarafında tek bir fiyat görmeyen: `566 (26.2%)` (ilk mumda stop olanlar dahil).
- Hedefe ne kadar yaklaşıp döndüler: hedef yolunun en az %50 kadarı `393 (18.2%)`; hedef yolunun en az %75 kadarı `142 (6.6%)`; hedef yolunun en az %90 kadarı `52 (2.4%)`.
- Stop ile hedef aynı mumda görülen (sıra bilinmediği için stop sayılan) işlem: `9`. Saatlik veride önce hedefin görüldüğü stop: `4`.

### 5. Girişten sonraki ilk mumda stop olanlar

- İşlem: `443` — stopların `20.5%`, bütün işlemlerin `10.5%` kadarı. Açılış boşluğuyla olan: `32`.
- Stop mesafesi `1 ATR` ya da daha yakın olan: `329 (74.3%)`. Dar stoplu işlemlerin `17.4%` kadarı ilk mumda stop oldu; daha geniş stoplularda `4.9%`.
- Saat çözünürlüğünde çözülen: `407`. Mumun ilk saatinde stop `134`, ilk iki saatinde `212`.
- Aynı `407` işlemde stoptan önce `+0.25 R`'yi hiç görmeyen (doğrudan stop): `316 (77.6%)`. Önce kâr görüp aynı mumda dönen: ≥ +0.25 R `91`; ≥ +0.5 R `45`; ≥ +1 R `8`.

| Giriş (zaman dilimi, olay mumunun kapanış saati) | İşlem | İlk mumda stop | Oran |
|---|---:|---:|---:|
| 1d 18:30 | 1406 | 183 | 13.0% |
| 4h 13:30 | 1496 | 138 | 9.2% |
| 4h 17:30 | 952 | 13 | 1.4% |
| 4h 18:00 | 369 | 103 | 27.9% |

### 6. Açılış boşluğuyla stop olanlar

- İşlem: `160 (7.4%)` (stopların payı). Zaman dilimi: 4h `108`, 1d `52`.
- İşlem gününün ilk mumunda (gece boşluğu) olan: `158`. Girişten sonraki ilk mumda olan: `32`.
- Ortalama brüt sonuç `-1.484 R`, en kötü `-4.592 R`. Stop fiyatı yerine açılıştan dolmanın ek kaybı ortalama `0.484 R`, toplam `77.4 R`.
- Boşluktan önce en az `+0.5 R` görmüş olan: `64`.

### 7. En az +0.5 R görüp stop olanlar

- İşlem: `816 (37.8%)` (stopların payı); bunların `382` kadarı en az `+1 R` gördü. Gördükleri en iyi anın medyanı `+0.95 R`.
- En iyi andan stopa kaç mum geçti: 1 mum `230 (28.2%)`; 2 mum `190 (23.3%)`; 3 mum `180 (22.1%)`; 4+ mum `216 (26.5%)`. Medyan `2` mum.
- Hedefe ne kadar yaklaşmışlardı: hedef yolunun en az %50 kadarı `390 (47.8%)`; hedef yolunun en az %75 kadarı `142 (17.4%)`; hedef yolunun en az %90 kadarı `52 (6.4%)`.

### 8. Stoptan önce uyarı var mıydı

Stop, tez seviyesinin 0.5 ATR ötesindedir. Kapanışa bakan bir kural ancak stoptan önce seviyenin ters tarafında bir kapanış varsa devreye girebilir.

- Hiç kapanış görülmeden (ilk mumda) stop: `443 (20.5%)`.
- Son kapanış hâlâ seviyenin doğru tarafındayken, tek mumda seviyeyi ve tamponu geçip stop: `1108 (51.3%)`.
- Son kapanış seviyenin ters tarafındayken stop: `607 (28.1%)`. (Stoptan önce herhangi bir kapanışta seviyenin ters tarafını gören: `708`.)
- Stop mumu başlarken fiyatın stopa uzaklığı: medyan `0.72 ATR`; `1616 (74.9%)` stopta 1 ATR ya da daha az, `616 (28.5%)` stopta 0.5 ATR ya da daha az. Yani stopların çoğu için sıradan büyüklükte tek bir ters mum yetti.
- Stop mumundan önceki son kapanışta işlemin açık sonucu: medyan `-0.19 R`; kârda olan `405 (18.8%)`, en az `+0.5 R` kârda olan `107 (5.0%)` (ilk mumda stop olanlar için giriş anı, yani 0 R).

| Stoptan önceki son tez durumu | Stop | Stopların payı | Aynı durumdan hedefe giden |
|---|---:|---:|---:|
| Hiç kapanış görülmedi (ilk mumda çıkış) | 443 | 20.5% | 171 |
| Tez henüz teyit almamıştı | 257 | 11.9% | 154 |
| Tez teyitliydi | 809 | 37.5% | 1094 |
| Tez sınanıyordu | 476 | 22.1% | 9 |
| Tez bozulmuştu | 173 | 8.0% | 7 |

İşlem açıkken en az bir kapanışta görülen etiketler — en az bir kapanış görmüş `1715` stop ve `1647` kazanan:

| Görülen | Stop olanlarda | Kâr edenlerde |
|---|---:|---:|
| Kapanış tez seviyesinin ters tarafında | 708 (41.3%) | 110 (6.7%) |
| Formasyon retest ediliyor | 172 (10.0%) | 31 (1.9%) |
| Formasyon: başarısız kırılım | 14 (0.8%) | 2 (0.1%) |
| Kapanış girişin zarar tarafında | 1398 (81.5%) | 715 (43.4%) |
| Ters yönlü kapanış | 1538 (89.7%) | 1177 (71.5%) |
| Karşı Stabil çizgisinde ret | 338 (19.7%) | 336 (20.4%) |
| Karşı OB/FVG bandında ret | 632 (36.9%) | 873 (53.0%) |
| Ters hacim baskısı | 428 (25.0%) | 302 (18.3%) |
| Ters yönlü yapı olayı (iç/dış; sweep dahil) | 377 (22.0%) | 364 (22.1%) |
| Sistemin kendi karşı yön adayı | 193 (11.3%) | 110 (6.7%) |
| Formasyon kırılımı teyit aldı (lehte) | 1223 (71.3%) | 1429 (86.8%) |

Bu tablo sonuç-koşulludur: stopa giden yol zaten zarardan ve çoğu kez seviyenin içinden geçer. Bir etiketin stop olanlarda sık görülmesi, o etikette çıkmanın kazandırdığını göstermez; onu `surec_olcum/RAPOR.md` ölçer.

### 9. Stop olduktan sonra fiyat ne yaptı

İşlemin özgün ufku (10 mum) bitene kadar, stop mumundan SONRAKİ mumlara bakılır. Stop mumunun kendi içindeki dönüş sayılmaz.

| Stoptan sonra | Tüm stoplar (2158) | İlk mumda stop (443) | +0.5 R görmeden stop (899) | +0.5 R görüp stop (816) |
|---|---:|---:|---:|---:|
| Stoptan sonra özgün hedefe ulaştı | 290 (13.4%) | 87 (19.6%) | 105 (11.7%) | 98 (12.0%) |
| Hedefe ulaşmadı ama ufuk sonunda girişin kâr tarafında | 284 (13.2%) | 77 (17.4%) | 97 (10.8%) | 110 (13.5%) |
| Ufuk sonunda giriş ile stop arasında | 467 (21.6%) | 51 (11.5%) | 238 (26.5%) | 178 (21.8%) |
| Ufuk sonunda stopun da ötesinde | 1058 (49.0%) | 228 (51.5%) | 452 (50.3%) | 378 (46.3%) |
| Stop ufkun son mumunda; sonrası yok | 59 (2.7%) | 0 (0.0%) | 7 (0.8%) | 52 (6.4%) |

### 10. Stop olmadan kapananlar (süre doldu)

- İşlem: `636 (15.0%)`; toplam net `+180.8 R`.
- Kârda kapanan `383` (ortalama `+0.734 R`); zararda kapanan `253` (ortalama `-0.396 R`).
- Zararda kapananların `162` kadarı yol boyunca en az `+0.5 R`, `71` kadarı en az `+1 R` görmüştü; `33` kadarı brütte artıdaydı, masraf zarara çevirdi.
- Kârda kapananlar hedef yolunun medyan `%77` kadarını görmüştü; `196` kadarı yol boyunca en az `0.5 R` aleyhte kalmıştı.
- İki yöne de `0.5 R` oynamadan süresi dolan: `22`.

### 11. Zora girip kurtaranlar

İşlem aleyhte şu kadar R gördükten sonra nasıl bitti? (Çıkış mumunun geri kalanı sayılmaz; stop olan her işlem tanım gereği 1 R görür.)

| Aleyhte en az | Gören işlem | Stop oldu | Kârla kapandı | Bunlardan hedefe giden | Stop olmadan zararda kapandı |
|---|---:|---:|---:|---:|---:|
| 0.25 R | 3401 | 2158 (63.5%) | 994 (29.2%) | 689 | 249 |
| 0.5 R | 2896 | 2158 (74.5%) | 535 (18.5%) | 339 | 203 |
| 0.75 R | 2501 | 2158 (86.3%) | 226 (9.0%) | 123 | 117 |

### 12. Kâr edenler nasıl kazandı

- Kâr eden `1818` işlemin `1435` kadarı hedefe ulaştı (ortalama `+1.677 R`; hedef ortalama `1.80 R` uzaktaydı), `383` kadarı süre dolunca kârda kapandı (ortalama `+0.734 R`).
- Hedefe kaçıncı mumda ulaşıldı: 1. mum `171 (11.9%)`; 2–3. mum `519 (36.2%)`; 4–6. mum `425 (29.6%)`; 7–10. mum `320 (22.3%)`. Medyan `4`. mum.
- Hedefe ulaşanların hedeften önce aleyhte gördüğü: ≥ 0.25 R `689 (48.0%)`; ≥ 0.5 R `339 (23.6%)`; ≥ 0.75 R `123 (8.6%)`.

### 13. Piyasa işlem açıkken ne yaptı

`XU100`, giriş anından çıkış mumunun kapanışına kadar, işlemin YÖNÜNE göre (short işlemde endeksin düşmesi lehtedir). `±%0.5` içi yatay sayılır. Endeks sembollerinin kendi işlemleri ölçülmez. Bu, giriş anında BİLİNMEYEN bir büyüklüktür.

| Çıkış | Ölçülen işlem | Endeks ters | Endeks yatay | Endeks lehte | Endeksin ortalama hareketi |
|---|---:|---:|---:|---:|---:|
| Stop oldu | 2128 | 1161 (54.6%) | 553 (26.0%) | 414 (19.5%) | -0.87% |
| Hedefe ulaştı | 1411 | 210 (14.9%) | 283 (20.1%) | 918 (65.1%) | +1.49% |
| Süre doldu | 632 | 215 (34.0%) | 101 (16.0%) | 316 (50.0%) | +0.40% |

İşlem süresince endeksin hareketine göre:

| İşlem süresince endeks | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| %2'den fazla ters | 621 | 72.3% | 9.5% | 8.7% | 20.0% | -0.666 | [-0.811, -0.520] | -0.634 (405) | -0.727 (216) | 1.91 | 0.103 |
| %0.5–2 ters | 967 | 73.6% | 15.0% | 16.1% | 21.3% | -0.593 | [-0.670, -0.510] | -0.598 (611) | -0.583 (356) | 1.97 | 0.136 |
| yatay (±%0.5) | 938 | 59.0% | 17.4% | 30.2% | 37.4% | -0.201 | [-0.303, -0.105] | -0.273 (614) | -0.064 (324) | 2.00 | 0.150 |
| %0.5–2 lehte | 874 | 35.0% | 7.2% | 46.9% | 57.3% | +0.423 | [+0.321, +0.537] | +0.396 (566) | +0.472 (308) | 1.92 | 0.132 |
| %2'den fazla lehte | 775 | 13.9% | 0.9% | 65.5% | 78.7% | +1.092 | [+0.934, +1.228] | +1.089 (491) | +1.096 (284) | 1.90 | 0.112 |

Tabloda yok: ölçülemeyen `58` işlem.

Girişten ÖNCEKİ 5 mumda endeksin hareketine göre (giriş anında bilinir):

| Girişten önce endeks | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| %2'den fazla ters | 305 | 54.1% | 15.1% | 32.1% | 43.6% | +0.092 | [-0.148, +0.344] | +0.238 (194) | -0.163 (111) | 2.16 | 0.116 |
| %0–2 ters | 927 | 53.4% | 12.3% | 31.6% | 40.9% | -0.073 | [-0.201, +0.062] | -0.066 (613) | -0.087 (314) | 1.99 | 0.141 |
| %0–2 lehte | 1553 | 52.0% | 9.5% | 34.0% | 41.8% | -0.006 | [-0.124, +0.108] | -0.048 (974) | +0.063 (579) | 1.94 | 0.145 |
| %2'den fazla lehte | 1390 | 47.5% | 9.3% | 35.4% | 45.4% | +0.065 | [-0.088, +0.204] | +0.011 (906) | +0.165 (484) | 1.87 | 0.106 |

Tabloda yok: ölçülemeyen `58` işlem.

### 14. Zarar hangi giriş koşullarında yoğunlaşıyor

`En kötü GA`: net R ortalamasının sembol / gün / hafta / ay kümeli %95 aralıklarının en düşük alt ve en yüksek üst sınırı. Bu tablolar ilişki gösterir; çok sayıda kesit olduğu için tek bir satır kural gerekçesi değildir.

**Stop mesafesi** (giriş ile stop arası; kırılım mumunun seviyeden ne kadar uzakta kapandığı + 0.5 ATR tampon). Hedef sabit `2.0 ATR` olduğu için dar stopta hedef R olarak uzak, geniş stopta yakındır:

- Stop mesafesi `1 ATR` ya da daha yakın `1888` işlem: stop `62.1%`, ilk mumda stop `17.4%`, kâr eden `35.6%`, net `-0.009 R` (hedef ortalama `2.61 R` uzakta, masraf `0.174 R`).
- Daha geniş stoplu `2345` işlem: stop `42.0%`, ilk mumda stop `4.9%`, kâr eden `48.8%`, net `+0.025 R` (hedef ortalama `1.41 R` uzakta, masraf `0.097 R`).

| Stop mesafesi | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| ≤ 0.8 ATR | 1041 | 65.1% | 21.7% | 25.1% | 32.9% | -0.038 | [-0.170, +0.119] | -0.103 (710) | +0.102 (331) | 2.91 | 0.196 |
| 0.8–1.0 ATR | 847 | 58.3% | 12.2% | 31.5% | 39.1% | +0.026 | [-0.101, +0.145] | +0.049 (548) | -0.015 (299) | 2.24 | 0.146 |
| 1.0–1.3 ATR | 983 | 51.1% | 7.8% | 34.9% | 44.7% | +0.036 | [-0.072, +0.153] | +0.029 (606) | +0.047 (377) | 1.77 | 0.120 |
| 1.3–1.7 ATR | 721 | 44.1% | 4.2% | 35.6% | 47.2% | -0.024 | [-0.130, +0.078] | -0.062 (470) | +0.049 (251) | 1.37 | 0.094 |
| 1.7–2.2 ATR | 363 | 33.1% | 1.7% | 42.7% | 52.1% | +0.015 | [-0.117, +0.163] | +0.056 (231) | -0.055 (132) | 1.05 | 0.073 |
| > 2.2 ATR | 278 | 16.5% | 0.4% | 54.7% | 63.7% | +0.128 | [+0.042, +0.213] | +0.120 (158) | +0.138 (120) | 0.72 | 0.052 |

**Dönem / yön:**

| Dönem / yön | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| dogrulama / long | 807 | 53.5% | 9.4% | 31.0% | 37.5% | -0.147 | [-0.358, -0.006] | 1.78 | 0.124 |
| dogrulama / short | 703 | 44.1% | 10.2% | 40.5% | 51.9% | +0.266 | [-0.048, +0.591] | 2.05 | 0.132 |
| kesif / long | 1371 | 46.2% | 10.7% | 41.5% | 47.0% | +0.103 | [-0.045, +0.235] | 1.84 | 0.130 |
| kesif / short | 1352 | 57.9% | 10.9% | 24.5% | 37.4% | -0.124 | [-0.275, +0.015] | 2.11 | 0.136 |

**Zaman dilimi ve olay mumunun kapanış saati:**

| Giriş | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1d 18:30 | 1406 | 52.6% | 13.0% | 32.4% | 42.5% | +0.051 | [-0.061, +0.166] | +0.052 (975) | +0.047 (431) | 2.04 | 0.086 |
| 4h 13:30 | 1496 | 44.6% | 9.2% | 38.2% | 47.7% | +0.070 | [-0.021, +0.167] | +0.026 (913) | +0.140 (583) | 1.76 | 0.142 |
| 4h 17:30 | 952 | 55.4% | 1.4% | 29.8% | 38.4% | -0.102 | [-0.196, -0.001] | -0.120 (602) | -0.073 (350) | 1.98 | 0.158 |
| 4h 18:00 | 369 | 58.8% | 27.9% | 33.3% | 37.9% | -0.077 | [-0.256, +0.116] | -0.092 (223) | -0.052 (146) | 2.29 | 0.189 |

Tabloda yok: küçük kovalarda kalan `10` işlem.

**Aynı gün, aynı yönde, bu işlemin girişine kadar açılmış birincil işlem sayısı** (kendisi dahil; `4h + 1d` birincil işlemler içinde):

| Aynı gün aynı yön | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 (yalnız) | 337 | 49.0% | 10.7% | 34.7% | 45.4% | +0.123 | [-0.043, +0.309] | +0.159 (240) | +0.035 (97) | 2.04 | 0.135 |
| 2–3 | 858 | 53.1% | 10.3% | 31.0% | 39.9% | -0.074 | [-0.182, +0.029] | -0.016 (563) | -0.186 (295) | 1.95 | 0.136 |
| 4–8 | 1662 | 51.7% | 11.7% | 34.1% | 43.0% | -0.005 | [-0.098, +0.092] | -0.079 (1030) | +0.117 (632) | 1.95 | 0.136 |
| 9+ | 1376 | 49.3% | 9.1% | 35.3% | 44.3% | +0.053 | [-0.115, +0.215] | +0.030 (890) | +0.095 (486) | 1.92 | 0.121 |

**Formasyon tipi** (en az 30 işlem):

| Formasyon | N | Stop | İlk mumda stop | Hedef | Kâr eden | Net R | En kötü GA | Keşif (n) | Doğrulama (n) | Ort. hedef R | Ort. masraf R |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Alçalan Kama | 740 | 50.7% | 11.1% | 32.3% | 39.6% | -0.086 | [-0.217, +0.056] | -0.040 (438) | -0.154 (302) | 1.83 | 0.125 |
| Alçalan Üçgen | 1251 | 50.9% | 9.9% | 34.9% | 44.0% | +0.017 | [-0.084, +0.109] | -0.034 (733) | +0.090 (518) | 1.91 | 0.129 |
| Simetrik Üçgen | 687 | 50.1% | 10.2% | 33.6% | 44.0% | +0.043 | [-0.069, +0.162] | +0.056 (457) | +0.015 (230) | 2.02 | 0.134 |
| Yükselen Kama | 694 | 53.5% | 9.7% | 33.1% | 41.1% | +0.011 | [-0.118, +0.147] | -0.045 (516) | +0.173 (178) | 2.00 | 0.133 |
| Yükselen Üçgen | 843 | 50.3% | 11.9% | 34.4% | 44.8% | +0.055 | [-0.079, +0.192] | +0.029 (567) | +0.109 (276) | 2.01 | 0.134 |

Tabloda yok: küçük kovalarda kalan `18` işlem.

### 15. Sonuç haftalara ne kadar yığılmış

İşlemler açıldıkları takvim haftasına göre toplanır.

- Hafta: `99`; net artıda biten `45` (toplam `+555.6 R`), ekside biten `54` (toplam `-513.3 R`).
- En iyi `5` hafta toplam `+204.9 R`; bütün işlemlerin neti `+42.3 R`. Bu `5` hafta çıkarılınca kalan `-162.6 R`.
- En kötü `5` hafta toplam `-125.8 R`; bunlar çıkarılınca kalan `+168.0 R`.
- Bütün işlemleri aynı yönde olan hafta: `5` (bu haftalardaki işlem: `15`).

| Hafta | İşlem | Long / short | Stop | Toplam net R |
|---|---:|---:|---:|---:|
| 2026-H38 | 87 | 5 / 82 | 17 | +88.9 |
| 2026-H31 | 69 | 11 / 58 | 23 | +39.4 |
| 2025-H27 | 55 | 46 / 9 | 18 | +27.7 |
| 2026-H20 | 53 | 20 / 33 | 19 | +25.8 |
| 2025-H21 | 24 | 4 / 20 | 6 | +23.1 |
| 2026-H12 | 40 | 27 / 13 | 30 | -22.4 |
| 2026-H37 | 62 | 51 / 11 | 44 | -22.9 |
| 2026-H41 | 41 | 33 / 8 | 25 | -26.5 |
| 2026-H34 | 53 | 36 / 17 | 35 | -26.9 |
| 2026-H13 | 73 | 27 / 46 | 49 | -27.1 |

Tablo en iyi `5` ve en kötü `5` haftayı gösterir.
