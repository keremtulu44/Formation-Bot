# Karne masraf katmanı ve mesaj sadeleştirmesi — 2026-11-16

**Durum:** uygulandı · **Kapsam:** yalnız rapor/metin (`karne.py`, `config.py`,
`test_karne.py`, `test_karne_masraf.py`) · **Davranış değişmedi:** sinyal üretimi,
eşikler, alarmlar, grafikler aynı.

## 1. Neden

Karne şunu söylüyordu: *"10 kırılım · hedef 4 · stop 5 · yönünde kapanan 4/10"*.
Eksik olan tek şey **masraf**tı. Her işlemde komisyon (gidiş-dönüş) ve kayma
(alış + satış) ödenir; bunlar düşülünce kâğıt üstünde artı görünen hafta eksi
olabilir. Karar veren sayı budur.

İkinci sorun okunabilirlikti: performans bloğu 6 satır + 4 emoji + 3 ölçü birimi
(adet / yüzde / oran) içeriyordu — göz nereden okuyacağını bilmiyordu.

## 2. Masraf parametreleri (`config.py`)

| Parametre | Varsayılan | Anlam |
|---|---:|---|
| `KARNE_KOMISYON_BPS` | `21.0` | Gidiş-dönüş toplam komisyon, **BSMV dahil** (binde 2,1) |
| `KARNE_KAYMA_ATR` | `0.05` | Tek yön kayma, ATR cinsinden → iki yön uygulanır |

**Varsayılanın gerekçesi (Türkiye perakende, 2026):** aracı kurum/banka
komisyonları on binde 0 (0 komisyonlu fintech) ile binde 2 (banka varsayılanı,
ör. Garanti binde 1,95) arasında; yaygın online oran on binde 6–10. BSMV komisyon
üzerinden %5, ayrıca borsa payı yüz binde 2,5. Seçilen **binde 2,1** =
yan başına on binde 10 + %5 BSMV + borsa payı; yani **ortalama-üst bandı** —
0 komisyonlu kurumda gerçek sonuç bundan daha iyi çıkar, rakam iyimser görünmez.

## 3. Hesap

```
brüt  = hedef → +HEDEF_ATR · ATR      stop → −STOP_ATR · ATR      nötr → ufuk sonu
masraf = KOMISYON_BPS/100  +  KAYMA_ATR · 2 · ATR / entry · 100
net   = brüt − masraf
```

`karne.sinyal_sonucu` çıktısına üç alan eklendi: `brut_pct`, `masraf_pct`,
`net_pct` (bekleyen sinyalde üçü de `None` — uydurma sayı yok).
`karne_hesapla` bunları ortalar (`ort_brut_pct`, `ort_net_pct`, `ort_masraf_pct`)
ve **haftalık kovalara** böler (`haftalik_net`, en çok son 4 hafta;
`haftalik_net_ortanca` yalnız ≥2 kova varsa).

Örnek (entry 100 TL, ATR 2 TL, komisyon binde 2,1, kayma 0,05 ATR → masraf %0,41):

| Durum | Brüt | Net |
|---|---:|---:|
| hedef (1,5 ATR) | +%3,00 | **+%2,59** |
| stop (1,0 ATR) | −%2,00 | **−%2,41** |
| nötr (ufuk sonu +%0,8) | +%0,80 | **+%0,39** |

**Başabaş isabet oranı** (hedef 1,5 / stop 1,0):

| Masraf | Gereken isabet |
|---|---:|
| yok | %40,0 |
| 0,10R | %44,0 |
| **0,16–0,18R (varsayılan)** | **%46,4** |
| 0,25R | %50,0 |

Yani "31 sinyalde 14 hedef (%45)" bugünkü haliyle başabaş gibi görünürken,
masrafla birlikte zarardır.

## 4. Mesaj (öncesi → sonrası)

**Önce** (6 satır, 4 emoji, 3 ölçü birimi):

```
⚡ Kırılım: 10 · yukarı 6 · aşağı 4
 10 bar: hedef 4 · nötr 1 · stop 5
 ✅ Yönünde kapanan: 4/10 (%40)
   ters 6
   ort. lehte +1,4% · aleyhte −0,9%
⚠️ n=10 küçük · 30+ sinyal gerek
```

**Sonra** (bölümlü, emoji yok, tek ölçü birimi):

```
Sonuç
   10 sinyal · yukarı 6 · aşağı 4
   hedef 4 · stop 5 · yatay 1
   Yönünde kapanan: 4/10 (%40)

Para (sinyal başına ortalama)
   Masraf dahil: −%0,21
   Masrafsız: +%0,38
   Masraf: binde 2,1 + kayma
   (komisyon + BSMV dahil)

Son 4 hafta
   +%0,31 · −%0,24 · −%0,15 · −%0,26
   Ortanca: −%0,21

Güven: az veri (10 sinyal)
30+ sinyalden sonra yorum yapılır
```

Kaldırılanlar: `⚡ Kırılım:` satırı, `🎯 <bar>: hedef…` satırı, `✅ Yönünde`
satırındaki emoji, `ters N` satırı, `ort. lehte/aleyhte` satırı (MFE/MAE özeti —
yerini net/brüt ortalamaya bıraktı), `⚠️ n=… küçük` satırı.
Güven eşiği üç kademeye ayrıldı: **n<30 az veri · 30–99 kısmi · ≥100 yeterli**
(`analytics/backtest.py` ile aynı dil).

Ayrıca *"ℹ️ Veriler yerel dosyada (Supabase gerekmez)"* satırı 379 px ile bütçeyi
aşıyordu → iki kısa satıra bölündü (*"ℹ️ Supabase gerekmez" + "/karne ile
istediğin an al"*); "yerel dosya" bilgisi başlıkta zaten var.

## 5. Nerede görünür (değişmedi)

| Yer | Ne zaman | İçerik |
|---|---|---|
| **Cuma gün sonu özeti** | Cuma 18:45 kapanış özetinin altına eklenir (`bot/app.py` `_haftalik_karne_ekle`) | Tam karne (yukarıdaki blok dahil) |
| Gün sonu analizi (20:00) | 18:45 özeti gönderilemezse yedek yol | Aynı tam karne |
| `/karne`, `/karnem` | Her an, istenen gün sayısıyla | Aynı tam karne |
| Public/grup | Haftalık kısa sürüm (`karne_kisa_metni`) | Değişmedi (teknik döküm yok) |

Günlük (her gün) özet bu bloğu **içermez**; haftalık karne Cuma'ya aittir.

## 6. Testler

`test_karne_masraf.py` (12 test): formül (elle hesap eşitliği), stopta masrafın
kaybı büyütmesi, masraf sıfırken net=brüt, nötr işareti, bekleyen sinyalde `None`,
komisyonun modül sabitinden okunması, haftalık kovalar + ortanca, tek haftada
ortanca üretilmemesi, metinde masraf bölümü, eski satırların üretilmemesi, güven
eşikleri, **her satırın 283 px bütçesine sığması**.

`test_karne.py` iki assert güncellendi (gerekçe: performans bloğu sadeleşti —
`"Kırılım: 2"` → `"2 sinyal · yukarı 2 · aşağı 0"`).

## 7. Bilinçli olarak yapılmayanlar

- **`analytics/backtest.py`** kolonları: rapor zaten `n=` etiketli ve ayrı bir
  yüzey; masraf kolonlarını oraya eklemek bu turun kapsamı dışında bırakıldı.
- **Kart/bildirim metinleri** (`kart_metin`, alarm metni): dokunulmadı.
- **`karne_kisa_metni`** (public): bilinçli olarak yalın kaldı.
- Masraf **günlük özete** eklenmedi; haftalık karne yeterli sıklık.
