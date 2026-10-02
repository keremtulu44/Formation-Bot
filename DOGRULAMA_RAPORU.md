# Formation-Bot — Bağımsız Doğrulama Raporu

**Tarih:** 2 Ekim 2026 · **Kapsam:** Soru 1 (bildirim zamanlaması) + Soru 2 (doğruluk karnesi önerisi) + Soru 3 (dışarıdan bakış: eksikler)
**Not:** Bu raporda **hiçbir program dosyası değiştirilmedi**. Tüm iş kod okuma + ölçüm + canlı veri karşılaştırmasıydı. Rapor dosyası (`DOGRULAMA_RAPORU.md`) repoya eklenen tek yeni dosyadır.

---

## Kısa Cevaplar

1. **Bildirim, rutin akışta gerçekten yalnız *kapanmış* mumla geliyor.** Günlük formasyonun kırılımı da yalnız günlük mum kapandıktan sonra (bot 18:30 kuralı ile; gerçek kapanış müzayedesi ~18:09) — yani saatlik mum kapanışında "günlük kırılım" diye bir bildirim üretilmiyor. Ancak **3 istisna** var: (a) 1 saatlik mumun "kapandı" kuralı 30 dakika erken; bu yüzden **:00–:29 arasında tetiklenen** bir tarama (restart / kaçırılan tarama telafisi / çok uzun süren tarama) kısmi mumu kapanmış sayıp bildirim üretebilir; (b) günün son 2h/4h kovası (17:30–18:00) hiç analiz edilmiyor; (c) yarım günlerde (arefe) günlük mum 18:30'a kadar "yarım" sayıldığı için o gün günlük bildirim normalde hiç gitmiyor.
2. **Doğruluk karnesi yapılabilir ve mantıklı.** Bugünkü kodda ölçüm altyapısı yok (yalnız günlük sayaçlar var); gereken şey "sinyal defteri + ileri performans" katmanı. Tasarım, metrikler, örnek haftalık mesaj ve tuzaklar Bölüm 2'de.
3. **Dışarıdan bakışla 12 bulgu** çıkardım: 3'ü "sessiz yanlış sinyal / kaçırılan sinyal" sınıfında (P0), 4'ü görünürlük/güven (P1), 5'i mühendislik hijyeni (P2). Bölüm 3'te kanıtlarıyla.

---

# Bölüm 1 — Bildirim mum kapanışını bekliyor mu?

## 1.1 Kod zinciri (kanıt)

Motor, her taramada **yalnız tamamlanmış mumlarla** beslenir ve kırılım kararı **kapanış fiyatı** ile verilir:

| Adım | Yer | Ne yapıyor |
|---|---|---|
| 1 | `main.py` ~1541–1546 | `resample_all_timeframes()` → 1h/2h/4h (+ ayrı derin 1d verisi) |
| 2 | `main.py` ~1580 | **`df_tf = tamamlanmis_mumlar(df_tf, tf_name)`** — devam eden mum atılır |
| 3 | `data.py` 1036–1066 | Kapanış kuralı: `kapanis = etiket + TF_KAPANIS_SURESI`; `kapanis > now` ise mum **verilmez** |
| 4 | `data.py` 34–39 | 1h: +30 dk · 2h: +2 saat · 4h: +4 saat · 1d: `gün 00:00 + 18:30` |
| 5 | `patterns/lifecycle.py` 442–445 | Kırılım yalnızca **`close[b] > üst + buffer`** (kapanış) ile aday olur |
| 6 | `patterns/lifecycle.py` 617–652 | `KIRILIM_TEYITLI` ayrıca `confirm_window ≤ 2` **sonraki bar** ile teyit ister |
| 7 | `main.py` 1634–1700 | Anlık push yalnız `ALERT_STATES` (teyitli kırılım / retest / tamamlandı / başarısız kırılım); izleme state'leri 18:45 özetine ertelenir |

Yani: izleme (aday) mesajları 18:45 toplu özetine gider; **anlık bildirim için mumun kapanmış olması + kapanışın seviye dışına çıkması + 1–2 bar teyit** gerekir. Hiçbir yerde "anlık fiyat" ile kırılım üretilmiyor (`fetch_last_bar` yalnız sabah ön-yükleme için kullanılıyor; analize girmiyor).

## 1.2 Gerçek veriyle ölçüm

`bot_data` içindeki gerçek THYAO 1H serisi (360 bar, 40 seans) ile `tamamlanmis_mumlar` filtresini çalıştırdım:

| Tarama anı (25 Eyl 2026) | Analiz edilen son mum |
|---|---|
| 10:35 | 09:30 |
| 11:35 | 10:30 |
| 13:35 | 12:30 ✔ (gerçekten 13:30'da kapandı) |
| 17:35 | 16:30 ✔ |
| 18:05 | 17:30 ✔ |
| **18:35 (günün son taraması)** | **1h: 17:30 · 2h: 15:30 · 4h: 13:30 · 1d: günün mumu** |

- Günlük mum: 18:29'da **girmez**, 18:35'te **girer** (botun kuralı: gün 00:00 + 18:30). Gerçek BIST kapanış müzayedesi fiyatı ~18:09'da oluştuğu için bot, günlük kırılımı ancak gün bittikten sonra görüyor → **günlük formasyonun kırılımı, saatlik mumla asla bildirilmiyor.**
- Canlı Yahoo kontrolü (2 Eki 2026, chart API): seans `09:30–18:00`, barlar `09:30…17:30` (+ canlı günde kapanış müzayedesinin düz `18:00` barı). Günlük açılış/yüksek/düşük değerleri 1H barlarının **ilk barının** açılış/yüksek/düşük değerleriyle birebir (5 ayrı gün doğrulandı) → yfinance barları **sol-etiketli** (etiket = bar başı), günün ilk bölümü 09:30 etiketli.

## 1.3 İstisnalar (bunlar önemli)

### (a) 1 saatlik "kapandı" kuralı 30 dakika erken
Kod `1h` için kapanışı `etiket + 30 dk` sayıyor. Gerçek 1 saatlik mumların ömrü **1 saat** (günün son 17:30 barı hariç; o 30 dakika). Bu yüzden normal tarama saatleri (:35) sorunsuz çünkü:

- :35'te analiz edilen bar = **bir önceki saat :30'da gerçekten kapanan bar** (ör. 13:35 → 12:30 etiketli bar, 13:30'da kapandı).

Ama **:00–:29 arasında** bir tarama tetiklenirse, henüz kapanmamış bar "kapanmış" sayılır:

- Ölçüm: tarama anı 13:05 → analiz edilen son bar **12:30** (bar 12:30–13:30; yalnız 35/60 dakikası oluşmuş).
- Bu durum şu yollarda oluşabilir: bot **restart** olduğunda / kaçırılan tarama telafisinde (ana döngü `tarama_animi_mi` ile "son kapanış + 5 dk" kuralını kullanır), ya da bir tarama turu :00'ı geçecek kadar uzarsa.
- Bu senaryoda **anlık bildirim (send_alerts=True)** üretilebilir; sonraki tarama mumu gerçek kapanışıyla yeniden oynatır (motor `tam_yeniden=True` ile pencereyi baştan işler) ama **yanlış erken mesaj geri alınmaz** (mühür yalnız aynı state'in tekrarını engeller).
- Manuel `/tara` ve `/panel` bu riski taşımaz çünkü `send_alerts=False` ile çalışır (push yok, yalnız panel/özet görünürlüğü).

### (b) Günün son 2h/4h kovası hiç analiz edilmiyor
- 18:35 taramasında: 2h son analiz edilen = **15:30** kovası, 4h = **13:30** kovası.
- Sebep: resample ile oluşan son kova `17:30` etiketli (içinde yalnız 17:30–18:00 barı var, yani 30 dakikalık bir kova) ve kapanış kuralı `+2 saat / +4 saat` olduğu için 19:30/21:30'a kadar "yarım" sayılıyor.
- Yani günün kapanış saatindeki (17:30–18:00) hareket 2h/4h formasyonlarında **hiç değerlendirilmiyor**. TradingView aynı kovayı (günün son kısmi barı) gösterir → Pine uyumu hedefiyle çelişir.

### (c) Yarım gün: günlük mum o gün hiç bildirilmiyor
- 19 Mart 2026 (13:00 kapanış) ölçümü: günlük mum 13:05/13:35/14:05/18:05'te **"yarım"**, ancak 18:35'te "tamam" sayılıyor; çünkü kural sabit `18:30` (dosyada `seans_kapanis_saati()` fonksiyonu var ama `tamamlanmis_mumlar` onu kullanmıyor).
- Yarım günde 13:05'ten sonra yeni mum kapanmadığı için otomatik tarama da durur → günlük kırılım **o gün hiç push edilmez** (20:00 "gün sonu analizi" `send_alerts=False` olduğu için yalnız paneli günceller).

## 1.4 Cevap ve öneriler

**Şu anki durum:** Sorunuzun cevabı "evet, rutin akışta kapanmış mumla geliyor" — sizin gözlemlediğinizi düşündüğünüz "saatlikte günlük kırılım" senaryosu kodda mümkün değil. Buna karşılık yukarıdaki (a) istisnası tam olarak sizin sezdiğiniz "mum tam kapanmadan" durumunu yaratabilir; dar bir zaman penceresinde gerçekleşir.

**Öneriler (öncelik sırası):**
1. **Kapanış kuralını seansa bağla:** `kapanis = min(etiket + TF_süresi, o günün seans kapanışı)` — böylece 1h için +1 saat, günün son barı için +30 dk, yarım günde 13:00 doğru çıkar. (Tek fonksiyon: `data.tamamlanmis_mumlar`.)
2. **"Kapanmış mum" güvenlik kapısı:** bildirim üretmeden önce son barın kapanış anını yeniden doğrula (`bar_kapandi_mi`); kapalı değilse push'u bir sonraki tura ertele. Restart/telafi yolunu da bu kapı korur.
3. **Tarama zamanlamasına bağlılığı azalt:** `tamamlanmis_mumlar` artık doğruysa, telafi taraması :05'te de güvenli olur (yanlış sinyal riski kalkar).
4. **Günün son 2h/4h kovasını analiz et:** kapanış kuralı seans kapanışına çekildiğinde 17:30 kovası 18:00'de "tamam" olur; 18:35 taraması onu da işler.
5. **Mesaja mum bilgisini ekle (güven):** anlık mesajlarda şu an hangi mumun kapandığı görünmüyor (`time_str` yalnız bilinmeyen-state yedek dalında, `notifier.py` 1117). Örnek satır: `🕒 Mum: 25 Eyl 17:30 → 18:00 kapanış · kapanmış mum`. Bu, kullanıcı olarak sizin sorunuzu bir daha sormamanızı sağlar.

---

# Bölüm 2 — Doğruluk / Karne Sistemi Önerisi

## 2.1 Bugün ne var, ne yok

**Var:**
- `main.py` içinde günlük sayaçlar: taranan hisse, bulunan formasyon, `alerts_attempted/sent/failed/below_threshold/deferred/kuyruk`, hata, tarama süresi, veri yaşı.
- `/durum` çıktısında: `telegram_gonderim`, engeller (cooldown/kap), `alerts_attempted/failed`, `aday_hunisi`, bekleyen digest, acil kuyruk.
- `/ozet` (18:45 ve 09:55): o anki tamamlanan/retest/sıkışan listesi; 18:45'te bekleyen aday özeti.
- `LiveState`: hisse|TF başına **son** kayıt (panel için) — geçmiş değil.
- Supabase `bot_store`: OHLCV cache + state anahtarları (cooldown, mühür, digest tamponu…). Sinyal geçmişi **yok**.

**Yok (kritik):**
- Sinyalin **sonrasına** dair hiçbir ölçüm: kırılımdan sonra fiyat ne yaptı, hedefe mi gitti, ne kadar lehte/aleyhte hareket etti, endekse göre ne yaptı...
- TF/pattern/kalite kırılımlı başarı oranı; "huni" dönüşümü (aday → teyit → tamamlanma/başarısızlık).
- Kalite eşiklerinin (1h 80 / 2h 78 / 4h 75 / 1d 70) **kalibrasyonu** — yani yüksek kaliteli sinyaller gerçekten daha mı iyi?
- Kalıcılık: `daily_stats` bellekte; restart'ta günün sayaçları sıfırlanıyor (gece yarısı loglanan özet dışında tarihçe kalmıyor).

## 2.2 Önerilen tasarım: "Sinyal defteri + ileri performans"

### A. Sinyal kaydı (açılış)
`notifier.send` başarılı olduğu anda (mevcut `_tek_seferlik_isle` noktasının yanında) tek satır kayıt açılır:

| Alan | Örnek | Not |
|---|---|---|
| `id` | `THYAO|4h|KIRILIM_TEYITLI|2026-09-25T13:30` | hisse+TF+state+**kırılım barı** → aynı olay iki kez sayılmaz (motor pencereyi her taramada yeniden oynatıyor; mühür de var ama karne tarafında da tekilleştirme şart) |
| `stock/tf/pattern/state` | THYAO / 4h / Simetrik Üçgen / KIRILIM_TEYITLI | |
| `dir` | +1 / −1 | kırılım yönü |
| `bar_time`, `close_time` | 2026-09-25 13:30 / 17:30 | mum + kapanış anı |
| `entry` | 292.25 | teyit barının kapanışı (muhafazakâr alternatif: sonraki barın açılışı da saklanır) |
| `atr` | 3.4 | sinyal anındaki ATR (normalize etmek için) |
| `quality`, `break_strength`, `mtf_destek`, `age_bars` | 84 / 79 / True / 12 | |
| `data_age_dk` | 4.2 | sinyal anında verinin yaşı (bayat veriyle gelen sinyalleri ayrıştırmak için) |
| `benchmark` | XU100 kapanışı | göreli getiri için |

### B. İlerleme (her tarama sonunda, açık kayıtlar)
- Bar bar **MFE** (maksimum lehte hareket) ve **MAE** (maksimum alehte hareket) hem **%** hem **ATR** cinsinden.
- Ufuklar: TF barı cinsinden 1/3/5/10 bar **ve** takvim günü cinsinden 1/3/5 gün (1h ile 1d sinyali karşılaştırılabilsin diye ikisi de tutulur).
- **İlk-dokunma yarışı**: `MFE ≥ +1.5 ATR` **önce** gerçekleştiyse "hedef", `MAE ≥ −1.0 ATR` önce gerçekleştiyse "stop", ikisi de yoksa ufuk sonunda "nötr/kararsız" (kapanış yönü ile birlikte).
- **Yön doğruluğu**: ufuk sonunda kapanış, sinyal yönünde mi? (basit ve anlaşılır metrik)
- **Göreli sonuç**: aynı pencerede XU100 (Yahoo: `XU100.IS`) getirisi çıkarılır → "piyasa zaten yükseliyordu" etkisi ayıklanır. Bu, BIST'te kritik: boğa haftasında bütün kırılımlar "başarılı" görünür.

### C. Haftalık karne (Telegram digest)
Örnek çıktı (sizin istediğiniz formata yakın):

```
📊 HAFTALIK DOĞRULUK KARNESİ · 06–10 Eki 2026
Tarama: 5 gün × 48 hisse × 4 TF = 960 slot
Canlı formasyon: 41 · Tekil hisse: 23
  1h 18 | 2h 9 | 4h 8 | 1d 6
Teyitli kırılım: 17 (yukarı 11 / aşağı 6)
Kırılım sonrası 10 bar (XU100'e göre):
  ✅ Hedef (MFE ≥ 1.5 ATR, önce): 8/17 (%47)
  ⚪ Nötr (±1 ATR içinde):        5/17 (%29)
  ❌ Stop (MAE ≥ 1 ATR, önce):    4/17 (%24)
  Ortalama MFE +%2.9 · ortalama MAE −%1.4 · ort. 6 bar
TF: 1h %41 | 2h %50 | 4h %57 | 1d %67 (n küçük)
Kalite kalibrasyonu: q≥85 %62 · 75–84 %44 · <75 %31
En çok formasyon: THYAO 4 · GARAN 3 · ASELS 3
En iyi: ASELS 4h +%9.2 · En kötü: PETKM 1h −%5.1
⚠️ n=17: yüzde yorumu için en az 30–50 sinyal biriktirin
```

- Ayrıca **huni** satırı: `aday 38 → teyit 17 → retest başarılı 6 → tamamlanan 9 → başarısız 5` (mevcut state'lerden doğrudan).
- **Eşik altı adayların karşı-olgusal karnesi** (`alerts_below_threshold` şu an sadece sayılıyor): kalite eşiğinin altında kalan adayların sonradan ne yaptığı → eşiklerin gerçekten işe yarayıp yaramadığını gösterir. Bence en değerli ikinci metrik budur.
- **Komut önerisi:** `/dogruluk` (son 7/30 gün), `/dogruluk THYAO 4h`, `/dogruluk --tf 1d`.

### D. Nerede uygulanır (kod yazmadan, akış önerisi)
- Yeni modül: `tracking/accuracy.py` (saf hesap, test edilebilir) + `tracking/store.py` (kalıcılık).
- Kalıcılık: mevcut altyapı iki seçenek sunuyor — (1) hızlı başlangıç: `bot_store` içinde `state:signal_journal:<hafta>` JSON kayıtları (dosya + Supabase, mevcut `state/persistence.py` deseniyle); (2) analitik için: `supabase_schema.sql`'e `signals` tablosu (id, stock, tf, …, mfe, mae, resolved_at) — SQL ile sorgulanabilir, önerim bu.
- Kancalar: (i) `main.py` bildirim başarısı (`_tek_seferlik_isle` yanı), (ii) `scan_all_stocks` sonu (açık sinyalleri güncelle), (iii) 18:45/gün sonu (hafta kapandıysa digest).
- **Geriye dönük karne:** `bot_data/` içinde 28 hisse × 40 seans **gerçek veri** zaten var; aynı motor bir kez bar-bar oynatılarak geçmiş sinyaller üretilip ileri getiriler hesaplanabilir → ilk karnenin canlı beklemeden çıkması mümkün (yaklaşık 16 sn'lik motor süresi; ölçüm: 5 hisse × 4 TF = 1.68 sn).

### E. Tuzaklar (karnenin yanlış olmaması için)
1. **Çift sayım:** motor her taramada pencereyi yeniden oynatır → aynı kırılım onlarca kez üretilir; kimlik `kırılım barı + yön` olmalı. (Notifier mührü de aynı işi yapar ama karne ona bağımlı olmamalı.)
2. **Giriş varsayımı:** teyit barının kapanışından girmek hafif iyimserdir; gerçekçi varsayım "sonraki barın açılışı". İkisini de raporlayıp farkı görün.
3. **Ölçüm ufku TF'e göre değişir:** 1h'te 10 bar ≈ 1.5 seans, 1d'de 10 bar = 2 hafta. Hem bar hem gün bazlı ufuk tutun.
4. **Endeks/piyasa etkisi:** XU100'e göre raporlamadan "başarı oranı" yanıltıcıdır. Ayrıca sektör/volatilite rejimi ayrımı faydalı olur.
5. **N küçük:** 17 sinyalde %47 ile %24 arasındaki fark gürültüdür; en az 30–50 sinyal + "n" ve mümkünse güven aralığı yazın.
6. **Veri kalitesi karışmasın:** `data_age_dk`/bayat veri ile gelen sinyaller karneye ayrı dilim olarak girmeli (bayat veriyle üretilen "kırılım" gerçek değildir).
7. **Sabit % eşiği kullanmayın:** sizin örneğinizdeki "%50 hareket" BIST'te tipik olarak anlamlı bir bar/uygarlık değil; sinyali **ATR'ye normalize** edin (±1 ATR gürültü, ±1.5–2 ATR hedef). İsterseniz "kırılımdan sonra X bar içinde %Y hareket olanların oranı" biçiminde basit bir görünüm de eklenir; ama asıl karne ATR + endeks göreli olmalı.

---

# Bölüm 3 — Dışarıdan Bakış: Eksikler

Aşağıdakiler "kodu bilen biri" değil, "sistemi dışarıdan denetleyen biri" gözüyle sıralandı. Zaten `YAPILACAKLAR.md`'de olanlar (A1–A10, B1–B10, C1–C7) ayrıca işaretlendi; tekrar listelemedim.

## P0 — Sessiz yanlış/eksik sinyal riski (önce bunlar)

| # | Bulgu | Kanıt | Etki |
|---|---|---|---|
| P0-1 | **1h kapanış kuralı 30 dk erken** (`etiket+30dk`), gerçek 1h barları 1 saat ömürlü | `data.py` 34–39 + 1036–1066; ölçüm: 13:05 taraması 12:30 barını "kapanmış" sayar; testler yalnız 17:59/18:00 sınırını ölçüyor | :00–:29 arasında tetiklenen tarama (restart/telafi/uzun tur) kısmi mumla bildirim üretebilir; sonradan düzeltilmez |
| P0-2 | **Günün son 2h/4h kovası (17:30–18:00) hiç analiz edilmiyor** | Ölçüm: 18:35 → 2h son=15:30, 4h son=13:30; `+2h/+4h` kuralı kovayı 19:30/21:30'a kadar "yarım" sayıyor | Kapanış saatindeki hareket 2h/4h'de kayıp; TradingView/Pine ile fark |
| P0-3 | **Yarım günde günlük mum 18:30'a kadar yarım** | `tamamlanmis_mumlar` sabit `18:30` kullanıyor, `seans_kapanis_saati()` (13:00) devrede değil; ölçüm 19 Mart: 13:05/14:05/18:05 "hayır", 18:35 "evet" | 2–3 gün/ yıl günlük sinyal kaybı; yarım günde 2h/4h kapanışı da 30 dk geç |

## P1 — Görünürlük, güven, operasyon

| # | Bulgu | Kanıt | Etki |
|---|---|---|---|
| P1-1 | Anlık mesajlarda **mum/kapanış zamanı yok** | `notifier.py`: `time_str` yalnız 1117 (bilinmeyen-state yedek dalı) | Kullanıcı "bu mesaj kapanmış muma mı ait?" sorusunu soramıyor/cevaplayamıyor (sizin sorunuzun kaynağı) |
| P1-2 | **İleri performans karnesi yok** | Bölüm 2 | Sistemin işe yarayıp yaramadığı ölçülemiyor; eşik kalibrasyonu imkânsız |
| P1-3 | **`daily_stats` kalıcı değil** | `main.py` 241+; yalnız gece yarısı loglanıyor | Restart günün sayaçlarını siliyor; karne/tarihçe için veri kaybı |
| P1-4 | **Log rotasyonu yok** | `setup_logging()` düz `FileHandler`; repoda `RotatingFileHandler` yok | Uzun süreli worker'da `bot.log` sınırsız büyür (disk) |
| P1-5 | **Sessizlik alarmı (dead-man) yok** | Heartbeat/tazelik var; "kaç taramadır 0 formasyon" kontrolü yok | Yahoo veri şekli değişse ve bot "0 formasyon" üretmeye başlasa, sinyal tarafında hiçbir uyarı çıkmaz |

## P2 — Mühendislik hijyeni

| # | Bulgu | Kanıt | Etki |
|---|---|---|---|
| P2-1 | **Yahoo veri sözleşmesi kontrol edilmiyor** | Gerçek seans 09:30–18:00 + ~18:09 müzayede; kod/yorumlar "son 1h barı 17:30, 18:30 kapanır" varsayıyor; günün ilk barının hacmi **1120 seans-gününün 1083'ünde 0** | Hacim skoru (`breakStrength` %8) günün ilk barında sistematik yanlış; Yahoo format değişirse sessiz bozulma |
| P2-2 | **Resample kova fazı ilk bara bağlı** | `resample_ohlcv` offset'i `df.index[0]`'dan alıyor; ölçüm: ilk bar (09:30) düşerse 2h kovaları 12:30/14:30/16:30'a, 4h 06:30/10:30/14:30'a kayıyor | Eski gündeki tek eksik bar tüm 2h/4h serisini TradingView'den kaydırır (Pine-birebir hedefi sessizce bozulur) |
| P2-3 | **Test koleksiyonunda yan etki** | `test_accuracy.py` import **30.8 sn** (tüm tanıyı import anında çalıştırıyor); pytest koleksiyonu ~60 sn, koşu 81 sn; 331 test geçiyor, `test_tarama_zamani.py` 100/100 | CI süresi şişiyor; tanılar "test" gibi görünüyor ama assert etmiyor |
| P2-4 | **Ölçülen ama takip edilmeyen metrik** | `test_accuracy.py` çıktısı: rastgele yürüyüşte yanlış pozitif **%8** (dosyanın kendi notu: hedef <%5) | Regresyon olarak izlenmiyor; kalite düşüşü fark edilmez |
| P2-5 | **Doküman/kod tutarsızlığı** | `config.py`: `BIST_CLOSE=18:10`, yorumlar "gerçek kapanış"; akışta 18:30/18:45; README "son mum 18:30'da kapanır" | Yeni geliştirici/karar verici yanlış modele göre değişiklik yapar (bu raporun çıkış nedenlerinden) |
| P2-6 | **Monolit dosyalar** | `main.py` 2495, `data.py` 1257, `notifier.py` 1241 satır | Uzun vadeli bakım (YAPILACAKLAR C2 ile aynı) |
| P2-7 | **Eksik depolar metadata** | LICENSE yok; linter/type-check yok; testler kök dizinde dağınık | Kamuya açık repoda kullanım/lisans belirsizliği; kod kalitesi otomatik izlenmiyor |

### Zaten bilinenlerle eşleşme
`YAPILACAKLAR.md`'de olan ve bu raporda tekrar etmediğim başlıklar: A1 (son_tarama merge), A2 (tatil/yarım gün döngüsü), A5 (4096/kap), A8 (.pkl), B1 (kullanılmayan sinyal göstergesi), B3 (digest kalıcılığı), B5 (yazma amplifikasyonu), B6 (eşik altı görünürlük), B10 (çoklu örnek), C1–C7. Benim eklediğim P0-1/P0-2/P0-3, P1-1, P2-1, P2-2 ve P2-4 bu listede **yok**.

---

## Ek — Nasıl doğruladım (tekrarlanabilir)

```bash
# 1) Motor süresi ve zamanlama ölçümü (repo kopyasına dokunmadan, /tmp'de venv)
python3 -m venv /tmp/venv && /tmp/venv/bin/pip install pandas==2.2.2 numpy==1.26.4 pytz requests python-dateutil pytest==8.3.2
# /tmp/demo_tf.py  -> tamamlanmis_mumlar + resample kapanış ölçümleri (Bölüm 1.2/1.3 çıktıları)
# /tmp/bench.py    -> 5 hisse x 4 TF motor süresi (1.68 sn) ; /tmp/bench2.py -> bar sayısına göre süre
# 2) Mevcut testler (yeşil)
/tmp/venv/bin/python -m pytest -q                 # 331 passed (81 sn)
/tmp/venv/bin/python test_tarama_zamani.py        # 100/100
# 3) Yahoo sözleşmesi (gerçek veri)
curl "https://query1.finance.yahoo.com/v8/finance/chart/THYAO.IS?interval=1h&range=1d"    # seans/kova/hacim şekli
curl "https://query1.finance.yahoo.com/v8/finance/chart/THYAO.IS?interval=1d&range=1mo"   # günlük açılış = 09:30 barı açılışı
```

**Ölçülen sayılar:** 331 test / 100 kontrol geçti · motor: 0.121 sn (360 bar 1h), 0.310 sn (500 bar 1d) → 48 hisse tahmini ~16–26 sn · günün ilk 1h barı hacmi 1120 seans-gününün 1083'ünde 0 · 18:35 taraması: 1h=17:30, 2h=15:30, 4h=13:30, 1d=gün mumu · 13:05 taraması: 12:30 (kısmi).

---

# EK — UYGULANAN P0 DÜZELTMELERİ (2 Eki 2026, aynı gün)

Bu raporun 1. bölümündeki üç kritik bulgu + mesaj görünürlüğü düzeltildi.
Kod değişiklikleri: `data.py`, `main.py`, `notifier.py`, `reporting/format.py`,
`state/persistence.py`, `config.py` (yalnız yorum), `README.md`, testler.

| Bulgu | Düzeltme | Kanıt |
|---|---|---|
| **P0-1** 1h kapanışı 30 dk erken (`etiket+30dk`) | Kapanış = `etiket + TF süresi`, o günün seans sonunu aşamaz (`TF_BAR_SURELERI`, `mum_kapanis_anlari`) | 13:05 taraması artık **11:30** (eskiden 12:30, kısmi bar) |
| **P0-2** Günün son 2h/4h kovası hiç analiz edilmiyordu | Kova seans sonunda (18:00) kesilir | 18:35 → 2h **17:30**, 4h **17:30** (eskiden 15:30 / 13:30) |
| **P0-3** Yarım günde günlük mum 18:30'a kadar yarım | Günlük mum o günün `seans_kapanis_saati()` ile tamamlanır (arefe 13:00) | 19 Mart: 12:59'da yok, **13:00'de tamam** (eskiden 18:35'e kadar yok) |
| **P1-1** Mesajda hangi mum kapandığı görünmüyordu | Anlık mesajlara `🕒 … mum … → … kapandı` satırı (`mum_kapanis_metni`) | `test_notifier_anlik_mesaja_mum_satiri_ekler` |
| — (yeni) Güvenlik kapısı | `bar_kapandi_mi()` push öncesi son kontrol; kapanmamışsa push ertelenir + sayaç | `test_kapanmamis_barla_push_yok` / `test_kapanmis_barla_push_uretilir` |
| — (yeni) JSON serileştirme | `bar_kapanis` ISO string; kalıcılık/kuyruk yazımlarına `default=str` | uçtan uca tarama testinde "Son tarama dosyaya kaydedilemedi" uyarısı kayboldu |

**Doğrulama:** `python -m pytest -q` → **354 test geçti** (önceki 331 + 23 yeni);
`python test_tarama_zamani.py` → **102/102** (önceki 100 + 2 yeni kontrol).
Uçtan uca: gerçek 4 hisse cache'iyle tarama → kayıtlarda `bar_kapandi=True`,
mesaj satırı doğru, günlük sayaç `alerts_bar_kapanmadi=0`.

**Davranış değişikliği notu (bilinçli):** 18:35 taraması artık günün son 2h/4h
kovasını da işler. Bu kova BIST'te 30 dakikalık (17:30–18:00) bir kovadır ve
TradingView'in 4 saatlik grafiğinde de aynı şekilde görünür; "kapanmış mum"
sayıldığı için (seans sonu) kırılım bildirimi üretebilir. İstenmezse
`data.mum_kapanis_anlari`'daki kesme kaldırılarak bu kova dışlanabilir.

---

# EK 2 — HAFTALIK DOĞRULUK KARNESİ (uygulandı: 2 Eki 2026)

Raporun 2. bölümündeki "doğruluk karnesi" tasarımı, **Supabase gerektirmeden**
ve **Cuma gün sonu mesajının altına eklenerek** uygulandı.

| Karar | Uygulama |
|---|---|
| Supabase gerekmesin | Defter tek yerel dosya: `DATA_DIR/karne_defteri.json` (atomik `.tmp`→`os.replace`). `supabase_store` hiç çağrılmaz; uzak store olmadan da tam çalışır. |
| Gün sonu mesajı altında | Cuma 18:45 `📋 Günlük Özet`'in altına eklenir; gönderilemezse (bot kapalı / hata) 20:00 `🌙 GÜN SONU ANALİZİ`'nin altına eklenir ve haftalık işaret konur. |
| Her Cuma | `KARNE_GUNU=4` (env ile değişir); haftada bir kez (ISO hafta işareti, kalıcı). `/karne` ile her an. |
| Mesaj sınırı | Karne eklenince mesaj 3900 karakteri aşarsa karne **ayrı mesaj** olur (`_karneyle_gonder`); `kirp()` sondan kestiği için karne kaybolmaz. |
| Ölçüm | Kırılım kaydı: giriş = teyit barının kapanışı + yön + kalite + ATR. Sonraki barlarda MFE/MAE; ilk dokunuş yarışı: hedef (1.5 ATR) / stop (1.0 ATR) / nötr; aynı barda ikisi de varsa stop (muhafazakâr). Yön doğruluğu ayrı satır. |
| Tekilleştirme | Kırılım: `hisse|TF|K|bar` (motor pencereyi her taramada yeniden oynatır). Formasyon: `hisse|TF|formasyon` + 48 saat TTL. |
| Bakım | `KARNE_SAKLAMA_GUN=120` ile eski kayıtlar budanır (dosya sınırsız büyümez). |

**Örnek çıktı** (gerçek cache ile uçtan uca):

```
📊 HAFTALIK DOĞRULUK KARNESİ · 28.09–02.10.2026
5 seans · defter: 8 kayıt (yerel dosya)

🔍 Formasyon tespiti: 5
 1 saatlik 2 · 4 saatlik 1 · günlük 1 · 2 saatlik 1
 Hisse: (4 hisse)
 THYAO 2 · ASELS 1 · EREGL 1 · GARAN 1

⚡ Kırılım sinyali: 2 (yukarı 2 · aşağı 0)
 10 bar içinde: hedef 1 · nötr 0 · stop 1
 Kırılım yönünde kapatan: 1/2 (%50) · ters 1 · yatay 0
 Ort. maks. lehte +%2.1 · alehte −%2.1
 TF (yönünde/n): 1 saatlik 1/2
 Kalite: q≥80 1/1 · q70–79 0/1
 En iyi: THYAO 1h %+3.0 · En kötü: ASELS 1h %-4.0

🔁 Huni: kırılım 2 → tamamlanan 1

⚠️ n=2 küçük: oranlar için 30+ sinyal birikmeli
ℹ️ Veriler yerel dosyada (Supabase gerekmez) · /karne ile istediğin an al
```

**Test:** `test_karne.py` 25 test (defter/tekilleştirme/buda, MFE-MAE ve yön aynası,
rapor metni, Cuma kapısı, gönderim tekilliği, mesaj sınırı güvenliği, tarama
sırasında defter kaydı). Toplam suite: **379 test**; `test_tarama_zamani.py` 102/102.

**Bilinen sınır:** Ölçüm yalnız botun topladığı veriyle yapılır; bot/worker kapalıyken
geçen barlar sonraki ilk taramada tek seferde işlenir (sinyal anı gerçek bar kapanışı
olduğu için giriş fiyatı kaymaz). Karne boş haftalarda (kayıt yoksa) gönderilmez.
