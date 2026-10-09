# Formation-Bot — Telegram format comparison examples

**Use:** Offline comparison only; no format was auto-selected and none was sent to Telegram. The underlying Formation replay used the existing cache values. A/B are current code formatters (`format_message` for the verbose/public renderer and `format_dm_message` for current DM). C/D/E are proposal-only renderings used to compare density and information order; they do not alter Formation state or policy.

**Data caveat:** This cache ends 2026-09-25. Times below are the original cache index labels with `+03:00`, not a separately inferred candle-close time. No live/current market quote, domain context, Volume, FVG, OB, or invented value is added. Display rounding in A/B/C/E is formatter presentation only; the source raw values appear in the table. `critical_price_level` / `break_price` here is the Formation’s existing boundary value, not a target or recommendation.

## 12 stratified cache-replay event rows

| # | Symbol | TF | Formation | State | Cache bar timestamp | Quality (raw) | Dir | Break level (raw) | Upper (raw) | Lower (raw) | Contraction (raw ratio) | Touches U/L | Age bars |
|---:|---|---|---|---|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| 1 | AKBNK | 1h | Alçalan Üçgen | KIRILIM_TEYITLI | `2026-08-10T11:30:00+03:00` | 87.96128447132105 | up | 67.37726870450106 | 67.37726870450106 | 66.58125495910645 | 0.6785201234830956 | 2/2 | 26 |
| 2 | AKBNK | 1h | Alçalan Üçgen | RETEST_BASARILI | `2026-08-10T12:30:00+03:00` | 87.96128447132105 | up | 67.29545038396662 | 67.29545038396662 | 66.58438014984131 | 0.6785201234830956 | 2/2 | 27 |
| 3 | AKBNK | 1h | Alçalan Üçgen | BASARISIZ_KIRILIM | `2026-08-10T14:30:00+03:00` | 87.96128447132105 | up | 67.13181374289773 | 67.13181374289773 | 66.59063053131104 | 0.6785201234830956 | 2/2 | 29 |
| 4 | PGSUS | 1h | Alçalan Kama | KIRILIM_TEYITLI | `2026-08-11T11:30:00+03:00` | 80.85786479729832 | down | 149.9823590446921 | 151.88666381835938 | 149.9823590446921 | 0.5112580781339309 | 2/2 | 35 |
| 5 | PGSUS | 1h | Alçalan Kama | RETEST_BASARILI | `2026-08-11T12:30:00+03:00` | 80.85786479729832 | down | 149.86471198586855 | 151.6999969482422 | 149.86471198586855 | 0.5112580781339309 | 2/2 | 36 |
| 6 | FROTO | 1h | Alçalan Kama | KIRILIM_TEYITLI | `2026-08-11T15:30:00+03:00` | 82.09968302621171 | up | 77.24000396728516 | 77.24000396728516 | 75.96200408935547 | 0.5409060399014788 | 2/2 | 42 |
| 7 | KRDMD | 2h | Alçalan Kama | KIRILIM_TEYITLI | `2026-08-11T15:30:00+03:00` | 83.61185024666538 | up | 39.80909035422585 | 39.80909035422585 | 38.0444450378418 | 0.573336973109835 | 2/2 | 28 |
| 8 | DOHOL | 2h | Yükselen Üçgen | KIRILIM_TEYITLI | `2026-08-12T11:30:00+03:00` | 87.17919425567246 | up | 21.277333068847657 | 21.277333068847657 | 20.780000686645508 | 0.5855779877590558 | 2/2 | 23 |
| 9 | FROTO | 1h | Alçalan Kama | FORMASYON_TAMAMLANDI | `2026-08-12T12:30:00+03:00` | 82.09968302621171 | up | 76.6160043334961 | 76.6160043334961 | 75.5780044555664 | 0.5409060399014788 | 2/2 | 48 |
| 10 | EREGL | 1h | Simetrik Üçgen | BASARISIZ_KIRILIM | `2026-08-20T10:30:00+03:00` | 80.61499466789245 | up | 37.769656214220774 | 37.769656214220774 | 37.565453789450906 | 0.9043430583642353 | 2/2 | 54 |
| 11 | AKBNK | 4h | Yükselen Kama | KIRILIM_TEYITLI | `2026-08-24T13:30:00+03:00` | 78.21953100689623 | up | 71.810009765625 | 71.810009765625 | 69.29999351501465 | 0.5518643004863585 | 2/2 | 37 |
| 12 | TAVHL | 1d | Alçalan Kama | KIRILIM_TEYITLI | `2026-09-21T00:00:00+03:00` | 73.48574708382111 | up | 271.4 | 271.4 | 246.96875 | 0.36520522388059656 | 2/2 | 29 |

## Renderings (five formats for the same event)

A = current verbose `format_message` renderer (random choice fixed by seed 42 for reproducibility); B = current compact DM `format_dm_message`; C–E are proposals only.

### Event 1: AKBNK · 1h · KIRILIM_TEYITLI · Alçalan Üçgen

**A — current verbose renderer** (`225 chars`)
```text
✅ AKBNK teyit aldı! yukarı kırılım
saatlik Alçalan Üçgen 67.38 kırılımı teyitli
Kalite 88 ⭐⭐⭐, daralma %68 - sıkışıyor, 4 temas
67.38 artık destek olabilir
Retest bekleniyor...

🔍 AKBNK saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`167 chars`)
```text
AKBNK · 1H Alçalan Üçgen
KIRILIM TEYİTLİ
Kalite 88 · Daralma %68 · 4 temas · 26 bar
Yukarı kırılım 67.37726870450106 teyitli · retest bekleniyor
Seviye destek olabilir
```

**C — proposal: event-first** (`113 chars`)
```text
AKBNK · 1h · Alçalan Üçgen
Kırılım teyitli — kalite 87.96
yukarı kırılım seviyesi: 67.3773 · bant 66.5813–67.3773
```

**D — proposal: structured field card** (`362 chars`)
```text
FORMATION EVENT | AKBNK · 1h · Alçalan Üçgen
State: Kırılım teyitli
Bar timestamp: 2026-08-10T11:30:00+03:00
Break direction: yukarı
Break level: 67.37726870450106
Formation band: lower=66.58125495910645; upper=67.37726870450106
Quality: 87.96128447132105
Contraction (stored ratio): 0.6785201234830956
Touches upper/lower: 2/2
Age (bars): 26
Retest observed: no
```

**E — proposal: compact one-screen** (`92 chars`)
```text
AKBNK 1h Alçalan Üçgen
Kırılım teyitli ↑ @ 67.3773
Q 88.0 · contraction 0.6785 · touches 2/2
```

### Event 2: AKBNK · 1h · RETEST_BASARILI · Alçalan Üçgen

**A — current verbose renderer** (`242 chars`)
```text
🎯 AKBNK RETEST BAŞARILI!
saatlik Alçalan Üçgen yukarı kırılım sonrası retest tuttu
Kalite 88 ⭐⭐⭐, 4 temas, 27 bar - formasyon tamamlanmaya yakın
Bu seviyelerden sonrası için kendi analizini yap

🔍 AKBNK saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`134 chars`)
```text
AKBNK · 1H Alçalan Üçgen
RETEST BAŞARILI
Kalite 88 · Daralma %68 · 4 temas · 27 bar
Yukarı kırılım 67.29545038396662 · retest başarılı
```

**C — proposal: event-first** (`113 chars`)
```text
AKBNK · 1h · Alçalan Üçgen
Retest başarılı — kalite 87.96
yukarı kırılım seviyesi: 67.2955 · bant 66.5844–67.2955
```

**D — proposal: structured field card** (`363 chars`)
```text
FORMATION EVENT | AKBNK · 1h · Alçalan Üçgen
State: Retest başarılı
Bar timestamp: 2026-08-10T12:30:00+03:00
Break direction: yukarı
Break level: 67.29545038396662
Formation band: lower=66.58438014984131; upper=67.29545038396662
Quality: 87.96128447132105
Contraction (stored ratio): 0.6785201234830956
Touches upper/lower: 2/2
Age (bars): 27
Retest observed: yes
```

**E — proposal: compact one-screen** (`92 chars`)
```text
AKBNK 1h Alçalan Üçgen
Retest başarılı ↑ @ 67.2955
Q 88.0 · contraction 0.6785 · touches 2/2
```

### Event 3: AKBNK · 1h · BASARISIZ_KIRILIM · Alçalan Üçgen

**A — current verbose renderer** (`152 chars`)
```text
❌ AKBNK kırılım başarısız
saatlik Alçalan Üçgen kırılım denedi ama geri döndü
Formasyon alanına dönüş - sahte kırılım olabilir
Tekrar sıkışma bekleniyor
```

**B — current compact DM** (`167 chars`)
```text
AKBNK · 1H Alçalan Üçgen
BAŞARISIZ KIRILIM
Kalite 88 · Daralma %68 · 4 temas · 29 bar
Başarısız kırılım 67.13181374289773
Fiyat kırılım sonrası formasyon alanına döndü
```

**C — proposal: event-first** (`115 chars`)
```text
AKBNK · 1h · Alçalan Üçgen
Başarısız kırılım — kalite 87.96
yukarı kırılım seviyesi: 67.1318 · bant 66.5906–67.1318
```

**D — proposal: structured field card** (`344 chars`)
```text
FORMATION EVENT | AKBNK · 1h · Alçalan Üçgen
State: Başarısız kırılım
Bar timestamp: 2026-08-10T14:30:00+03:00
Break direction: yukarı
Break level: 67.13181374289773
Formation band: lower=66.59063053131104; upper=67.13181374289773
Quality: 87.96128447132105
Contraction (stored ratio): 0.6785201234830956
Touches upper/lower: 2/2
Age (bars): 29
```

**E — proposal: compact one-screen** (`94 chars`)
```text
AKBNK 1h Alçalan Üçgen
Başarısız kırılım ↑ @ 67.1318
Q 88.0 · contraction 0.6785 · touches 2/2
```

### Event 4: PGSUS · 1h · KIRILIM_TEYITLI · Alçalan Kama

**A — current verbose renderer** (`212 chars`)
```text
✅ PGSUS teyit aldı! aşağı kırılım
saatlik Alçalan Kama 149.98 kırılımı teyitli
Kalite 81 ⭐⭐, daralma %51, 4 temas
149.98 artık direnç olabilir
Retest bekleniyor...

🔍 PGSUS saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`165 chars`)
```text
PGSUS · 1H Alçalan Kama
KIRILIM TEYİTLİ
Kalite 81 · Daralma %51 · 4 temas · 35 bar
Aşağı kırılım 149.9823590446921 teyitli · retest bekleniyor
Seviye direnç olabilir
```

**C — proposal: event-first** (`114 chars`)
```text
PGSUS · 1h · Alçalan Kama
Kırılım teyitli — kalite 80.86
aşağı kırılım seviyesi: 149.9824 · bant 149.9824–151.8867
```

**D — proposal: structured field card** (`361 chars`)
```text
FORMATION EVENT | PGSUS · 1h · Alçalan Kama
State: Kırılım teyitli
Bar timestamp: 2026-08-11T11:30:00+03:00
Break direction: aşağı
Break level: 149.9823590446921
Formation band: lower=149.9823590446921; upper=151.88666381835938
Quality: 80.85786479729832
Contraction (stored ratio): 0.5112580781339309
Touches upper/lower: 2/2
Age (bars): 35
Retest observed: no
```

**E — proposal: compact one-screen** (`92 chars`)
```text
PGSUS 1h Alçalan Kama
Kırılım teyitli ↓ @ 149.9824
Q 80.9 · contraction 0.5113 · touches 2/2
```

### Event 5: PGSUS · 1h · RETEST_BASARILI · Alçalan Kama

**A — current verbose renderer** (`239 chars`)
```text
🎯 PGSUS RETEST BAŞARILI!
saatlik Alçalan Kama aşağı kırılım sonrası retest tuttu
Kalite 81 ⭐⭐, 4 temas, 36 bar - formasyon tamamlanmaya yakın
Bu seviyelerden sonrası için kendi analizini yap

🔍 PGSUS saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`133 chars`)
```text
PGSUS · 1H Alçalan Kama
RETEST BAŞARILI
Kalite 81 · Daralma %51 · 4 temas · 36 bar
Aşağı kırılım 149.86471198586855 · retest başarılı
```

**C — proposal: event-first** (`114 chars`)
```text
PGSUS · 1h · Alçalan Kama
Retest başarılı — kalite 80.86
aşağı kırılım seviyesi: 149.8647 · bant 149.8647–151.7000
```

**D — proposal: structured field card** (`363 chars`)
```text
FORMATION EVENT | PGSUS · 1h · Alçalan Kama
State: Retest başarılı
Bar timestamp: 2026-08-11T12:30:00+03:00
Break direction: aşağı
Break level: 149.86471198586855
Formation band: lower=149.86471198586855; upper=151.6999969482422
Quality: 80.85786479729832
Contraction (stored ratio): 0.5112580781339309
Touches upper/lower: 2/2
Age (bars): 36
Retest observed: yes
```

**E — proposal: compact one-screen** (`92 chars`)
```text
PGSUS 1h Alçalan Kama
Retest başarılı ↓ @ 149.8647
Q 80.9 · contraction 0.5113 · touches 2/2
```

### Event 6: FROTO · 1h · KIRILIM_TEYITLI · Alçalan Kama

**A — current verbose renderer** (`211 chars`)
```text
✅ FROTO teyit aldı! yukarı kırılım
saatlik Alçalan Kama 77.24 kırılımı teyitli
Kalite 82 ⭐⭐, daralma %54, 4 temas
77.24 artık destek olabilir
Retest bekleniyor...

🔍 FROTO saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`166 chars`)
```text
FROTO · 1H Alçalan Kama
KIRILIM TEYİTLİ
Kalite 82 · Daralma %54 · 4 temas · 42 bar
Yukarı kırılım 77.24000396728516 teyitli · retest bekleniyor
Seviye destek olabilir
```

**C — proposal: event-first** (`112 chars`)
```text
FROTO · 1h · Alçalan Kama
Kırılım teyitli — kalite 82.10
yukarı kırılım seviyesi: 77.2400 · bant 75.9620–77.2400
```

**D — proposal: structured field card** (`361 chars`)
```text
FORMATION EVENT | FROTO · 1h · Alçalan Kama
State: Kırılım teyitli
Bar timestamp: 2026-08-11T15:30:00+03:00
Break direction: yukarı
Break level: 77.24000396728516
Formation band: lower=75.96200408935547; upper=77.24000396728516
Quality: 82.09968302621171
Contraction (stored ratio): 0.5409060399014788
Touches upper/lower: 2/2
Age (bars): 42
Retest observed: no
```

**E — proposal: compact one-screen** (`91 chars`)
```text
FROTO 1h Alçalan Kama
Kırılım teyitli ↑ @ 77.2400
Q 82.1 · contraction 0.5409 · touches 2/2
```

### Event 7: KRDMD · 2h · KIRILIM_TEYITLI · Alçalan Kama

**A — current verbose renderer** (`215 chars`)
```text
✅ KRDMD teyit aldı! yukarı kırılım
2 saatlik Alçalan Kama 39.81 kırılımı teyitli
Kalite 84 ⭐⭐, daralma %57, 4 temas
39.81 artık destek olabilir
Retest bekleniyor...

🔍 KRDMD 2 saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`166 chars`)
```text
KRDMD · 2H Alçalan Kama
KIRILIM TEYİTLİ
Kalite 84 · Daralma %57 · 4 temas · 28 bar
Yukarı kırılım 39.80909035422585 teyitli · retest bekleniyor
Seviye destek olabilir
```

**C — proposal: event-first** (`112 chars`)
```text
KRDMD · 2h · Alçalan Kama
Kırılım teyitli — kalite 83.61
yukarı kırılım seviyesi: 39.8091 · bant 38.0444–39.8091
```

**D — proposal: structured field card** (`359 chars`)
```text
FORMATION EVENT | KRDMD · 2h · Alçalan Kama
State: Kırılım teyitli
Bar timestamp: 2026-08-11T15:30:00+03:00
Break direction: yukarı
Break level: 39.80909035422585
Formation band: lower=38.0444450378418; upper=39.80909035422585
Quality: 83.61185024666538
Contraction (stored ratio): 0.573336973109835
Touches upper/lower: 2/2
Age (bars): 28
Retest observed: no
```

**E — proposal: compact one-screen** (`91 chars`)
```text
KRDMD 2h Alçalan Kama
Kırılım teyitli ↑ @ 39.8091
Q 83.6 · contraction 0.5733 · touches 2/2
```

### Event 8: DOHOL · 2h · KIRILIM_TEYITLI · Yükselen Üçgen

**A — current verbose renderer** (`218 chars`)
```text
✅ DOHOL teyit aldı! yukarı kırılım
2 saatlik Yükselen Üçgen 21.28 kırılımı teyitli
Kalite 87 ⭐⭐⭐, daralma %59, 4 temas
21.28 artık destek olabilir
Retest bekleniyor...

🔍 DOHOL 2 saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`169 chars`)
```text
DOHOL · 2H Yükselen Üçgen
KIRILIM TEYİTLİ
Kalite 87 · Daralma %59 · 4 temas · 23 bar
Yukarı kırılım 21.277333068847657 teyitli · retest bekleniyor
Seviye destek olabilir
```

**C — proposal: event-first** (`114 chars`)
```text
DOHOL · 2h · Yükselen Üçgen
Kırılım teyitli — kalite 87.18
yukarı kırılım seviyesi: 21.2773 · bant 20.7800–21.2773
```

**D — proposal: structured field card** (`366 chars`)
```text
FORMATION EVENT | DOHOL · 2h · Yükselen Üçgen
State: Kırılım teyitli
Bar timestamp: 2026-08-12T11:30:00+03:00
Break direction: yukarı
Break level: 21.277333068847657
Formation band: lower=20.780000686645508; upper=21.277333068847657
Quality: 87.17919425567246
Contraction (stored ratio): 0.5855779877590558
Touches upper/lower: 2/2
Age (bars): 23
Retest observed: no
```

**E — proposal: compact one-screen** (`93 chars`)
```text
DOHOL 2h Yükselen Üçgen
Kırılım teyitli ↑ @ 21.2773
Q 87.2 · contraction 0.5856 · touches 2/2
```

### Event 9: FROTO · 1h · FORMASYON_TAMAMLANDI · Alçalan Kama

**A — current verbose renderer** (`255 chars`)
```text
🏁 FROTO Alçalan Kama TAMAMLANDI
saatlik grafikte yukarı kırılım - retest olmadan ilerledi / fiyat kırılan seviyeye geri dönmedi, 4 temas, 48 bar
Kalite 82 ⭐⭐ - görev tamam
Yeni formasyon için taramaya devam

🔍 FROTO saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`167 chars`)
```text
FROTO · 1H Alçalan Kama
FORMASYON TAMAMLANDI
Kalite 82 · Daralma %54 · 4 temas · 48 bar
Yukarı kırılım 76.6160043334961 · retest olmadı; fiyat kırılan seviyeye dönmedi
```

**C — proposal: event-first** (`117 chars`)
```text
FROTO · 1h · Alçalan Kama
Formasyon tamamlandı — kalite 82.10
yukarı kırılım seviyesi: 76.6160 · bant 75.5780–76.6160
```

**D — proposal: structured field card** (`363 chars`)
```text
FORMATION EVENT | FROTO · 1h · Alçalan Kama
State: Formasyon tamamlandı
Bar timestamp: 2026-08-12T12:30:00+03:00
Break direction: yukarı
Break level: 76.6160043334961
Formation band: lower=75.5780044555664; upper=76.6160043334961
Quality: 82.09968302621171
Contraction (stored ratio): 0.5409060399014788
Touches upper/lower: 2/2
Age (bars): 48
Retest observed: no
```

**E — proposal: compact one-screen** (`96 chars`)
```text
FROTO 1h Alçalan Kama
Formasyon tamamlandı ↑ @ 76.6160
Q 82.1 · contraction 0.5409 · touches 2/2
```

### Event 10: EREGL · 1h · BASARISIZ_KIRILIM · Simetrik Üçgen

**A — current verbose renderer** (`153 chars`)
```text
❌ EREGL kırılım başarısız
saatlik Simetrik Üçgen kırılım denedi ama geri döndü
Formasyon alanına dönüş - sahte kırılım olabilir
Tekrar sıkışma bekleniyor
```

**B — current compact DM** (`169 chars`)
```text
EREGL · 1H Simetrik Üçgen
BAŞARISIZ KIRILIM
Kalite 81 · Daralma %90 · 4 temas · 54 bar
Başarısız kırılım 37.769656214220774
Fiyat kırılım sonrası formasyon alanına döndü
```

**C — proposal: event-first** (`116 chars`)
```text
EREGL · 1h · Simetrik Üçgen
Başarısız kırılım — kalite 80.61
yukarı kırılım seviyesi: 37.7697 · bant 37.5655–37.7697
```

**D — proposal: structured field card** (`348 chars`)
```text
FORMATION EVENT | EREGL · 1h · Simetrik Üçgen
State: Başarısız kırılım
Bar timestamp: 2026-08-20T10:30:00+03:00
Break direction: yukarı
Break level: 37.769656214220774
Formation band: lower=37.565453789450906; upper=37.769656214220774
Quality: 80.61499466789245
Contraction (stored ratio): 0.9043430583642353
Touches upper/lower: 2/2
Age (bars): 54
```

**E — proposal: compact one-screen** (`95 chars`)
```text
EREGL 1h Simetrik Üçgen
Başarısız kırılım ↑ @ 37.7697
Q 80.6 · contraction 0.9043 · touches 2/2
```

### Event 11: AKBNK · 4h · KIRILIM_TEYITLI · Yükselen Kama

**A — current verbose renderer** (`216 chars`)
```text
✅ AKBNK teyit aldı! yukarı kırılım
4 saatlik Yükselen Kama 71.81 kırılımı teyitli
Kalite 78 ⭐⭐, daralma %55, 4 temas
71.81 artık destek olabilir
Retest bekleniyor...

🔍 AKBNK 4 saatlik - daha fazlası için takipte kal
```

**B — current compact DM** (`165 chars`)
```text
AKBNK · 4H Yükselen Kama
KIRILIM TEYİTLİ
Kalite 78 · Daralma %55 · 4 temas · 37 bar
Yukarı kırılım 71.810009765625 teyitli · retest bekleniyor
Seviye destek olabilir
```

**C — proposal: event-first** (`113 chars`)
```text
AKBNK · 4h · Yükselen Kama
Kırılım teyitli — kalite 78.22
yukarı kırılım seviyesi: 71.8100 · bant 69.3000–71.8100
```

**D — proposal: structured field card** (`358 chars`)
```text
FORMATION EVENT | AKBNK · 4h · Yükselen Kama
State: Kırılım teyitli
Bar timestamp: 2026-08-24T13:30:00+03:00
Break direction: yukarı
Break level: 71.810009765625
Formation band: lower=69.29999351501465; upper=71.810009765625
Quality: 78.21953100689623
Contraction (stored ratio): 0.5518643004863585
Touches upper/lower: 2/2
Age (bars): 37
Retest observed: no
```

**E — proposal: compact one-screen** (`92 chars`)
```text
AKBNK 4h Yükselen Kama
Kırılım teyitli ↑ @ 71.8100
Q 78.2 · contraction 0.5519 · touches 2/2
```

### Event 12: TAVHL · 1d · KIRILIM_TEYITLI · Alçalan Kama

**A — current verbose renderer** (`218 chars`)
```text
✅ TAVHL teyit aldı! yukarı kırılım
günlük Alçalan Kama 271.40 kırılımı teyitli
Kalite 73 ⭐, daralma %37 - erken, 4 temas
271.40 artık destek olabilir
Retest bekleniyor...

🔍 TAVHL günlük - daha fazlası için takipte kal
```

**B — current compact DM** (`154 chars`)
```text
TAVHL · 1D Alçalan Kama
KIRILIM TEYİTLİ
Kalite 73 · Daralma %37 · 4 temas · 29 bar
Yukarı kırılım 271.4 teyitli · retest bekleniyor
Seviye destek olabilir
```

**C — proposal: event-first** (`115 chars`)
```text
TAVHL · 1d · Alçalan Kama
Kırılım teyitli — kalite 73.49
yukarı kırılım seviyesi: 271.4000 · bant 246.9688–271.4000
```

**D — proposal: structured field card** (`330 chars`)
```text
FORMATION EVENT | TAVHL · 1d · Alçalan Kama
State: Kırılım teyitli
Bar timestamp: 2026-09-21T00:00:00+03:00
Break direction: yukarı
Break level: 271.4
Formation band: lower=246.96875; upper=271.4
Quality: 73.48574708382111
Contraction (stored ratio): 0.36520522388059656
Touches upper/lower: 2/2
Age (bars): 29
Retest observed: no
```

**E — proposal: compact one-screen** (`92 chars`)
```text
TAVHL 1d Alçalan Kama
Kırılım teyitli ↑ @ 271.4000
Q 73.5 · contraction 0.3652 · touches 2/2
```

## Comparison notes

- A is the current verbose humanized renderer; it may use randomized template/footer text. The shown variant is reproducible under fixed seed, not a guarantee of the exact next random draw in production.
- B is the current compact DM renderer. Public channel routing continues to use the existing verbose renderer; this audit did not change public policy.
- C–E are only presentation candidates. The text is Formation-only, has no target price/financial advice, and intentionally does not infer MTF or domain context.
- Across the 12 samples, mean displayed lengths were A 213.0, B 160.2, C 114.0, D 356.5 and E 92.7 characters; this is a density comparison only, not a ranking or selection. If a format is chosen later, validate it with users and separately review DM/public route differences.