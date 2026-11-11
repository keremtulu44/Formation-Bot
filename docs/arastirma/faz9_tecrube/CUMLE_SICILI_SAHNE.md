# FAZ9-A — Cümle Sicili & Sahne Ölçümü (Tur A: karar değişmedi)

*Defter: FAZ9-A replay (ana50) · n=412 plan · sonuç 137/132/143 · kârlı %56 · net +175.5A*

## 0) Değişmezlik kanıtı (FAZ8 ile birebir)

| kontrol | sonuç |
|---|---|
| plan kümesi | 412 vs FAZ8 412 → BİREBİR ✓ |
| plan başına sonuç farkı | 0 adet ✓ |
| pnl mutlak fark (ort) | 0.000000 ATR ✓ |

## 1) Cümle sicili — kim hangi iddiayla geldi, nasıl bitti (n≥30)

Her satır = tetikte **aktif** olan bir cümle (iddia); FAZ9 A1 kaydı. Kâr = işlem başına ortalama pnl.

| iddia (kim:id) | n | hedef | stop | zaman | kârlı | net | işlem başı |
|---|---|---|---|---|---|---|---|
| stabil:izle | 410 | 137 | 132 | 141 | %56 | +173.3 | +0.423 |
| blok:konfluans | 402 | 136 | 128 | 138 | %56 | +179.1 | +0.446 |
| formasyon:izle | 356 | 115 | 114 | 127 | %56 | +143.0 | +0.402 |

*Nadir (n<30, yorum yok): ms:olasi_tepki(13)*

## 2) Cümle KOŞULU öbekleri (kosul metni ilk40 karakter, n≥30)

| kim:kosul(40) | n | hedef | stop | zaman | kârlı | net | işlem başı |
|---|---|---|---|---|---|---|---|
| blok:OB bandı temaslı, tepki onayı var | 394 | 131 | 126 | 137 | %56 | +172.2 | +0.437 |
| stabil:zemin ACTIVE, dinamik CONTRACTING, trend | 188 | 54 | 66 | 68 | %53 | +62.1 | +0.330 |
| stabil:zemin ACTIVE, dinamik EXPANDING, trend D | 141 | 53 | 41 | 47 | %58 | +79.0 | +0.560 |
| stabil:zemin ACTIVE, dinamik FLAT, trend DAILY_ | 61 | 23 | 18 | 20 | %57 | +24.6 | +0.404 |

## 3) Sahne ölçümü — etiket × sonuç (n≥30; etiket = kayıt, filtre değil)

| sahne | n | hedef | stop | zaman | kârlı | net | işlem başı |
|---|---|---|---|---|---|---|---|
| TÜMÜ (baseline) | 412 | 137 | 132 | 143 | %56 | +175.5 | +0.426 |
| zemin_onayli | 412 | 137 | 132 | 143 | %56 | +175.5 | +0.426 |
| zone_dolu | 407 | 135 | 132 | 140 | %55 | +168.6 | +0.414 |
| formasyon_aktif | 325 | 107 | 98 | 120 | %57 | +144.4 | +0.444 |
| formasyon_olgun | 320 | 104 | 97 | 119 | %57 | +138.1 | +0.432 |
| zemin_kademe_yukari | 222 | 68 | 77 | 77 | %53 | +92.3 | +0.416 |
| zemin_kademe_asagi | 183 | 65 | 52 | 66 | %60 | +80.3 | +0.439 |
| zemin_yakin | 67 | 29 | 23 | 15 | %57 | +25.3 | +0.377 |
| zone_dar | 61 | 23 | 20 | 18 | %57 | +27.7 | +0.455 |

*Nadir sahneler (n<30): ms_destek(19), zone_genis(18)*

*Etiket sayısı dağılımı: {'zemin_onayli': 412, 'zone_dolu': 407, 'formasyon_aktif': 325, 'formasyon_olgun': 320, 'zemin_kademe_yukari': 222, 'zemin_kademe_asagi': 183, 'zemin_yakin': 67, 'zone_dar': 61, 'ms_destek': 19, 'zone_genis': 18}*

## 4) Çift-kesişim sahneleri (n≥30, en sık6)

| sahne çifti | n | hedef | stop | zaman | kârlı | net | işlem başı |
|---|---|---|---|---|---|---|---|
| zemin_onayli ∧ zone_dolu | 407 | 135 | 132 | 140 | %55 | +168.6 | +0.414 |
| formasyon_aktif ∧ zemin_onayli | 325 | 107 | 98 | 120 | %57 | +144.4 | +0.444 |
| formasyon_aktif ∧ zone_dolu | 321 | 105 | 98 | 118 | %56 | +138.0 | +0.430 |
| formasyon_aktif ∧ formasyon_olgun | 320 | 104 | 97 | 119 | %57 | +138.1 | +0.432 |
| formasyon_olgun ∧ zemin_onayli | 320 | 104 | 97 | 119 | %57 | +138.1 | +0.432 |
| formasyon_olgun ∧ zone_dolu | 317 | 103 | 97 | 117 | %56 | +132.7 | +0.419 |

---
## 5) Yorum kuralları

- Bu rapor **karar vermez** (sözleşme): aday listesidir; her aday ayrı ön-kayıt + kapı ister (FAZ8 usulü).
- n<30 sayılmaz; n<300 nadirdir, yalnız sayı basılır.
- Aleyhte satır da tecrübedir (envanter §I usulü).
- FAZ9 A1/A2 **karar değiştirmedi** (bölüm0 kanıtı) — herhangi bir fark bu raporun değil, replay determinizminin sorunudur.