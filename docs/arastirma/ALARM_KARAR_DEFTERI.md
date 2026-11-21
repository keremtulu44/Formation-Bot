# Alarm karar defteri — 20 Kasım 2026

**Öncelik:** 4 saatlikte önceki dibin hacimli geri alımını yeni veride, bildirim göndermeden izlemek. Alarmın sorusu “12 mum sonra daha yukarıda mı?” değil, “önce yukarı tepki verme olasılığı benzer geri alımlardan daha mı yüksek?” Canlı bot değiştirilmedi.

## İlk beş fikrin kararı

| Fikir | Karar ve dayanak |
|---|---|
| Dikey → yatay Stabil, ilk fitil teması | Tek başına bildirim yok. Önce yukarı 1 ATR: %46,7; genel yatay temas %46,5. Görsel çıkış tanımı ayrıca doğrulanmalı. |
| Sabit Stabil altındaki dipten temiz geri alış | Sessiz izleme adayı. Yalnız yeşil oranı ayırmadı; yolun ≥%80’i belirgin gövdeli yeşilse 19 olayın 13’ü önce yukarı. Hepsi 3–5 mum; dört başarılı olay aynı tarihte. |
| Kırılım + Stabil üstü + önde boş 1 ATR | Ek puan yok. Aynı teyit ve destek şartıyla açık %50,1, yakın engel %50,9. |
| Yukarı eğim + BOS + üst hacim >0,5× | Ek puan yok. %49,5; yalnız eğim %49,2. |
| 1s hacim çok düşük, üst hacimler korunuyor | Kartta bağlam. Aynı saat/hisse karşılaştırmasında gövde 0,10 / 0,32 ATR; sonraki dört mumda dip 0,68 / 0,73 ATR. Küçük gövde gelecekte küçük risk demek değil. |

[Tanımlar, tarihli örnekler ve önceki beş ölçüm](sonuclar/bes_alarm_pilotu/RAPOR.md).

## Yeni aday: 4s önceki dip geri alımı + aynı saate göre hacim

**Kapanışta bilinen kural:** Mum, önceki 20 tamamlanmış mumun en düşük fiyatının altını görüp bu seviyenin üstünde ve kendi fiyat aralığının üst çeyreğinde kapanır. Hacmi, aynı hissede aynı periyodun **aynı başlangıç ve bitiş saatli** önceki 20 mumunun medyanına bölünür (günlükte önceki 20 günlük mum). Böylece öğlen mumu açılışla kıyaslanmaz. RVOL ≥1,5× yüksek; <1× düşük; arası ayrı. Bu kuralda Stabil veya yeşil gövde şartı yoktur.

**174 BIST hissesi**, 1s/2s/4s/günlük native mumlar. Kapanıştan sonraki 12 mumda önce +1 mi −1 Wilder ATR(14) mi görüldü? Aynı mumda çift isabet ve süre sonu paydada. Aynı hisse/periyotta hacim grubundan bağımsız 12 mum bekleme; eksik ileri ufuk ve 19 Kasım 2026 dışarıda. 11.755 ölçüm; hisse ve periyotlar arasında örtüşme var.

| Önce +1 ATR | Yüksek hacim | Düşük hacim |
|---|---:|---:|
| 1 saat | 844/1.856 (%45,5) | 879/2.023 (%43,5) |
| 2 saat | 423/860 (%49,2) | 575/1.238 (%46,4) |
| **4 saat** | **399/776 (%51,4)** | **543/1.188 (%45,7)** |
| Günlük | 143/283 (%50,5) | 225/402 (%56,0) |

4s’te orta hacim %47,7 (379/794). Yüksek–düşük farkı 1 Temmuz 2026 öncesi **%50,5 / %49,2**, sonrası **%53,6 / %35,3**: farkın büyük kısmı son dönemde zayıf hacim grubunun bozulmasından geliyor. Aynı 4s kapanış anında iki gruptan da hisse bulunan 197 zaman diliminde, her dilimi küçük grubun sayısıyla ağırlıklandırınca %55,7 / %49,9 (toplam ağırlık 334). Tarih etkisine karşı ek kontrol; farklı hisseler eşdeğer değil. En kalabalık tek günde 43 yüksek hacimli sinyal var. 4s sonucu periyotları gördükten sonra seçildi; bağımsız ileri test değil.

**Tepki ≠ trend:** 4s yüksek hacimde 399 lehte, 352 aleyhte, 13 belirsiz, 12 süresi dolmuş. 12. kapanışın medyanı **−0,30 ATR**. Örneğin **ASTOR, 6 Kasım 2026 13:00**: eski dip 148,30; fitil 145,60; kapanış 154,20; hacim 1,54×. İkinci mumda +1 ATR önce geldi. **THYAO, 23 Ekim 2026 17:00**: 251,50 altına 247,80 fitil; kapanış 257,50, hacim 2,37×; yedinci mumda önce **−1 ATR**. Yüksek hacmi genel alım puanı yapmak sonuçlarla uyumsuz.

**Önerilen kart metni:** “4s: Önceki 20 mumun dibi geri alındı. Aynı saate göre hacim 1,54×. Kısa tepki adayı.” İlk kullanım dışarıya bildirim değil: kuralları sabitle, ilk yeni 100 yüksek hacimli olay ile aynı dönemin düşük hacimli geri alımlarını biriktir; sonuçları hem sinyal hem ayrı işlem günü bazında karşılaştır. Bu öneri izleme altyapısının kurulduğu anlamına gelmez.

[Yeni olaylar, tarih ve fiyatlar](sonuclar/dip_geri_alim_hacmi/OLAYLAR.csv.gz) · [dönem/periyot/hacim kırılımı](sonuclar/dip_geri_alim_hacmi/OZET.csv). Yeniden üretim: `python -m research.dip_geri_alim_hacmi`.

## Kapsam kontrolü

[Hareket haritası 1](sonuclar/hareket_kapsam/RAPOR.md): aynı 985 kartta hacim sırası kart hedefini 283’ten 295’e taşıdı, ayrı hareketlerde erken yakalama ise 116’dan 114’e indi. Genel hacim filtresi açılmadı.
