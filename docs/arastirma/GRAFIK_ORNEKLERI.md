# Alarm grafiği — 3 gerçek örnek

Aşağıdaki üç grafik **gerçek alarmlardan** alındı (aynı veri: 352 seri, `4h`).
Üçü de aynı format: göreceğin şey her seferinde aynı.

## Grafikte ne var

| Görsel | Anlamı |
|---|---|
| **Dikey kesikli çizgi** | alarmın çıktığı bar — "ALARM →" |
| **Kırmızı/yeşil kutu (üstte)** | alarmın **iddia ettiği yön** |
| **Mavi gölgeli koni** | aynı sembolde geçmiş **200 alarmdan** sonra tipik olarak ne oldu |
| **Mavi / mor ince çizgi** | tipik yukarı ve aşağı uzanımın **medyanı** |
| **Yeşil noktalı çizgiler** | bu alarmdan sonra **gerçekten** olan (12 bar) |
| **Turuncu noktalı çizgiler** | aynı şeyin 40 bar versiyonu |
| **Sol üstteki kutu** | alarm fiyatı, ATR, sonraki 12 bar gerçekleşen, ve **alarm yönünde lehte mi aleyhte mi** |

**Grafik yorum yapmıyor.** İki şeyi yan yana koyuyor: *"tipik olarak ne olur"* ve
*"bu sefer ne oldu"*. Karşılaştırmayı sen yapıyorsun.

---

## 1 · Tipik bir alarm — XU100, 4h

![Tipik XU100](grafik_tipik_xu100.png)

Alarm `KIRILIM_ADAYI` demiş, **yukarı**. Sonraki 12 barda yukarı +0,2 ATR,
aşağı −3,5 ATR. Yani **alarmın dediği yönün tersi** oldu.

Ama dikkat: mavi koni de aşağı doğru geniş. Bu, "tipik olarak bu sembolde alarm
sonrası aşağı oynaklık daha büyük" demek. Grafik bunu saklamıyor.

---

## 2 · Alarmın haklı çıktığı örnek — KONTR, 4h

![İyi KONTR](grafik_iyi_kontr.png)

Alarm `KIRILIM_TEYITLI`, yön **aşağı**. Sonraki 12 barda aşağı −7,0 ATR, yukarı
sadece +1,9. **Alarm yönünde lehte** — 7 ATR'lik bir düşüş.

Bu örnek önemli: demek ki alarm bazen gerçekten önden konuşuyor. Ama bu **tek
örnek**; aşağıdaki üçüncü grafik tersini gösteriyor. İkisini birlikte görmek
şart, yoksa insan "alarm çalışıyor" ya da "alarm çalışmıyor" diye yanlış
geneller.

---

## 3 · Alarmın yanıldığı örnek — EREGL, 4h

![Kötü EREGL](grafik_kotu_eregl.png)

Alarm `FORMASYON_TAMAMLANDI`, yön **yukarı**. Sonraki 12 barda yukarı +0,6,
aşağı −3,4 ATR. **Alarm yönünde aleyhte.** Fiyat 24,30'dan 22,80'e indi.

---

## Bu üç örnek ne anlatıyor

Üç alarm, üç farklı sonuç: **biri haklı (7 ATR), biri yanlış (−3,4 ATR), biri
belirsiz (0,2 vs 3,5)**. Tek tek bakınca hiçbiri bir şey kanıtlamıyor.

Kanıt 177.723 alarmın tamamında: 12 barda alarm yönünde ≥1 ATR görme oranı
**%65,8**, hiç alarm olmayan barlarda **%63,7**. Fark **+2,1 puan**.

Yani **alarm doğru yönde biraz daha sık** hareket görüyor — ama "tahmin" demek
için çok az. Grafikler bunu tek tek göstermiyor; gösterdiği şey **dağılımın ne
kadar geniş olduğu**. Üç örnekte de görüyorsun: aynı formatta üç alarm, üç
tamamen farklı sonuç.

---

## Kendi grafiğini üretmek

```bash
python -m research.grafik_alarm --sembol KONTR --tf 4h --bar 61 \
    --etiket "KIRILIM_TEYITLI" --yon -1 --cikti var/grafik/kontr.png
```

`--yon`: `1` yukarı, `-1` aşağı, `0` yönsüz. Bar indeksini replay çıktısından
(`var/replay/da_pol/tetikler.jsonl`) alabilirsin — her satırda `symbol`,
`timeframe`, `bar_index` var.

Kod: [`research/grafik_alarm.py`](../../research/grafik_alarm.py). Canlı çizim
hattı (`grafik/render.py`) **değişmedi**; bu ayrı bir araç.
