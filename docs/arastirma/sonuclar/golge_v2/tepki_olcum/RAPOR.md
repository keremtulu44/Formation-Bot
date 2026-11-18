# Gölge v2 — Tepki Ölçümü: Kâr Gördükten Sonra Aleyhte Gözleme Tepki Verilseydi

> Üretici: `python -m research.golge_v2_tepki_olcum`. Bu dosya elle düzenlenmez.

- Evren: `176` sembol, `4h + 1d`, Mod 0, `2 ATR` hedef, `10` mum ufuk, `30 bps` masraf. İşlem: `4233`; motor kod özeti `df187d7e9732`.
- Baz eşitliği: ana rapordaki `net15_20_r` ile `4233` ortak işlemde en büyük mutlak fark `0.0` R, farklı işlem `0`; ana CSV'de bulunmayan işlem `0`. `surec_olcum` çıktısıyla `4233` ortak işlemde sonucu (net, çıkış nedeni, çıkış mumu) farklı olan `0`; yalnız birinde bulunan `0`.

**Soru.** `kar_gorup_donen` raporu, kâr görüp stop olan işlemlerde tepe ile stop arasında bilinen engele takılma, tez seviyesinin içine kapanış, formasyon bozulması, Market Structure ters süpürmesi ve ters hacim görüldüğünü sayar. Baz sistem bu gözlemleri kaydeder ama işlem açıkken stop, hedef, süre ve ilk mumlardaki ters yapı kırılımında tez iptali dışında bir şey yapmaz. Burada ölçülen: tepki verseydi ne olurdu?

**Yöntem.** Eşleşmiş replay: aynı işlemler, aynı giriş, aynı ilk stop, aynı hedef, aynı masraf, aynı motor. İşlem çıkışa kadar en az 0.5 ATR (ya da 1 ATR) gördükten sonra — aynı kapanış dahil — tetik ilk kez yandığında tek bir tepki verilir. `Sonraki açılışta çık`: karar mumun kapanışında, çıkış bir sonraki mumun açılışında. `Stopu girişe çek`: stop bir sonraki mumdan itibaren giriş fiyatındadır; fiyat o an girişin zarar tarafındaysa işlem sonraki açılışta kapanır. Tetikler `kar_gorup_donen` ile aynı tanımları kullanır; engel seviyeleri her zaman önceki kapanışta bilinenlerdir.

**Okuma kılavuzu.** `Tetiklenen`: tepkinin verildiği işlem. `Sonucu değişen`: baza göre net R'si, çıkış nedeni ya da çıkış mumu değişen işlem (stopu girişe çekmek, fiyat girişe dönmezse hiçbir şeyi değiştirmez). `Stop olacaklarda / Hedefe gideceklerde / Süre sonu`: sonucu değişen işlemlerin BAZ sonucuna göre sayısı ve tepkinin o gruptaki toplam etkisi (R); artı = tepki kazandırdı. `Fark R/işlem`: kümedeki bütün işlemler üzerinden işlem başına net R farkı (sonucu değişmeyenlerde 0). `En kötü GA`: sembol / gün / hafta / ay kümeli %95 aralıkların en düşük alt ve en yüksek üst sınırı.

**Kabul kuralı** (`surec_olcum` ile aynı merdiven). `GECTI`: fark keşif ve doğrulamada pozitif, iki dönemde de sonucu değişen işlem ≥ 30 ve iki dönemde de en kötü alt sınır sıfırın üstünde. `UMUT_VAR`: aynı, ama alt sınır yalnız havuzda sıfırın üstünde. `ZAYIF_ARTI`: iki dönemde de pozitif ama aralık sıfırı içeriyor ya da bir dönemde sonucu değişen işlem < 30. `GECMEDI`: en az bir dönemde fark pozitif değil. `ZARARLI`: havuzda en kötü üst sınır bile negatif. `SAYILMAZ_N<30`: sonucu değişen işlem 30'dan az.

**Bu ölçüm ön-kayıtlı değildir.** Tetik listesi `kar_gorup_donen` tablosu görüldükten sonra, o tablonun satırlarından yazıldı. `2` eşik × `12` tetik × `2` tepki = `48` varyant, `3` küme; çoklu karşılaştırma düzeltmesi yok. Geçen bir varyant bile kural değil, ileriye dönük gölge defterde izlenecek adaydır.

## Kısa özet

- **Baz sistem tepki vermiyor; yalnız kaydediyor.** D7: `637` işlem; baz sonuç stop `280`, hedef `262`, süre sonu / diğer `95`. Çıkıştan önce 0.5 ATR gören `411`, 1 ATR gören `293` işlem.
- **Kabul merdivenini geçen varyant** (`48` varyant; `GECTI` ya da `UMUT_VAR`): D7 `0` (GECMEDI 36, SAYILMAZ_N<30 7, ZAYIF_ARTI 5); D6 `0` (GECMEDI 42, ZAYIF_ARTI 6); D1 `2` (GECMEDI 38, UMUT_VAR 2, ZARARLI 4, ZAYIF_ARTI 4).
- **D7, 0.5 ATR sonrası, tepki "sonraki açılışta çık":** koşulsuz `-0.0637 R/işlem` (GECMEDI). Tetikli en iyi: `SEVIYE_ICI` `+0.0069` (ZAYIF_ARTI); en kötü: `HERHANGI` `-0.0331` (GECMEDI). Fark iki dönemde de artı olan tetik: `SEVIYE_ICI`.
- **D7, 0.5 ATR sonrası, tepki "stopu girişe çek":** koşulsuz `-0.0600 R/işlem` (GECMEDI). Tetikli en iyi: `SEVIYE_ICI` `+0.0069` (ZAYIF_ARTI); en kötü: `HERHANGI` `-0.0226` (GECMEDI). Fark iki dönemde de artı olan tetik: `SEVIYE_ICI`.
- **D7, 1 ATR sonrası, tepki "sonraki açılışta çık":** koşulsuz `-0.0304 R/işlem` (GECMEDI). Tetikli en iyi: `SEVIYE_ICI` `+0.0067` (SAYILMAZ_N<30); en kötü: `HERHANGI` `-0.0192` (GECMEDI). Fark iki dönemde de artı olan tetik: `SEVIYE_ICI`.
- **D7, 1 ATR sonrası, tepki "stopu girişe çek":** koşulsuz `-0.0203 R/işlem` (GECMEDI). Tetikli en iyi: `BLOK` `+0.0102` (ZAYIF_ARTI); en kötü: `VP_TERS` `-0.0098` (GECMEDI). Fark iki dönemde de artı olan tetik: `BLOK`, `SEVIYE_ICI`, `ENDEKS`, `IKI_FARKLI`.
- **Neden tutmuyor (D7, 0.5 ATR sonrası, sonraki açılışta çık):** `ENGEL` tetiği stop olacak `65` işlemde `+76.6 R` kazandırıyor, hedefe gidecek `86` işlemde `-87.5 R` kaybettiriyor; `SEVIYE_ICI` tetiği stop olacak `47` işlemde `+15.1 R` kazandırıyor, hedefe gidecek `2` işlemde `-5.0 R` kaybettiriyor. Bir tetik ancak hedefe gidecek işlemlerde nadiren yanıyorsa işe yarar.
- **Bütün kümelerde (D7, D6, D1) iki dönemde de artı olan varyant:** `yarim_seviye_ici_cik`, `bir_seviye_ici_cik`, `bir_seviye_ici_basabas`. Kümeler iç içe olduğu için bu, bağımsız üç doğrulama değildir.

## Kümeler yan yana

Üç küme iç içedir (D7 ⊂ D6 ⊂ D1); aynı yönde çıkmaları üç bağımsız doğrulama değildir.

| Eşik | Tepki | Tetik | D7 fark (karar) | D6 fark (karar) | D1 fark (karar) |
|---|---|---|---:|---:|---:|
| 0.5 ATR | Sonraki açılışta çık | HER_ISLEM | -0.0637 (GECMEDI) | -0.0322 (GECMEDI) | -0.0474 (ZARARLI) |
| 0.5 ATR | Sonraki açılışta çık | ENGEL | -0.0239 (GECMEDI) | -0.0134 (GECMEDI) | -0.0357 (ZARARLI) |
| 0.5 ATR | Sonraki açılışta çık | STABIL | -0.0078 (GECMEDI) | +0.0044 (ZAYIF_ARTI) | +0.0011 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | MS | -0.0088 (GECMEDI) | -0.0097 (GECMEDI) | -0.0162 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | BLOK | -0.0199 (GECMEDI) | -0.0143 (GECMEDI) | -0.0162 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | SEVIYE_ICI | +0.0069 (ZAYIF_ARTI) | +0.0067 (ZAYIF_ARTI) | +0.0061 (ZAYIF_ARTI) |
| 0.5 ATR | Sonraki açılışta çık | FRM | -0.0075 (GECMEDI) | -0.0056 (GECMEDI) | -0.0014 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | MS_SUPURME | -0.0059 (GECMEDI) | +0.0004 (GECMEDI) | -0.0092 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | VP_TERS | -0.0195 (GECMEDI) | -0.0087 (GECMEDI) | -0.0008 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | ENDEKS | -0.0169 (GECMEDI) | -0.0089 (GECMEDI) | -0.0094 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | HERHANGI | -0.0331 (GECMEDI) | -0.0190 (GECMEDI) | -0.0299 (GECMEDI) |
| 0.5 ATR | Sonraki açılışta çık | IKI_FARKLI | -0.0128 (GECMEDI) | -0.0047 (GECMEDI) | -0.0106 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | HER_ISLEM | -0.0600 (GECMEDI) | -0.0388 (GECMEDI) | -0.0372 (ZARARLI) |
| 0.5 ATR | Stopu girişe çek | ENGEL | -0.0130 (GECMEDI) | -0.0085 (GECMEDI) | -0.0278 (ZARARLI) |
| 0.5 ATR | Stopu girişe çek | STABIL | -0.0019 (SAYILMAZ_N<30) | +0.0052 (ZAYIF_ARTI) | +0.0009 (ZAYIF_ARTI) |
| 0.5 ATR | Stopu girişe çek | MS | -0.0069 (GECMEDI) | -0.0076 (GECMEDI) | -0.0110 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | BLOK | -0.0086 (GECMEDI) | -0.0099 (GECMEDI) | -0.0170 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | SEVIYE_ICI | +0.0069 (ZAYIF_ARTI) | +0.0067 (ZAYIF_ARTI) | +0.0054 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | FRM | -0.0075 (GECMEDI) | -0.0089 (GECMEDI) | -0.0007 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | MS_SUPURME | +0.0009 (GECMEDI) | +0.0078 (GECMEDI) | -0.0046 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | VP_TERS | -0.0080 (GECMEDI) | -0.0043 (GECMEDI) | -0.0011 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | ENDEKS | -0.0103 (GECMEDI) | -0.0051 (GECMEDI) | -0.0031 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | HERHANGI | -0.0226 (GECMEDI) | -0.0145 (GECMEDI) | -0.0226 (GECMEDI) |
| 0.5 ATR | Stopu girişe çek | IKI_FARKLI | +0.0017 (GECMEDI) | +0.0038 (GECMEDI) | -0.0061 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | HER_ISLEM | -0.0304 (GECMEDI) | -0.0028 (GECMEDI) | -0.0039 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | ENGEL | -0.0154 (GECMEDI) | -0.0039 (GECMEDI) | -0.0044 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | STABIL | -0.0070 (SAYILMAZ_N<30) | -0.0044 (GECMEDI) | +0.0078 (ZAYIF_ARTI) |
| 1 ATR | Sonraki açılışta çık | MS | -0.0082 (GECMEDI) | -0.0097 (GECMEDI) | -0.0043 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | BLOK | -0.0114 (GECMEDI) | +0.0001 (GECMEDI) | +0.0008 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | SEVIYE_ICI | +0.0067 (SAYILMAZ_N<30) | +0.0064 (ZAYIF_ARTI) | +0.0056 (UMUT_VAR) |
| 1 ATR | Sonraki açılışta çık | FRM | -0.0005 (SAYILMAZ_N<30) | +0.0014 (GECMEDI) | -0.0035 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | MS_SUPURME | +0.0016 (GECMEDI) | -0.0007 (GECMEDI) | +0.0005 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | VP_TERS | -0.0162 (GECMEDI) | -0.0076 (GECMEDI) | -0.0016 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | ENDEKS | -0.0037 (GECMEDI) | -0.0001 (GECMEDI) | -0.0011 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | HERHANGI | -0.0192 (GECMEDI) | -0.0076 (GECMEDI) | -0.0048 (GECMEDI) |
| 1 ATR | Sonraki açılışta çık | IKI_FARKLI | -0.0045 (GECMEDI) | -0.0024 (GECMEDI) | -0.0014 (GECMEDI) |
| 1 ATR | Stopu girişe çek | HER_ISLEM | -0.0203 (GECMEDI) | -0.0144 (GECMEDI) | -0.0087 (GECMEDI) |
| 1 ATR | Stopu girişe çek | ENGEL | +0.0058 (GECMEDI) | -0.0039 (GECMEDI) | -0.0071 (GECMEDI) |
| 1 ATR | Stopu girişe çek | STABIL | -0.0051 (SAYILMAZ_N<30) | -0.0048 (GECMEDI) | +0.0030 (ZAYIF_ARTI) |
| 1 ATR | Stopu girişe çek | MS | -0.0011 (GECMEDI) | -0.0080 (GECMEDI) | -0.0025 (GECMEDI) |
| 1 ATR | Stopu girişe çek | BLOK | +0.0102 (ZAYIF_ARTI) | +0.0052 (GECMEDI) | -0.0022 (GECMEDI) |
| 1 ATR | Stopu girişe çek | SEVIYE_ICI | +0.0067 (SAYILMAZ_N<30) | +0.0064 (ZAYIF_ARTI) | +0.0051 (UMUT_VAR) |
| 1 ATR | Stopu girişe çek | FRM | +0.0013 (SAYILMAZ_N<30) | -0.0012 (GECMEDI) | -0.0029 (GECMEDI) |
| 1 ATR | Stopu girişe çek | MS_SUPURME | +0.0046 (GECMEDI) | +0.0038 (GECMEDI) | +0.0003 (GECMEDI) |
| 1 ATR | Stopu girişe çek | VP_TERS | -0.0098 (GECMEDI) | -0.0072 (GECMEDI) | -0.0027 (GECMEDI) |
| 1 ATR | Stopu girişe çek | ENDEKS | +0.0027 (ZAYIF_ARTI) | -0.0028 (GECMEDI) | -0.0002 (GECMEDI) |
| 1 ATR | Stopu girişe çek | HERHANGI | -0.0004 (GECMEDI) | -0.0080 (GECMEDI) | -0.0078 (GECMEDI) |
| 1 ATR | Stopu girişe çek | IKI_FARKLI | +0.0064 (ZAYIF_ARTI) | +0.0024 (GECMEDI) | -0.0018 (GECMEDI) |

## D7_A_Arti — 637 işlem

Keşif `414`, doğrulama `223`; baz net `+0.115 R`. Baz sonuç: stop `280`, hedef `262`, süre sonu / diğer `95`.

### 0.5 ATR gördükten sonra — tepki: sonraki açılışta çık

Çıkıştan önce 0.5 ATR gören işlem: `411`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 411 | 411 | 175 / 233 | 129: +160.9 R | 194: -197.1 R | 88: -4.4 R | -0.0637 | [-0.1399, +0.0216] | -0.0258 (258) / -0.1341 (153) | -40.6 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 216 | 216 | 92 / 124 | 65: +76.6 R | 86: -87.5 R | 65: -4.3 R | -0.0239 | [-0.0827, +0.0284] | -0.0208 (134) / -0.0296 (82) | -15.2 | **GECMEDI** |
| … karşı Stabil seviyesi | 31 | 31 | 11 / 20 | 7: +7.0 R | 11: -11.7 R | 13: -0.3 R | -0.0078 | [-0.0279, +0.0100] | -0.0053 (21) / -0.0125 (10) | -5.0 | **GECMEDI** |
| … karşı Market Structure seviyesi | 150 | 150 | 69 / 81 | 49: +54.5 R | 57: -59.4 R | 44: -0.8 R | -0.0088 | [-0.0684, +0.0347] | -0.0078 (83) / -0.0104 (67) | -5.6 | **GECMEDI** |
| … karşı OB / FVG bandı | 146 | 146 | 57 / 89 | 36: +45.9 R | 62: -55.9 R | 48: -2.7 R | -0.0199 | [-0.0605, +0.0259] | -0.0098 (98) / -0.0386 (48) | -12.7 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 53 | 53 | 43 / 5 | 47: +15.1 R | 2: -5.0 R | 4: -5.7 R | +0.0069 | [-0.0130, +0.0244] | +0.0098 (38) / +0.0015 (15) | +4.4 | **ZAYIF_ARTI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 75 | 75 | 45 / 27 | 43: +21.8 R | 16: -20.6 R | 16: -5.9 R | -0.0075 | [-0.0357, +0.0187] | -0.0083 (53) / -0.0058 (22) | -4.8 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 79 | 79 | 44 / 33 | 36: +18.1 R | 16: -18.1 R | 27: -3.6 R | -0.0059 | [-0.0327, +0.0172] | +0.0054 (50) / -0.0268 (29) | -3.8 | **GECMEDI** |
| Ters hacim baskısı | 96 | 96 | 46 / 46 | 33: +19.3 R | 20: -22.7 R | 43: -9.0 R | -0.0195 | [-0.0458, +0.0047] | -0.0166 (60) / -0.0248 (36) | -12.4 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 150 | 150 | 73 / 74 | 58: +48.1 R | 46: -48.5 R | 46: -10.5 R | -0.0169 | [-0.0549, +0.0216] | -0.0118 (89) / -0.0265 (61) | -10.8 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 274 | 274 | 125 / 146 | 93: +91.9 R | 101: -104.1 R | 80: -8.9 R | -0.0331 | [-0.0950, +0.0215] | -0.0320 (171) / -0.0350 (103) | -21.1 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 140 | 140 | 75 / 60 | 63: +35.9 R | 27: -33.7 R | 50: -10.4 R | -0.0128 | [-0.0538, +0.0224] | -0.0067 (91) / -0.0241 (49) | -8.2 | **GECMEDI** |

### 0.5 ATR gördükten sonra — tepki: stopu girişe çek

Çıkıştan önce 0.5 ATR gören işlem: `411`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 411 | 285 | 148 / 134 | 129: +113.9 R | 84: -129.1 R | 72: -23.0 R | -0.0600 | [-0.1328, +0.0258] | -0.0496 (184) / -0.0793 (101) | -38.2 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 216 | 152 | 79 / 73 | 65: +57.8 R | 38: -54.7 R | 49: -11.3 R | -0.0130 | [-0.0633, +0.0384] | -0.0113 (95) / -0.0161 (57) | -8.3 | **GECMEDI** |
| … karşı Stabil seviyesi | 31 | 19 | 8 / 11 | 7: +6.2 R | 3: -5.5 R | 9: -2.0 R | -0.0019 | [-0.0216, +0.0122] | -0.0051 (13) / +0.0041 (6) | -1.2 | **SAYILMAZ_N<30** |
| … karşı Market Structure seviyesi | 150 | 108 | 59 / 49 | 49: +41.3 R | 26: -39.0 R | 33: -6.7 R | -0.0069 | [-0.0549, +0.0344] | -0.0097 (60) / -0.0016 (48) | -4.4 | **GECMEDI** |
| … karşı OB / FVG bandı | 146 | 91 | 47 / 44 | 36: +33.6 R | 23: -31.7 R | 32: -7.3 R | -0.0086 | [-0.0413, +0.0307] | -0.0036 (63) / -0.0178 (28) | -5.5 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 53 | 53 | 43 / 5 | 47: +15.1 R | 2: -5.0 R | 4: -5.7 R | +0.0069 | [-0.0130, +0.0244] | +0.0098 (38) / +0.0015 (15) | +4.4 | **ZAYIF_ARTI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 75 | 67 | 44 / 20 | 43: +19.8 R | 11: -18.7 R | 13: -6.0 R | -0.0075 | [-0.0406, +0.0182] | -0.0115 (49) / -0.0000 (18) | -4.8 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 79 | 67 | 41 / 24 | 36: +17.0 R | 8: -10.2 R | 23: -6.2 R | +0.0009 | [-0.0218, +0.0207] | +0.0080 (41) / -0.0121 (26) | +0.6 | **GECMEDI** |
| Ters hacim baskısı | 96 | 78 | 41 / 34 | 33: +18.6 R | 9: -13.1 R | 36: -10.7 R | -0.0080 | [-0.0375, +0.0141] | -0.0082 (49) / -0.0078 (29) | -5.1 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 150 | 113 | 63 / 48 | 58: +39.4 R | 21: -30.7 R | 34: -15.3 R | -0.0103 | [-0.0449, +0.0226] | -0.0066 (70) / -0.0171 (43) | -6.5 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 274 | 204 | 110 / 92 | 93: +72.1 R | 47: -67.1 R | 64: -19.4 R | -0.0226 | [-0.0845, +0.0355] | -0.0213 (128) / -0.0252 (76) | -14.4 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 140 | 115 | 69 / 41 | 63: +33.4 R | 14: -21.8 R | 38: -10.6 R | +0.0017 | [-0.0346, +0.0317] | -0.0016 (75) / +0.0077 (40) | +1.1 | **GECMEDI** |

### 1 ATR gördükten sonra — tepki: sonraki açılışta çık

Çıkıştan önce 1 ATR gören işlem: `293`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 293 | 293 | 110 / 181 | 58: +90.9 R | 163: -122.4 R | 72: +12.1 R | -0.0304 | [-0.0886, +0.0290] | -0.0221 (177) / -0.0459 (116) | -19.4 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 140 | 140 | 55 / 85 | 28: +40.1 R | 64: -54.5 R | 48: +4.5 R | -0.0154 | [-0.0560, +0.0269] | -0.0123 (85) / -0.0212 (55) | -9.8 | **GECMEDI** |
| … karşı Stabil seviyesi | 18 | 18 | 5 / 13 | 1: +1.0 R | 7: -5.6 R | 10: +0.2 R | -0.0070 | [-0.0196, +0.0034] | -0.0050 (14) / -0.0107 (4) | -4.5 | **SAYILMAZ_N<30** |
| … karşı Market Structure seviyesi | 95 | 95 | 39 / 56 | 23: +30.9 R | 42: -38.1 R | 30: +2.0 R | -0.0082 | [-0.0470, +0.0266] | -0.0048 (51) / -0.0143 (44) | -5.2 | **GECMEDI** |
| … karşı OB / FVG bandı | 93 | 93 | 32 / 61 | 15: +23.1 R | 45: -32.9 R | 33: +2.6 R | -0.0114 | [-0.0403, +0.0189] | -0.0052 (61) / -0.0228 (32) | -7.2 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 20 | 20 | 17 / 1 | 19: +7.2 R | 1: -2.9 R | — | +0.0067 | [-0.0066, +0.0176] | +0.0057 (14) / +0.0086 (6) | +4.3 | **SAYILMAZ_N<30** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 26 | 26 | 16 / 9 | 14: +5.4 R | 5: -6.0 R | 7: +0.3 R | -0.0005 | [-0.0159, +0.0116] | -0.0016 (19) / +0.0015 (7) | -0.3 | **SAYILMAZ_N<30** |
| Market Structure ters süpürme / sahte kırılım | 45 | 45 | 23 / 21 | 15: +8.3 R | 10: -8.8 R | 20: +1.5 R | +0.0016 | [-0.0128, +0.0160] | +0.0116 (31) / -0.0170 (14) | +1.0 | **GECMEDI** |
| Ters hacim baskısı | 59 | 59 | 23 / 32 | 14: +9.7 R | 15: -16.4 R | 30: -3.6 R | -0.0162 | [-0.0358, +0.0028] | -0.0204 (35) / -0.0083 (24) | -10.3 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 90 | 90 | 39 / 48 | 26: +26.2 R | 32: -26.8 R | 32: -1.8 R | -0.0037 | [-0.0367, +0.0318] | -0.0122 (46) / +0.0121 (44) | -2.4 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 171 | 171 | 72 / 97 | 40: +46.6 R | 74: -64.0 R | 57: +5.2 R | -0.0192 | [-0.0631, +0.0220] | -0.0290 (105) / -0.0010 (66) | -12.2 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 75 | 75 | 35 / 37 | 24: +16.1 R | 15: -17.1 R | 36: -1.9 R | -0.0045 | [-0.0301, +0.0188] | +0.0058 (48) / -0.0237 (27) | -2.9 | **GECMEDI** |

### 1 ATR gördükten sonra — tepki: stopu girişe çek

Çıkıştan önce 1 ATR gören işlem: `293`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 293 | 142 | 72 / 68 | 58: +53.8 R | 39: -60.1 R | 45: -6.7 R | -0.0203 | [-0.0641, +0.0241] | -0.0151 (84) / -0.0301 (58) | -12.9 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 140 | 68 | 37 / 31 | 28: +27.1 R | 12: -19.2 R | 28: -4.3 R | +0.0058 | [-0.0231, +0.0337] | +0.0100 (39) / -0.0021 (29) | +3.7 | **GECMEDI** |
| … karşı Stabil seviyesi | 18 | 8 | 2 / 6 | 1: +1.0 R | 2: -3.6 R | 5: -0.7 R | -0.0051 | [-0.0159, +0.0035] | -0.0028 (5) / -0.0094 (3) | -3.3 | **SAYILMAZ_N<30** |
| … karşı Market Structure seviyesi | 95 | 53 | 30 / 23 | 23: +21.1 R | 11: -18.4 R | 19: -3.5 R | -0.0011 | [-0.0295, +0.0258] | +0.0024 (27) / -0.0075 (26) | -0.7 | **GECMEDI** |
| … karşı OB / FVG bandı | 93 | 38 | 21 / 17 | 15: +15.2 R | 5: -6.5 R | 18: -2.2 R | +0.0102 | [-0.0070, +0.0287] | +0.0083 (27) / +0.0137 (11) | +6.5 | **ZAYIF_ARTI** |
| Kapanış tez seviyesinin ters tarafında | 20 | 20 | 17 / 1 | 19: +7.2 R | 1: -2.9 R | — | +0.0067 | [-0.0066, +0.0176] | +0.0057 (14) / +0.0086 (6) | +4.3 | **SAYILMAZ_N<30** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 26 | 21 | 16 / 4 | 14: +5.3 R | 2: -4.6 R | 5: +0.1 R | +0.0013 | [-0.0140, +0.0125] | -0.0014 (16) / +0.0064 (5) | +0.8 | **SAYILMAZ_N<30** |
| Market Structure ters süpürme / sahte kırılım | 45 | 34 | 21 / 12 | 15: +7.7 R | 5: -5.5 R | 14: +0.7 R | +0.0046 | [-0.0088, +0.0169] | +0.0143 (22) / -0.0133 (12) | +3.0 | **GECMEDI** |
| Ters hacim baskısı | 59 | 43 | 18 / 21 | 14: +7.7 R | 6: -8.7 R | 23: -5.2 R | -0.0098 | [-0.0294, +0.0062] | -0.0137 (25) / -0.0025 (18) | -6.2 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 90 | 52 | 28 / 22 | 26: +17.7 R | 7: -10.3 R | 19: -5.7 R | +0.0027 | [-0.0188, +0.0277] | +0.0003 (25) / +0.0072 (27) | +1.8 | **ZAYIF_ARTI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 171 | 94 | 51 / 41 | 40: +32.3 R | 17: -25.9 R | 37: -6.7 R | -0.0004 | [-0.0369, +0.0339] | +0.0002 (54) / -0.0016 (40) | -0.3 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 75 | 53 | 31 / 19 | 24: +14.8 R | 6: -9.0 R | 23: -1.7 R | +0.0064 | [-0.0156, +0.0249] | +0.0092 (33) / +0.0012 (20) | +4.1 | **ZAYIF_ARTI** |

## D6_A_Cekirdek_Veya_Arti — 1124 işlem

Keşif `738`, doğrulama `386`; baz net `+0.061 R`. Baz sonuç: stop `504`, hedef `447`, süre sonu / diğer `173`.

### 0.5 ATR gördükten sonra — tepki: sonraki açılışta çık

Çıkıştan önce 0.5 ATR gören işlem: `718`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 718 | 718 | 319 / 395 | 230: +280.1 R | 328: -325.4 R | 160: +9.1 R | -0.0322 | [-0.1075, +0.0501] | -0.0094 (465) / -0.0760 (253) | -36.2 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 433 | 433 | 195 / 238 | 132: +152.7 R | 177: -172.2 R | 124: +4.4 R | -0.0134 | [-0.0710, +0.0388] | -0.0129 (272) / -0.0144 (161) | -15.1 | **GECMEDI** |
| … karşı Stabil seviyesi | 86 | 86 | 46 / 40 | 31: +30.9 R | 26: -27.4 R | 29: +1.4 R | +0.0044 | [-0.0207, +0.0247] | +0.0064 (61) / +0.0006 (25) | +4.9 | **ZAYIF_ARTI** |
| … karşı Market Structure seviyesi | 295 | 295 | 139 / 156 | 93: +102.5 R | 118: -119.2 R | 84: +5.8 R | -0.0097 | [-0.0621, +0.0319] | -0.0030 (172) / -0.0225 (123) | -10.9 | **GECMEDI** |
| … karşı OB / FVG bandı | 292 | 292 | 123 / 169 | 77: +94.1 R | 126: -114.4 R | 89: +4.2 R | -0.0143 | [-0.0486, +0.0219] | -0.0137 (188) / -0.0155 (104) | -16.1 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 97 | 97 | 79 / 12 | 83: +25.6 R | 3: -7.6 R | 11: -10.4 R | +0.0067 | [-0.0067, +0.0188] | +0.0063 (65) / +0.0075 (32) | +7.5 | **ZAYIF_ARTI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 141 | 141 | 82 / 56 | 73: +40.8 R | 36: -40.7 R | 32: -6.4 R | -0.0056 | [-0.0268, +0.0143] | -0.0050 (97) / -0.0069 (44) | -6.3 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 178 | 178 | 103 / 73 | 77: +51.0 R | 44: -45.9 R | 57: -4.7 R | +0.0004 | [-0.0222, +0.0213] | +0.0077 (116) / -0.0136 (62) | +0.5 | **GECMEDI** |
| Ters hacim baskısı | 179 | 179 | 99 / 75 | 63: +35.6 R | 31: -35.3 R | 85: -10.0 R | -0.0087 | [-0.0340, +0.0134] | -0.0115 (109) / -0.0032 (70) | -9.7 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 272 | 272 | 135 / 131 | 105: +87.0 R | 85: -84.8 R | 82: -12.1 R | -0.0089 | [-0.0395, +0.0202] | -0.0059 (172) / -0.0146 (100) | -9.9 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 528 | 528 | 251 / 274 | 183: +181.0 R | 200: -200.3 R | 145: -2.0 R | -0.0190 | [-0.0819, +0.0445] | -0.0219 (338) / -0.0134 (190) | -21.3 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 297 | 297 | 171 / 120 | 126: +77.8 R | 67: -73.5 R | 104: -9.5 R | -0.0047 | [-0.0409, +0.0248] | -0.0010 (194) / -0.0117 (103) | -5.3 | **GECMEDI** |

### 0.5 ATR gördükten sonra — tepki: stopu girişe çek

Çıkıştan önce 0.5 ATR gören işlem: `718`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 718 | 514 | 273 / 232 | 230: +200.2 R | 142: -209.3 R | 142: -34.5 R | -0.0388 | [-0.1079, +0.0361] | -0.0318 (340) / -0.0521 (174) | -43.6 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 433 | 310 | 167 / 140 | 132: +112.5 R | 73: -103.2 R | 105: -19.0 R | -0.0085 | [-0.0550, +0.0333] | -0.0083 (195) / -0.0090 (115) | -9.6 | **GECMEDI** |
| … karşı Stabil seviyesi | 86 | 65 | 39 / 25 | 31: +23.4 R | 10: -14.0 R | 24: -3.6 R | +0.0052 | [-0.0185, +0.0219] | +0.0013 (47) / +0.0125 (18) | +5.8 | **ZAYIF_ARTI** |
| … karşı Market Structure seviyesi | 295 | 215 | 120 / 94 | 93: +77.8 R | 53: -76.2 R | 69: -10.1 R | -0.0076 | [-0.0487, +0.0237] | -0.0058 (125) / -0.0111 (90) | -8.5 | **GECMEDI** |
| … karşı OB / FVG bandı | 292 | 197 | 100 / 94 | 77: +66.5 R | 47: -63.8 R | 73: -13.9 R | -0.0099 | [-0.0384, +0.0214] | -0.0118 (129) / -0.0063 (68) | -11.1 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 97 | 97 | 79 / 12 | 83: +25.6 R | 3: -7.6 R | 11: -10.4 R | +0.0067 | [-0.0067, +0.0188] | +0.0063 (65) / +0.0075 (32) | +7.5 | **ZAYIF_ARTI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 141 | 126 | 78 / 45 | 73: +36.5 R | 24: -36.0 R | 29: -10.5 R | -0.0089 | [-0.0303, +0.0110] | -0.0090 (87) / -0.0086 (39) | -10.0 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 178 | 148 | 96 / 50 | 77: +45.7 R | 20: -26.2 R | 51: -10.8 R | +0.0078 | [-0.0129, +0.0269] | +0.0128 (94) / -0.0019 (54) | +8.8 | **GECMEDI** |
| Ters hacim baskısı | 179 | 155 | 88 / 63 | 63: +34.0 R | 17: -23.2 R | 75: -15.7 R | -0.0043 | [-0.0314, +0.0169] | -0.0089 (94) / +0.0044 (61) | -4.9 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 272 | 209 | 119 / 86 | 105: +72.5 R | 38: -53.9 R | 66: -24.3 R | -0.0051 | [-0.0316, +0.0199] | +0.0019 (132) / -0.0184 (77) | -5.7 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 528 | 398 | 223 / 170 | 183: +138.9 R | 88: -124.9 R | 127: -30.4 R | -0.0145 | [-0.0682, +0.0400] | -0.0134 (255) / -0.0166 (143) | -16.3 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 297 | 248 | 154 / 88 | 126: +71.1 R | 35: -50.3 R | 87: -16.5 R | +0.0038 | [-0.0271, +0.0296] | -0.0012 (161) / +0.0135 (87) | +4.3 | **GECMEDI** |

### 1 ATR gördükten sonra — tepki: sonraki açılışta çık

Çıkıştan önce 1 ATR gören işlem: `502`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 502 | 502 | 202 / 295 | 104: +154.1 R | 269: -189.4 R | 129: +32.2 R | -0.0028 | [-0.0555, +0.0454] | -0.0049 (316) / +0.0014 (186) | -3.1 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 278 | 278 | 115 / 162 | 58: +79.6 R | 132: -100.0 R | 88: +16.0 R | -0.0039 | [-0.0470, +0.0356] | -0.0044 (171) / -0.0029 (107) | -4.3 | **GECMEDI** |
| … karşı Stabil seviyesi | 48 | 48 | 19 / 29 | 10: +12.0 R | 18: -16.5 R | 20: -0.4 R | -0.0044 | [-0.0215, +0.0091] | -0.0032 (37) / -0.0066 (11) | -4.9 | **GECMEDI** |
| … karşı Market Structure seviyesi | 189 | 189 | 79 / 110 | 44: +56.0 R | 88: -74.4 R | 57: +7.5 R | -0.0097 | [-0.0454, +0.0236] | -0.0057 (110) / -0.0175 (79) | -10.9 | **GECMEDI** |
| … karşı OB / FVG bandı | 179 | 179 | 70 / 108 | 33: +46.8 R | 86: -57.1 R | 60: +10.4 R | +0.0001 | [-0.0229, +0.0250] | +0.0004 (108) / -0.0004 (71) | +0.1 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 37 | 37 | 32 / 3 | 33: +10.8 R | 1: -2.9 R | 3: -0.7 R | +0.0064 | [-0.0016, +0.0132] | +0.0058 (23) / +0.0076 (14) | +7.2 | **ZAYIF_ARTI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 55 | 55 | 33 / 21 | 25: +12.0 R | 13: -11.7 R | 17: +1.3 R | +0.0014 | [-0.0087, +0.0126] | +0.0042 (34) / -0.0039 (21) | +1.6 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 108 | 108 | 60 / 47 | 36: +24.8 R | 28: -27.0 R | 44: +1.4 R | -0.0007 | [-0.0158, +0.0154] | +0.0035 (77) / -0.0088 (31) | -0.8 | **GECMEDI** |
| Ters hacim baskısı | 119 | 119 | 61 / 53 | 31: +21.0 R | 24: -27.5 R | 64: -2.0 R | -0.0076 | [-0.0266, +0.0099] | -0.0142 (70) / +0.0050 (49) | -8.5 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 165 | 165 | 76 / 84 | 50: +47.7 R | 57: -47.0 R | 58: -0.8 R | -0.0001 | [-0.0237, +0.0222] | -0.0116 (97) / +0.0220 (68) | -0.1 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 329 | 329 | 144 / 182 | 78: +89.9 R | 146: -114.6 R | 105: +16.1 R | -0.0076 | [-0.0518, +0.0309] | -0.0170 (207) / +0.0103 (122) | -8.6 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 164 | 164 | 87 / 73 | 50: +36.2 R | 41: -41.0 R | 73: +2.1 R | -0.0024 | [-0.0233, +0.0179] | +0.0009 (105) / -0.0088 (59) | -2.7 | **GECMEDI** |

### 1 ATR gördükten sonra — tepki: stopu girişe çek

Çıkıştan önce 1 ATR gören işlem: `502`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 502 | 262 | 137 / 120 | 104: +91.8 R | 64: -94.3 R | 94: -13.8 R | -0.0144 | [-0.0581, +0.0258] | -0.0189 (163) / -0.0059 (99) | -16.2 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 278 | 153 | 81 / 71 | 58: +51.9 R | 32: -47.0 R | 63: -9.3 R | -0.0039 | [-0.0318, +0.0237] | -0.0060 (92) / +0.0001 (61) | -4.4 | **GECMEDI** |
| … karşı Stabil seviyesi | 48 | 32 | 15 / 17 | 10: +8.1 R | 8: -10.3 R | 14: -3.2 R | -0.0048 | [-0.0187, +0.0068] | -0.0055 (24) / -0.0035 (8) | -5.4 | **GECMEDI** |
| … karşı Market Structure seviyesi | 189 | 115 | 63 / 52 | 44: +39.2 R | 28: -42.0 R | 43: -6.1 R | -0.0080 | [-0.0339, +0.0141] | -0.0089 (66) / -0.0061 (49) | -8.9 | **GECMEDI** |
| … karşı OB / FVG bandı | 179 | 89 | 48 / 40 | 33: +29.0 R | 13: -16.7 R | 43: -6.5 R | +0.0052 | [-0.0115, +0.0217] | -0.0009 (55) / +0.0169 (34) | +5.9 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 37 | 37 | 32 / 3 | 33: +10.8 R | 1: -2.9 R | 3: -0.7 R | +0.0064 | [-0.0016, +0.0132] | +0.0058 (23) / +0.0076 (14) | +7.2 | **ZAYIF_ARTI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 55 | 47 | 31 / 15 | 25: +10.6 R | 7: -10.5 R | 15: -1.5 R | -0.0012 | [-0.0119, +0.0081] | +0.0002 (28) / -0.0039 (19) | -1.4 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 108 | 83 | 53 / 29 | 36: +21.3 R | 11: -13.7 R | 36: -3.3 R | +0.0038 | [-0.0088, +0.0162] | +0.0064 (58) / -0.0012 (25) | +4.2 | **GECMEDI** |
| Ters hacim baskısı | 119 | 97 | 50 / 42 | 31: +18.1 R | 13: -18.1 R | 53: -8.1 R | -0.0072 | [-0.0279, +0.0094] | -0.0142 (56) / +0.0062 (41) | -8.1 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 165 | 107 | 58 / 46 | 50: +35.2 R | 17: -25.6 R | 40: -12.8 R | -0.0028 | [-0.0220, +0.0154] | -0.0057 (59) / +0.0029 (48) | -3.1 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 329 | 196 | 106 / 87 | 78: +60.8 R | 39: -55.7 R | 79: -14.2 R | -0.0080 | [-0.0423, +0.0226] | -0.0122 (119) / -0.0001 (77) | -9.0 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 164 | 124 | 73 / 47 | 50: +32.0 R | 18: -24.7 R | 56: -4.6 R | +0.0024 | [-0.0164, +0.0203] | -0.0012 (77) / +0.0094 (47) | +2.7 | **GECMEDI** |

## D1_Birincil — 4233 işlem

Keşif `2723`, doğrulama `1510`; baz net `+0.010 R`. Baz sonuç: stop `2158`, hedef `1435`, süre sonu / diğer `640`.

### 0.5 ATR gördükten sonra — tepki: sonraki açılışta çık

Çıkıştan önce 0.5 ATR gören işlem: `2539`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 2539 | 2539 | 1160 / 1362 | 851: +1121.5 R | 1096: -1298.3 R | 592: -23.7 R | -0.0474 | [-0.0903, -0.0017] | -0.0321 (1601) / -0.0749 (938) | -200.4 | **ZARARLI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 1855 | 1855 | 847 / 996 | 592: +761.7 R | 758: -908.5 R | 505: -4.2 R | -0.0357 | [-0.0689, -0.0013] | -0.0250 (1140) / -0.0548 (715) | -150.9 | **ZARARLI** |
| … karşı Stabil seviyesi | 377 | 377 | 196 / 173 | 136: +163.4 R | 117: -154.9 R | 124: -3.9 R | +0.0011 | [-0.0129, +0.0146] | +0.0024 (252) / -0.0013 (125) | +4.5 | **GECMEDI** |
| … karşı Market Structure seviyesi | 1268 | 1268 | 611 / 647 | 423: +509.3 R | 479: -573.0 R | 366: -4.7 R | -0.0162 | [-0.0429, +0.0122] | +0.0008 (739) / -0.0467 (529) | -68.4 | **GECMEDI** |
| … karşı OB / FVG bandı | 1304 | 1304 | 589 / 707 | 390: +540.5 R | 548: -628.5 R | 366: +19.4 R | -0.0162 | [-0.0424, +0.0118] | -0.0181 (816) / -0.0127 (488) | -68.6 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 392 | 392 | 301 / 65 | 318: +120.8 R | 16: -47.9 R | 58: -46.8 R | +0.0061 | [-0.0026, +0.0142] | +0.0091 (246) / +0.0008 (146) | +26.0 | **ZAYIF_ARTI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 374 | 374 | 221 / 144 | 188: +126.4 R | 92: -114.0 R | 94: -18.4 R | -0.0014 | [-0.0104, +0.0078] | +0.0049 (232) / -0.0128 (142) | -6.0 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 650 | 650 | 356 / 287 | 264: +241.4 R | 188: -256.9 R | 198: -23.6 R | -0.0092 | [-0.0225, +0.0045] | +0.0028 (416) / -0.0311 (234) | -39.1 | **GECMEDI** |
| Ters hacim baskısı | 656 | 656 | 389 / 254 | 269: +190.7 R | 109: -153.3 R | 278: -40.9 R | -0.0008 | [-0.0138, +0.0127] | -0.0006 (370) / -0.0013 (286) | -3.5 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 925 | 925 | 481 / 433 | 359: +340.4 R | 266: -321.1 R | 300: -59.1 R | -0.0094 | [-0.0289, +0.0126] | +0.0023 (568) / -0.0305 (357) | -39.7 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 2091 | 2091 | 1001 / 1071 | 732: +862.4 R | 808: -973.5 R | 551: -15.6 R | -0.0299 | [-0.0634, +0.0049] | -0.0181 (1293) / -0.0514 (798) | -126.7 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 1119 | 1119 | 643 / 456 | 486: +383.3 R | 266: -374.4 R | 367: -53.9 R | -0.0106 | [-0.0291, +0.0088] | +0.0021 (682) / -0.0336 (437) | -45.0 | **GECMEDI** |

### 0.5 ATR gördükten sonra — tepki: stopu girişe çek

Çıkıştan önce 0.5 ATR gören işlem: `2539`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 2539 | 1774 | 1014 / 742 | 851: +769.7 R | 425: -753.6 R | 498: -173.4 R | -0.0372 | [-0.0666, -0.0068] | -0.0263 (1122) / -0.0568 (652) | -157.3 | **ZARARLI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 1855 | 1293 | 730 / 552 | 592: +530.8 R | 288: -518.3 R | 413: -130.1 R | -0.0278 | [-0.0527, -0.0030] | -0.0207 (789) / -0.0406 (504) | -117.6 | **ZARARLI** |
| … karşı Stabil seviyesi | 377 | 279 | 171 / 104 | 136: +115.9 R | 48: -87.4 R | 95: -24.9 R | +0.0009 | [-0.0113, +0.0110] | +0.0013 (182) / +0.0001 (97) | +3.7 | **ZAYIF_ARTI** |
| … karşı Market Structure seviyesi | 1268 | 905 | 526 / 372 | 423: +369.8 R | 193: -334.3 R | 289: -81.8 R | -0.0110 | [-0.0331, +0.0099] | -0.0006 (523) / -0.0297 (382) | -46.4 | **GECMEDI** |
| … karşı OB / FVG bandı | 1304 | 868 | 490 / 372 | 390: +356.0 R | 186: -338.0 R | 292: -90.0 R | -0.0170 | [-0.0351, +0.0015] | -0.0161 (536) / -0.0185 (332) | -71.9 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 392 | 392 | 301 / 65 | 318: +118.4 R | 16: -48.0 R | 58: -47.4 R | +0.0054 | [-0.0031, +0.0135] | +0.0090 (246) / -0.0009 (146) | +23.0 | **GECMEDI** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 374 | 322 | 203 / 110 | 188: +111.8 R | 51: -83.9 R | 83: -30.9 R | -0.0007 | [-0.0091, +0.0078] | +0.0037 (206) / -0.0086 (116) | -3.0 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 650 | 520 | 322 / 191 | 264: +192.9 R | 90: -155.6 R | 166: -56.7 R | -0.0046 | [-0.0162, +0.0064] | +0.0032 (331) / -0.0186 (189) | -19.4 | **GECMEDI** |
| Ters hacim baskısı | 656 | 573 | 357 / 204 | 269: +171.5 R | 68: -122.4 R | 236: -53.9 R | -0.0011 | [-0.0133, +0.0116] | +0.0017 (318) / -0.0062 (255) | -4.8 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 925 | 710 | 425 / 277 | 359: +276.6 R | 109: -191.0 R | 242: -98.7 R | -0.0031 | [-0.0190, +0.0129] | +0.0078 (433) / -0.0228 (277) | -13.1 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 2091 | 1511 | 886 / 608 | 732: +620.6 R | 319: -566.5 R | 460: -149.9 R | -0.0226 | [-0.0492, +0.0038] | -0.0123 (930) / -0.0413 (581) | -95.8 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 1119 | 939 | 587 / 331 | 486: +322.1 R | 142: -256.3 R | 311: -91.7 R | -0.0061 | [-0.0236, +0.0103] | -0.0005 (571) / -0.0161 (368) | -25.8 | **GECMEDI** |

### 1 ATR gördükten sonra — tepki: sonraki açılışta çık

Çıkıştan önce 1 ATR gören işlem: `1749`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 1749 | 1749 | 709 / 1026 | 393: +653.8 R | 891: -769.0 R | 465: +98.9 R | -0.0039 | [-0.0325, +0.0268] | -0.0032 (1077) / -0.0050 (672) | -16.3 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 1233 | 1233 | 509 / 712 | 282: +447.6 R | 580: -533.4 R | 371: +67.2 R | -0.0044 | [-0.0290, +0.0199] | -0.0078 (746) / +0.0018 (487) | -18.6 | **GECMEDI** |
| … karşı Stabil seviyesi | 220 | 220 | 113 / 99 | 73: +100.7 R | 69: -79.6 R | 78: +11.9 R | +0.0078 | [-0.0011, +0.0168] | +0.0083 (146) / +0.0069 (74) | +33.0 | **ZAYIF_ARTI** |
| … karşı Market Structure seviyesi | 807 | 807 | 349 / 449 | 201: +292.2 R | 350: -341.9 R | 256: +31.4 R | -0.0043 | [-0.0228, +0.0136] | +0.0020 (471) / -0.0156 (336) | -18.2 | **GECMEDI** |
| … karşı OB / FVG bandı | 883 | 883 | 361 / 514 | 192: +318.3 R | 420: -369.2 R | 271: +54.2 R | +0.0008 | [-0.0199, +0.0212] | -0.0075 (535) / +0.0157 (348) | +3.3 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 164 | 164 | 125 / 25 | 135: +52.2 R | 4: -11.9 R | 25: -16.4 R | +0.0056 | [+0.0005, +0.0105] | +0.0066 (100) / +0.0039 (64) | +23.9 | **UMUT_VAR** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 139 | 139 | 72 / 62 | 51: +27.8 R | 41: -41.1 R | 47: -1.5 R | -0.0035 | [-0.0084, +0.0014] | -0.0024 (77) / -0.0054 (62) | -14.8 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 406 | 406 | 210 / 190 | 138: +146.6 R | 124: -146.4 R | 144: +2.1 R | +0.0005 | [-0.0106, +0.0108] | +0.0039 (260) / -0.0055 (146) | +2.3 | **GECMEDI** |
| Ters hacim baskısı | 419 | 419 | 233 / 174 | 137: +103.9 R | 79: -96.3 R | 203: -14.5 R | -0.0016 | [-0.0104, +0.0082] | -0.0053 (223) / +0.0051 (196) | -6.9 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 549 | 549 | 259 / 281 | 164: +180.3 R | 182: -172.7 R | 203: -12.5 R | -0.0011 | [-0.0139, +0.0115] | +0.0005 (320) / -0.0040 (229) | -4.9 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 1349 | 1349 | 574 / 760 | 331: +482.9 R | 610: -566.9 R | 408: +63.7 R | -0.0048 | [-0.0283, +0.0180] | -0.0100 (823) / +0.0046 (526) | -20.3 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 635 | 635 | 336 / 284 | 217: +197.4 R | 172: -200.3 R | 246: -3.0 R | -0.0014 | [-0.0146, +0.0112] | -0.0002 (371) / -0.0036 (264) | -6.0 | **GECMEDI** |

### 1 ATR gördükten sonra — tepki: stopu girişe çek

Çıkıştan önce 1 ATR gören işlem: `1749`.

| Tetik | Tetiklenen | Sonucu değişen | İyileşen / kötüleşen | Stop olacaklarda (n: toplam) | Hedefe gideceklerde (n: toplam) | Süre sonu / diğer (n: toplam) | Fark R/işlem | En kötü GA | Keşif (etk.) / doğrulama (etk.) | Toplam R | Karar |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Koşulsuz: eşik görüldüğü kapanışta (karşılaştırma tabanı) | 1749 | 898 | 507 / 379 | 393: +368.9 R | 192: -330.2 R | 313: -75.7 R | -0.0087 | [-0.0286, +0.0104] | -0.0121 (548) / -0.0027 (350) | -37.0 | **GECMEDI** |
| Mum bilinen bir karşı engele değdi, kapanışla aşamadı | 1233 | 671 | 376 / 287 | 282: +265.5 R | 138: -240.2 R | 251: -55.2 R | -0.0071 | [-0.0252, +0.0101] | -0.0100 (396) / -0.0018 (275) | -29.9 | **GECMEDI** |
| … karşı Stabil seviyesi | 220 | 156 | 97 / 57 | 73: +65.4 R | 28: -46.2 R | 55: -6.4 R | +0.0030 | [-0.0047, +0.0099] | +0.0034 (97) / +0.0024 (59) | +12.9 | **ZAYIF_ARTI** |
| … karşı Market Structure seviyesi | 807 | 473 | 274 / 193 | 201: +184.7 R | 95: -157.0 R | 177: -38.4 R | -0.0025 | [-0.0175, +0.0101] | -0.0013 (273) / -0.0047 (200) | -10.7 | **GECMEDI** |
| … karşı OB / FVG bandı | 883 | 457 | 261 / 192 | 192: +180.4 R | 86: -153.8 R | 179: -35.9 R | -0.0022 | [-0.0160, +0.0111] | -0.0055 (261) / +0.0037 (196) | -9.3 | **GECMEDI** |
| Kapanış tez seviyesinin ters tarafında | 164 | 164 | 125 / 25 | 135: +49.9 R | 4: -12.1 R | 25: -16.4 R | +0.0051 | [+0.0002, +0.0095] | +0.0064 (100) / +0.0026 (64) | +21.5 | **UMUT_VAR** |
| Formasyon bozuldu (retest ediliyor / teyitsiz / başarısız / karşı kırılım) | 139 | 104 | 58 / 41 | 51: +23.9 R | 18: -27.3 R | 35: -8.9 R | -0.0029 | [-0.0075, +0.0017] | -0.0039 (62) / -0.0012 (42) | -12.4 | **GECMEDI** |
| Market Structure ters süpürme / sahte kırılım | 406 | 300 | 181 / 113 | 138: +107.8 R | 48: -79.7 R | 114: -26.9 R | +0.0003 | [-0.0078, +0.0083] | +0.0009 (189) / -0.0007 (111) | +1.2 | **GECMEDI** |
| Ters hacim baskısı | 419 | 342 | 201 / 129 | 137: +89.7 R | 45: -76.7 R | 160: -24.3 R | -0.0027 | [-0.0109, +0.0056] | -0.0043 (175) / +0.0004 (167) | -11.2 | **GECMEDI** |
| Girişten bu kapanışa endeks işlemin tersine en az %0.5 | 549 | 350 | 203 / 142 | 164: +130.5 R | 43: -76.2 R | 143: -55.0 R | -0.0002 | [-0.0104, +0.0097] | +0.0004 (197) / -0.0012 (153) | -0.6 | **GECMEDI** |
| Domain gözlemlerinden herhangi biri (engel, tez seviyesi, formasyon, süpürme, hacim) | 1349 | 763 | 434 / 318 | 331: +295.4 R | 152: -262.3 R | 280: -66.0 R | -0.0078 | [-0.0258, +0.0102] | -0.0111 (456) / -0.0017 (307) | -32.8 | **GECMEDI** |
| Eşikten beri iki farklı tür domain gözlemi birikti | 635 | 485 | 288 / 181 | 217: +153.2 R | 75: -125.7 R | 193: -35.1 R | -0.0018 | [-0.0134, +0.0091] | -0.0049 (279) / +0.0038 (206) | -7.6 | **GECMEDI** |

## Sınırlar

- Ön-kayıtlı değildir ve çok sayıda varyant sınar; tek tek satırlar değil, keşif / doğrulama tutarlılığı ve kümeler arası tekrar okunmalıdır.
- Mum çözünürlüğündedir: stop ile hedef aynı mumda ise stop sayılır; girişe çekilen stop için de aynı kural geçerlidir (muhafazakâr).
- İki tepki ölçüldü: tam çıkış ve stopu girişe çekme. Sabit oranlı kısmi çıkış ayrı bir ölçüm gerektirmez: masraf pozisyonla orantılı olduğundan pozisyonun bir kısmına uygulanan tepkinin farkı ve güven aralığı tam tepkininkinin aynı oranıdır; eksi olan artıya dönmez. Stopu tetik mumunun ötesine taşıma ve yeniden giriş ölçülmedi.
- Tetikler `kar_gorup_donen` raporunun "tepeden stopa" tablosundaki satırları kapsar ama aynı pencereyi kullanmaz: o tablo tepe mumundan (ancak işlem bittikten sonra bilinir) sayar, tetik eşiğin görüldüğü kapanıştan. O tabloda sayılan her işlemde aynı gözlem tetik olarak da yanar; tetik ayrıca tepe mumu dışındaki mumlarda ve stop olmayan işlemlerde de yanar. Tek fark hacim satırındadır: tablo tepe mumundaki "yüksek çaba – zayıf sonuç" gözlemini de sayar; tetik yalnız ters hacim baskısı etiketidir.
- Tepki işlemin kendi zaman dilimindeki mum kapanışında verilir; mum içi tepki ölçülmedi.
- Endeks tetiği, endeks sembollerinin kendi işlemlerinde tanımsızdır (yanmaz).
- Kâr görme şartı OLMADAN aynı süreç etiketlerinde çıkış ve kâr koruma (stopu kâra kilitleme, hedefte iz sürme) `surec_olcum` raporundadır.
