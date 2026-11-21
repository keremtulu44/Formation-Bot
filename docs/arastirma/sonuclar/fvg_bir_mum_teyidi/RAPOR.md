# Hızlı ilk temasta bir mum beklemek: 17:00 izinin içi

**Sonuç:** ≥2 ATR genişliğinde, ilk 1–3 mumda test edilen FVG’de sırf bir sonraki kapanış yönü teyit etti diye daha iyi bir anlık alarm elde etmedik. En ilginç bulgu **zamanlama**: native 4 saatlikte 17:00 etiketli olayların bir kısmında hareket sonraki mumun içinde gelişmiyor; **açılışı zaten hedefin ötesinde**.

## 17:00 mumundan sonra ne oldu?

Ölçü: ilk temas kapanışına eşit uzaklıktaki iki bariyerden (±1 temas ATR’si) yalnız lehte olanın bir sonraki mumda görülmesi. İkisine de değenler bu sayıya girmez. Sonraki mumun açılışında hedef geçilmişse bunu sonraki kapanışta fırsat gibi sunmuyoruz.

| 4 saatlik temas mumu (İstanbul) | Olay | İlk sonraki mumda lehte | Aynı saat referansında lehte |
|---|---:|---:|---:|
| 09:00 | 290 | 67 (%23,1) | 32 (%11,0) |
| 13:00 | 102 | 15 (%14,7) | 12 (%11,8) |
| **17:00** | **401** | **210 (%52,4)** | **93 (%23,2)** |

401 olay 133 sembol ve 238 temas tarihine yayılıyor. **210’un 145’i** (%69,0) bir sonraki mumun açılışında zaten lehte eşiğe ulaşmış. Diğer 191 olayı kayıp saymıyoruz: 51’inde yalnız ters eşik, 52’sinde iki eşik, 88’inde hiçbiri görülmedi. 17:00 bulgusu saat kırılımına baktıktan sonra fark edildi: bağımsız doğrulanmış bir saat kuralı değildir. Referans her olay için aynı sembol, periyot, haftanın günü ve saatindeki en yakın eski mumdur; olay tarihinden en az 13 bar geride, aynı aday kümesinin dışında. Yön olaydan taşınır; referansın kendi ATR’si kullanılır. Bu, volatilite/haber/likidite eşleşmesi değildir; aynı kontrol tekrar kullanılabilir. Mum saatleri TradingView native arşivinin etiketleridir, tam temas saati değildir.

**Örnek — AKBNK, 19 Mart 2025:** 4 saatlik 17:00 mumunda düşüş FVG’sinin ilk temas kapanışı 65,95; ATR 1,394, lehte eşik yaklaşık 64,56. **20 Mart 09:00 mumunun açılışı 64,35**, kapanışı 63,35. Kapanıştan kapanışa güçlü görünür; sabah uyarısının yakalayabileceği yeni bir ilk 1 ATR hareketi değildir.

## Teyit kuralı gerçekten daha iyi seçiyor mu?

Aynı [erken temas kohortu](../fvg_temas_davranisi/RAPOR.md): 175 sembol, 1.453 temas, 2s/4s/günlük. ≥2 ATR, ilk 1–3 mum, temas mumunda tam dolum yok, 12 ileri bar mevcut. Yeni dönem yok: arşiv 19 Kasım 2026'da bitiyor. **Bu bir geçmiş veri deneyi, yeni tarihler üzerinde ileri test değil.**

Bir mum bekle; ilk mumda fiyat eski lehte/ters bariyerlerden birine değdiyse veya bant tamamen dolduysa yeni kart verme. Kalanlarda **yükseliş bölgesinde temas kapanışının üzerinde**, düşüş bölgesinde altında kapanış = teyit. Bu, mum gövdesinin rengi değildir. Teyit anında iki bariyer de yeni kapanışa taşınır; ATR sabit kalır. Hedefi görmek için verilen süre uzamaz: ilk kola 12, gecikmiş kola kalan 11 mum. Aynı mumda iki eşik = belirsiz, kâr değil.

| Karar | Kart | Lehte önce | Aleyhte önce | Aynı mum / süre sonu |
|---|---:|---:|---:|---:|
| Temas kapanışında | 1.453 | 787 (%54,2) | 550 | 102 / 14 |
| Bekle, hâlâ uygun olan herkese | 804 | 427 (%53,1) | 331 | 34 / 12 |
| Bekle, yalnız yönü teyit edenlere | 265 | 136 (%51,3) | 121 | 4 / 4 |
| Bekle, yönü teyit etmeyenler (kontrol) | 539 | 291 (%54,0) | 210 | 30 / 8 |

Beklerken **382 lehte**, **198 aleyhte**, **62 iki taraflı** ilk hareket zaten gerçekleşti; bariyer görülmeyen 7 bant doldu. Aynı 265 teyitli olayı bugünden geriye bakıp **eski kapanıştan** saysaydık 164/265 (%61,9) bulacaktık. Teyit bilindiğinde o fiyat artık geçmişti: doğru ölçü 136/265. Dönemler de aynı hükmü vermiyor: 1 Temmuz 2026 öncesi teyitli %47,5 (95/200), sonrası %63,1 (41/65). Tek başına zorunlu teyit için kanıt değil.

**Örnek — THYAO, 19 Şubat 2026:** 4s düşüş temasının 09:00 kapanışı 319,50. 13:00 teyit kapanışı 314,00. Eski lehte eşik 312,65 aynı gün 17:00 mumunda görüldü. Teyit kapanışından ise yeni hedef 307,15 oldu; önce ters eşik (320,85) 23 Şubat 09:00 mumunda görüldü. Aynı bölge, farklı bildirim zamanı, farklı sonuç.

**Karar:** Canlı filtresi ekleme. Bir sonraki bağımsız kontrolde iki sayıyı ayrı kaydet: 17:00 etiketli ilk temasın *ertesi seans açılışındaki farkı* ve *açılıştan sonraki ilave hareket*. Arşivde hedef görülmesi, bildirimin teslim edildiği veya o fiyattan işlem yapılabileceği anlamına gelmez.

[Tarihli olaylar](OLAYLAR.csv.gz) · [Politikalar ve alt gruplar](OZET.csv) · [Saat eşleştirmeleri](SAAT_KONTROL.csv). Tekrar: `python -m research.fvg_bir_mum_teyidi --cikti var/fvg_bir_mum_teyidi`.
