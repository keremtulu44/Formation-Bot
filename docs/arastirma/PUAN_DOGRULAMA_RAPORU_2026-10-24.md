# Puan doğrulama raporu — HÜKÜM

Tarih: 2026-10-24
Ön kayıt: `docs/arastirma/PUAN_DOGRULAMA_ON_KAYIT.md`
Ön kayıt SHA-256: `345c1260564b85f2bcf8bdf0b0be2100e6b8eb0c218f2e3696be6e17a7fc8b5f`
(yazıldığı anda, herhangi bir ölçüm çalıştırılmadan önce alındı)

## 1. Hüküm

**Mevcut formasyon kalitesi puanıyla öngörücü bir puanlama kurulamaz.**
Sebep, ağırlıkların yanlış olması değil: **kırılım olayının kendisi**, aynı yönde
rastgele bir girişten yalnızca **+1,5 puan** iyi (ön kayıtta bar +3,0 idi).
Olay rastgelelikten zar zor ayrılıyorsa, o olayı sıralayacak hiçbir puan
öngörücü olamaz.

Ölçülen tek gerçek ayrım formasyonun şeklinde değil, **piyasa koşulunda**:
kırılımın yönü endeksin 20 barlık eğimiyle aynıysa devam oranı %38,1,
tersse %33,0. Bu bir puan değil, bir süzgeç — ve ön kayıt kuralları gereği
(aşağıya bak) **doğrulanmış sayılmadı**, ikincil bulgu olarak raporlanıyor.

Bu süzgecin bile formasyona bağlı olmadığı ölçüldü: hiç analiz edilmemiş
**77 sembolde** uyumlu kırılım %37,5, aynı yönde **rastgele** (trend takip eden)
giriş %36,4. Yani formasyon, naif trend takibine yalnızca **+1,0 puan** ekliyor;
kısa tarafta eksiye düşüyor (−0,9).

## 2. Ne ölçüldü

- **Veri:** 177 sembol × 4 zaman dilimi (1s, 2s, 4s, 1g), 7 Mayıs 2025 – 19 Ekim 2026.
- **Replay:** 16.818 kırılım olayı, 12,1 dakika, **hata yok**.
  Etiket penceresi tamamlanan gözlem: 16.417.
- **Her gözlemde:** kırılım anında **dondurulmuş** kalite (sızıntısız), 17 bileşen,
  baraj ızgarası (0,5–4 ATR × lehte/ters), hacim oranı, endeks eğimi, göreli güç,
  retest bayrağı, bant genişliği, gecikme.
- **Etiket:** lehte 2,0 ATR / ters 1,0 ATR / 24 bar (ana); 7 varyantla duyarlılık.
- **Bölmeler:** ayrık sembol (S) ve uzak dönem + 35 gün boşluk (Z).
  Yan yana blok (Y) yalnızca tuzak göstergesi olarak hesaplandı, karar için kullanılmadı.

## 3. Ön kayıtlı sonuçlar

| # | Hipotez | Ölçüm | Bar | Sonuç |
|---|---|---|---|---|
| H0 | Formasyon kırılımı rastgele girişten iyi | **+1,5 puan** (GA +0,5…+2,6) | ≥ +3,0 | **KALDI** |
| H1 | Endeks uyumu geçidi | uyumlu %38,1 / ters %33,0 | ≥ +3,0, S+Z | Çalıştırılmadı (H0 durdurma kuralı) |
| H2 | Likidite katkısı | üst %36,8 / alt %35,1 (+1,7) | ≥ +3,0 | **KALDI** |
| H3 | Sert geçit, yumuşak eşikten iyi | **−0,7 puan** (S: −0,6 · Z: −0,8) | ≥ +3,0 | **KALDI** |
| H4 | Hücre taban oranları kalibre | Brier 0,2321 vs sabit 0,2307 | daha iyi olmalı | **KALDI** |

H0'ın ayrıntısı (ana etiket, yön eşleştirmeli, piyasa sürüklenmesi arındırılmış):

| kesim | kırılım | rastgele giriş | fark |
|---|---|---|---|
| 1s | %37,6 | %36,1 | +1,5 |
| 2s | %38,0 | %36,9 | +1,1 |
| 4s | %38,1 | %37,0 | +1,3 |
| 1g | %34,6 | %36,2 | +1,3 |
| long | %39,9 | %37,4 | +2,5 |
| short | %35,4 | %35,4 | +0,0 |

7 etiket varyantının hepsinde fark pozitif ama **+0,4 ile +2,3** arasında.
100 sembollük ilk turda da aynı: +1,9 (GA +0,5…+3,2). İki bağımsız evrende de
barın altında — sonuç örneklem şansı değil.

**İcra varsayımı sağlamlığı:** sinyal kapanışta gelir, giriş ertesi barın
açılışında yapılır varsayımıyla test tekrarlandı: fark **+1,8** (GA +0,8…+2,9),
yine barın altında. Ölçüm giriş fiyatı seçimine duyarlı değil.

H4 ayrıntısı: 18 hücrenin 13'ünde sapma ±2 puandan az (iyi kalibre), ama uç
dilimlerde dağılıyor (<%30 tahmin → %38,6 gözlenen; >%50 tahmin → %18,6) ve
Brier sabit tahminciden **kötü**. Yani hücre oranlarını "olasılık" diye
kartta satmak da savunulamaz.

## 4. Neden hiçbir puan bunu kurtaramaz

Daha önce 100 sembolde ölçülenler bunu tamamlıyor:

- Kalite → sonuç AUC **0,492** [0,478–0,505]; **36 etiket varyantının hiçbirinde**
  0,503'ü geçmedi.
- Kova tablosu düz: %34,1 / %37,6 / %36,4 / %36,9 / %35,3.
- Bileşenlerin hiçbiri ayırmıyor: geometri 0,488, eğim 0,486, temas 0,500,
  güç 0,513 (en iyisi, yine de zayıf).
- Çift sayım: geometri–eğim korelasyonu 0,98; kalite–geometri 0,73.
  Yani "kalite" fiilen geometri puanının kopyası.

## 5. Kartın bugünkü iddiası

Kartta `◇ %76'sı devam etti` yazıyor. Ölçülen taban **%36,1**; 80–84 kovası
%36,9. Fark **~39 puan**. 76 sayısı fiyatın devamından değil, motorun kendi
"tamamlandı" sayacından geliyor (%84) ve o sayaç fiyatın hedefe gittiğini
ölçmüyor.

## 6. Doğrulanmış sayılmayan ama ölçülmüş olan (ürün kararı için)

Endeks uyumu, kırılımlar **içinde** tutarlı biçimde ayrışıyor:

| TF | uyumlu | uyumsuz | fark |
|---|---|---|---|
| 1s | %37,6 | %32,8 | +4,8 |
| 2s | %38,4 | %33,0 | +5,4 |
| 4s | %40,2 | %33,9 | +6,3 |
| 1g | %34,3 | %31,7 | +2,6 |

Dört hücreli tablo (uyum × likidite): **%31,4 – %38,5**.
Bu, puan değil koşul bilgisidir ve ön kayıt kuralları gereği **doğrulanmış
sayılmadı** (H0 düştüğü için H1 karar amaçlı çalıştırılmadı). Yeniden
doğrulamak için ayrı bir ön kayıt ve yeni veri gerekir.

### 6b. Sembol ayrık doğrulama (77 dokunulmamış sembol)

İlk 100 sembollük analizde hiç kullanılmayan **77 sembol** ayrı bir dilim olarak
ölçüldü (5.980 gözlem). Sonuç, ikincil bulguyu bağımsız örneklemde tekrarlıyor:

| kesim | uyumlu | uyumsuz | fark |
|---|---|---|---|
| 77 sembol · tümü | %37,5 | %32,5 | +5,0 |
| 1s | %36,5 | %32,0 | +4,6 |
| 2s | %37,8 | %33,8 | +4,0 |
| 4s | %41,3 | %33,2 | +8,1 |
| 1g | %34,7 | %29,1 | +5,6 |

7 etiket varyantının hepsinde +4,3 ile +5,9 arası. S doğrulama +5,7, Z doğrulama +2,9.

**Ama aynı dilimde rastgele trend takibiyle kıyas:** uyumlu kırılım %37,5,
aynı yönde rastgele giriş %36,4 → **+1,0 puan** (long +2,7 · short −0,9).
Yani süzgecin kazancı formasyondan değil, trendin kendisinden geliyor.

### 6c. En iyi alt küme bile barı geçmiyor

Kırılımın seviyeye uzaklığına göre bölündü (taze = seviyeye yakın). Rastgele
uyumlu taban %37,0:

| seviyeye mesafe | n | kırılım | fark | uyumlu alt küme |
|---|---|---|---|---|
| 0–0,3 ATR | 3.140 | %35,5 | −1,4 | %39,9 (n=1.582) |
| 0,3–0,5 ATR | 1.492 | %36,1 | −0,8 | %36,9 |
| 0,5–1 ATR | 2.967 | %34,3 | −2,7 | %36,2 |
| 1–2 ATR | 3.397 | %36,8 | −0,1 | %38,2 |
| 2+ ATR | 4.758 | %36,7 | −0,3 | %38,3 |

En iyi alt küme (taze + uyumlu) rastgeleyi **+2,9 puan** geçiyor — yine +3,0
barının altında, üstelik bu alt küme sonradan seçildiği için şans payı yüksek.

## 7. Öneriler

1. **Karttan yüzdeyi kaldır.** "%76 devam etti" bugün yanlış; "%36" demek de
   yanıltıcı olur, çünkü puanla ilgisi yok.
2. **Kalite sayısını "öngörü" diye sunmayı bırak.** Yapıyı tarif eden bir ölçü
   olarak kalabilir (formasyon çizilebiliyor mu), ama seçim kriteri olamaz.
3. **Eşikleri sadeleştir.** Dört TF eşiği ampirik olarak farksız; tek eşik
   yeterli. Bu bir kalite ayarı değil, yalnızca bildirim hacmi düğmesi.
4. **Koşul bilgisini ayrı tut.** Endeks uyumu +5 puan civarı bir ayrım gösteriyor;
   ürüne alınacaksa ayrı ön kayıtla, yeni veride doğrulanmalı.
5. **Puanı yeniden tasarlamaya kalkışma.** Ölçüm şunu söylüyor: kırılım olayının
   kendisi rastgele girişten +1,5 puan; bu tabanda iyi bir sıralama üretmek
   mümkün değil. Emek, olay seçimine (hangi kırılım, ne zaman) gitmeli.

## 8. Sınırlar

- 18 ay, tek piyasa rejimi (güçlü yukarı eğilim), tek ülke.
- Haber/gündem verisi yok; takvim tabanlı rejim hipotezleri ölçülemedi.
- "Kartta etiket göstermek faydalı mı" sorusu replay ile ölçülemez.
- H1/H2 ikincil sonuçları yeni veride sınanmadan ürüne alınmamalı.

## 9. Tekrar üretim

```
python scripts/puan_replay.py --sembol-sayisi 177 --cikti var/replay/gozlemler177.csv
python scripts/kontrol_deneyi.py --gozlem var/replay/gozlemler177.csv
python scripts/kalibrasyon.py   --girdi var/replay/gozlemler177.csv
python scripts/gecit_kiyas.py   --girdi var/replay/gozlemler177.csv
python scripts/puan_analiz.py   --girdi var/replay/gozlemler177.csv
python scripts/puan_tarama.py   --girdi var/replay/gozlemler177.csv
```

Hiçbiri üretim koduna, `bot_data/` dizinine veya Telegram'a dokunmaz.
