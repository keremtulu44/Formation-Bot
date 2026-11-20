# Alarm tetiklendi — ne okumalıyım?

Bu dosya tek soruya cevap veriyor: **alarm geldiğinde grafiğe bakıp ne anlamalıyım?**

Cevap 4 satır. Grafikte sol üstteki mavi panel her zaman bu 4 satırı yazıyor:

| satır | soru | örnek |
|---|---|---|
| **1) Büyüklük** | 12 barda tipik ne kadar oynar? | "3,4 ATR (%80: 2,7 – 4,6)" |
| **2) Yön** | alarmın dediği yön belli mi? | "lehte 1,5 / aleyhte 1,7 → **yön zayıf**" |
| **3) Şu an** | oynaklık bu sembolde normal mi? | "sakin (%36 dilim)" |
| **4) Bu sefer** | gerçekleşen, tipikten saptı mı? | "8,9 ATR → **tipikten BÜYÜK**" |

**En önemli satır 2.** Çünkü ölçüm şunu söylüyor: alarmların çoğunda
*lehte ≈ aleyhte*. Yani **alarm yön söylemiyor** — sadece "oynaklık artıyor"
diyor. Aşağıdaki üç örnekte bu oran sırasıyla **0,8 / 1,1 / 0,7** — üçü de
"yön zayıf".

Bunun anlamı: **grafiği oynaklık bekleyerek oku, yön bekleyerek okuma.**

---

## Örnek 1 — "tipik" alarm (XU100 4h)

![Tipik XU100](grafik_tipik_xu100.png)

Panel diyor: tipik **4,2 ATR** (%80: 2,9–6,0) · lehte 1,9 / aleyhte 1,7 → **yön
zayıf** · oynaklık **sakin** · bu sefer 3,7 ATR → **≈ tipik**.

Grafikte: mavi koni hem yukarı hem aşağı açılıyor (o yüzden "koni", ok değil).
Alarm "yukarı" dedi ama 12 barda yukarı **+0,2** ATR, aşağı **−3,5** ATR oldu.

**Ne anlamalı:** Alarm isabetli çıkmadı, ama **beklenen büyüklük** tuttu (3,7 ≈
4,2). Yani alarm büyüklük konusunda doğru, yön konusunda yanlıştı. Bu tipik
durum.

---

## Örnek 2 — alarm haklı (KONTR 4h)

![İyi KONTR](grafik_iyi_kontr.png)

Panel: tipik **3,4 ATR** · lehte 1,5 / aleyhte 1,7 → **yön zayıf** · bu sefer
**8,9 ATR → tipikten BÜYÜK**.

Alarm "aşağı" dedi ve fiyat 12 barda **7,0 ATR** düştü. Panel "bu sefer
tipikten büyük" diyor — yani **beklenenden büyük bir hareket** oldu ve alarm
yönünde oldu.

**Ne anlamalı:** Bu bir başarı **ama panel bunu önceden söylemiyordu.** Panel
"yön zayıf" diyordu; büyüklük tahmini doğruydu, yön tahmini ortalamada
kazançlı değildi.

---

## Örnek 3 — alarm yanlış (EREGL 4h)

![Kötü EREGL](grafik_kotu_eregl.png)

Panel: tipik **3,5 ATR** · lehte 1,1 / aleyhte 1,6 → **yön zayıf** · oynaklık
**sakin (%0 dilim)** · bu sefer 4,0 ATR → **≈ tipik**.

Alarm "yukarı" dedi, fiyat **3,4 ATR düştü**.

**Ne anlamalı:** "Sakin" dilim uyarısı önemli — oynaklık sembolün dibindeyken
alarm çıkmış ve ters yönde sert hareket olmuş. Düşük oynaklık, düşük risk
demek değil.

---

## Üçünden çıkan tek ders

Üç alarmın **üçünde de panel "yön zayıf"** dedi. Biri haklı (%7 ATR kazanç), biri
yanlış (%3,4 ATR kayıp), biri belirsiz.

Bu yüzden panelin 2. satırı **yön değil, yönün zayıflığını** söylüyor. Sen
grafiğe baktığında şunu aramalısın:

1. **Koni ne kadar geniş?** Genişse hareket büyük olacak, ama yönü belirsiz.
2. **Gerçekleşen koninin içinde mi?** İçindeyse "normal", dışındaysa "sürpriz".
3. **3. satır ne diyor?** Sakin dilimdeyse alarm sonrası hareket daha şaşırtıcı
   olur — sakinlik güvenlik sanılmasın.

---

## Kendi grafiğini üret

```bash
python -m research.grafik_alarm --sembol KONTR --tf 4h --bar 61 \
    --etiket "KIRILIM_TEYITLI" --yon -1 --cikti var/grafik/kontr.png
```

`--yon`: `1` yukarı, `-1` aşağı. Bar indeksi `var/replay/da_pol/tetikler.jsonl`
içinde (`symbol`, `timeframe`, `bar_index`).

Kod: [`research/grafik_alarm.py`](../../research/grafik_alarm.py).
Canlı çizim hattı (`grafik/render.py`) değişmedi.
