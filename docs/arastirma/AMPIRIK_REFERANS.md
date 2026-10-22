# Ampirik Referans — ölçümü canlı metne bağlayan katman

> **Durum:** Yürürlükte · **Tarih:** 2026-10-21 · **Kod:** `ampirik_referans.py`
> **Test:** `test_ampirik_referans.py` (29 kontrol)
> **Kaynak tablolar:** [ARASTIRMA_BULGULARI.md](ARASTIRMA_BULGULARI.md) ·
> [FORMASYON_SONUCLARI.md](FORMASYON_SONUCLARI.md)

## 1. Neden var

Alarm kartı ve `/tara` çıktısı yalnız **"şu an ne oldu"** bilgisini taşıyordu:
kırılan seviye, kapanış, kalite, temas sayısı. Oysa `docs/arastirma/` altında
**aynı kurulumun arşivde nasıl sonuçlandığı** ölçülü durumda — bu sayılar
kartta hiç görünmüyordu (metin "sade" kalıyordu), yalnız 2621 satırlık rapor
dosyalarında duruyordu.

Bu katman ölçümü **olayın kendi özelliklerine koşullu** tek satıra çevirir:
her alarmda tekrarlanan sabit bir dipnot değil, o an ayırt edici olan sayı.

```
▲ SISE 4s YUKARI TEYİTLİ
Yükselen Üçgen — kapanışla
· kapanış 39,60 (seviye 39,26)
· kalite 81/100 — güç 100
retest yok — MTF 1g onaylı
katılım 4s destekliyor
◇ rol uyumlu %80 n15724      ← yeni: bu kurulumun arşivdeki sonucu
› /tara SISE
• yatırım tavsiyesi değildir
```

## 2. Sözleşme

1. **Uydurma yok.** Her sayı rapor tablosundan elle alınmıştır; kaynağı
   `KAYNAK_TABLOLARI` sözlüğünde satır adıyla yazılıdır. Tabloda olmayan kesit
   (ör. 1h FVG zone referansı, 15m TF) için satır **üretilmez**.
2. **`n` satırda görünür.** Ölçüm tabanı olmadan oran basılmaz.
3. **Betimleme, tavsiye değil.** Çıktı "beklenen getiri" değil "arşivde bu
   kurulumda şu davranış gözlendi" cümlesidir. `al/sat/hedef/stop/kâr/zarar/
   tavsiye/garanti` kelimeleri testle yasaklanmıştır.
4. **Tek kaynak.** Sayı yalnız `ampirik_referans.py`'de durur; biçimleyici
   (kart, `/tara`) sayı hesaplamaz, gelen satırı basar.
5. **Sessizlik yeğdir.** Koşul sağlanmıyorsa satır dönmez. Kartı doldurmak için
   ilgisiz ölçüm basılmaz.
6. **Satır bütçesi.** Her satır ≤ 283 px (`telegram_measure`); testte
   `_kart_esik_px()` ile doğrulanır. Uzun ifade kısaltılır, satır bölünmez
   (bölünme girintili devam satırı üretir ve kart düzenini bozar).
7. **Varsayılan kapalı.** `domain_bolumleri(olcum=True)` verilmedikçe hiçbir
   yüzey değişmez; mevcut çağıranların metni bayt bayt aynı kalır.

## 3. Hangi ölçüm, hangi koşulda, hangi satır

Öncelik sırası `ONCELIK` sözlüğünde; kart en çok **2** satır basar.

| # | Ölçüm | Koşul (canlı veri) | Kart satırı | n | Kaynak |
|---|---|---|---|---|---|
| 0 | MS devamı | alarm TF'de teyitli+güncel BOS/CHoCH | `◇ BOS ↓dış devam %67 n1736` | kova n | Soru 5 |
| 1 | Yön–rol uyumu | kırılım yönü + en yakın PH/PL | `◇ rol uyumlu %80 n15724` | 15724 / 13573 | FRM-20 |
| 2 | Zone yüksekliği | ATR + alarm TF zone geometrisi | `◇ yüksek bölge kalıcı %71 n162` | kova n | Soru 4 |
| 3 | RVOL çeyreği | rvol alt/üst uçta (≈Q1 / ≈Q4) | `◇ yüksek RVOL %61 n11928` | kova n | Hacim tablosu |
| 4 | Zone içi/dışı | fiyat herhangi TF'de OB/FVG içinde | `◇ zone içi %76 tamam n11905` | 11905 / 20232 | FRM-19 |
| 5 | Retest oranı | yalnız `retest_seen=False` | `◇ retest oranı %35 n28624` | 28624 | FRM-12 |
| 6 | Taban | her teyitli olay (yedek satır) | `◇ medyan 1,2 ATR n24618` | 24618 | FRM-16 |

### Bilinçli yaklaşımlar (gizlenmiyor)

- **RVOL çeyreği yaklaşıktır.** Arşivde çeyrekler gözlem dağılımından kesildi;
  canlı `rvol` değeri çeyrek **ortalamasına en yakın** kovaya atanır. Kesin
  sınır canlı tarafta yeniden üretilemediği için `≈` yaklaşımı kullanılır ve
  yalnız ayrışan uçlar (Q1/Q4) basılır.
- **Zone yüksekliği kova tablosu 1d FVG ölçümüdür** (n=6285). Satır "tüm
  ailelerde geçerli" iddiası taşımaz; orta kovalarda nitelik etiketi yerine
  ölçülen yükseklik yazılır (`◇ bölge 0,8 ATR %65 n1989`).
- **Retest gördüyse satır basılmaz.** FRM-13 sonucu retest **derinliğine**
  bağlıdır; derinlik kartta ölçülmediği için sabit oran yanıltıcı olurdu.
- **MS tablosunda yön yoksa** kapsam×tip satırına düşülür (n daha büyük).

## 4. Raporlardan farkı

| | `docs/arastirma/*.md` | karttaki `◇` satırı |
|---|---|---|
| Amaç | soruyu kanıtlamak | olayı bağlama oturtmak |
| Kapsam | 704 seri, tüm kesitler | tek olay, tek kesit |
| Güvenlik | GA, çoklu test notları | n + "arşiv" ifadesi |
| Karar | kural önerisi | kural değil, referans |

Satır bir **iddia** değil **bağlam**dır: "%80 tamamlandı" cümlesi bu olayın
%80 kazanacağı anlamına gelmez; aynı tanımla ölçülen 15.724 olayın %79,7'sinin
tamamlandığını söyler. Maliyet, kayma, pozisyon ve çıkış kuralı yoktur.

## 5. Yeni bir ölçüm nasıl eklenir

1. Sayıyı `docs/arastirma/` tablosundan al; satır adını `KAYNAK_TABLOLARI`'na yaz.
2. `ampirik_referans.py` içinde tabloyu ekle (n + oran birlikte).
3. `_<ad>_satiri()` fonksiyonunu yaz: koşul yoksa `None` döndür.
4. `olcum_satirlari()` aday listesine ve `ONCELIK`'e ekle.
5. `test_ampirik_referans.py`'ye üç test ekle: **değer**, **koşulsuzluk**,
   **genişlik**. `n < 50` olan kesitler için satır yazılmaz.
6. Bu tabloya satır ekle.

## 6. Sınırlar

- Tek rejim penceresi (intraday 2025-05 → 2026-10); rejim değişiminde özellikle
  yön asimetrisi dönebilir. Satırlar bu yüzden "arşivde" ifadesiyle yazılır.
- Motor parametreleri değiştirilmedi (canlı "Dengeli" profili).
- Ölçümler 12 bar / ATR penceresindedir; 12 adet 1h bar ile 12 adet 1d bar aynı
  takvim süresi değildir.
- Kart satırı bir **olasılık** sunmaz: kalibrasyon, GA ve çoklu test düzeltmesi
  bu katmanın kapsamı dışındadır (raporlarda durur).
