# Public Grup Hazırlık Analizi — Bildirim Hattı ve Dil

> Tarih: 2026-10-02 · Dal: `arena/01a0fdec-formation-bot` · Dayanak: kod okuması + 384 test
> Bu doküman "şu an neredeyiz, public grup için ne eksik?" sorusunun ölçülmüş cevabıdır.

## 0) Kısa hüküm

- **Bildirim hattı sağlam ve testli.** DM + tek public kanal yolu olgun: gürültü kapıları,
  tek-seferlik mühür, engellenen olay kuyruğu, gönderim sağlığı, mum kapanışı güvenliği hepsi var.
- **Public kanal akışı bugün "yarım yayın" modunda:** kanala yalnız 2 state (+ kalite ≥ 80) ve
  günlük özet gidiyor; 18:45 izleme digest'i ve haftalık karne kanala **hiç gitmiyor**.
- **"Public grup" (supergroup) bugün tam çalışmaz:** yayın tarafı (`TELEGRAM_CHANNEL_ID` bir grup
  ID'si olabilir) çalışır, ama **etkileşim tarafı çalışmaz** — komutlar yalnız tek bir `chat_id`'den
  kabul ediliyor (`telegram_commands.py:264`), grup komutları sessizce yok sayılır.
- **Dil: %100 Türkçe ve koda gömülü.** i18n katmanı yok; uluslararası bir grup hedefleniyorsa
  mesaj şablonlarının sözlüğe taşınması gerekir (ölçüm ve plan aşağıda).

## 1) Bildirim hattı bugün nasıl çalışıyor?

| Katman | Dosya | Görev |
|---|---|---|
| Gönderim motoru | `notifier.py` | Mesaj biçimi, DM + kanal gönderimi, cooldown/kap/mühür/kuyruk |
| Politika (tek kaynak) | `config.py:343-380` | `ALERT_STATES`, `WATCH_STATES`, `PUBLIC_STATES`, `ALERT_MIN_QUALITY` |
| Erteleme tamponu | `telegram_alert_flow.py` | Düşük öncelikli adayları 18:45 digest'ine biriktirir |
| Metin üretimi | `reporting/format.py`, `reporting/panel.py` | Özet/digest/panel metinleri, `STATE_TR` |
| Komut katmanı | `telegram_commands.py` | Webhook **veya** yoklama; yetki + hız kontrolü |
| Zamanlama | `main.py:2528-2600` | 09:55 / 18:45 özetleri, Cuma karne, 20:00 gün sonu |

**Akış:**

1. **Anında DM** (4 kritik state): `KIRILIM_TEYITLI`, `RETEST_BASARILI`, `FORMASYON_TAMAMLANDI`,
   `BASARISIZ_KIRILIM` — TF bazlı kalite eşiği (`1h:80 / 2h:78 / 4h:75 / 1d:70`) ile.
2. **18:45 digest'e ertelenen** (6 izleme state): sıkışma, kırılım hazırlığı/adayı/denemesi,
   retest bekleniyor/ediliyor. Tampon kalıcı (`telegram_digest_pending.json`), taşma şeffaf
   ("12/21 gösteriliyor" + "… N aday daha").
3. **Günlük özet** (09:55 + 18:45) DM'e; kanala ise yalnız temel özet (`main.py:2594`).
4. **Cuma doğruluk karnesi**: yalnız DM özetinin altına eklenir (`main.py:2560-2570`).

**Sağlamlık ağları (testli):** saatlik 20 / günlük 120 mesaj kapı · 4 saat cooldown ·
tek-seferlik mühür (hisse+TF+state, günde 1, bar süresine ölçekli TTL) · engellenen acil olay
kuyruğu (20 kayıt / 180 dk TTL) · gönderim sağlığı heartbeat'i · 4000 karakter kırpma ·
429/5xx'te tekrar deneme · kapanmamış mumla push etmeme (P0 koruması) · 409/401 teşhis ipuçları.

**Test durumu:** suite **384 test, hepsi geçiyor**. Bu turda duvar saatine bağlı kırılan
1 flaky test düzeltildi (`test_karne.py::test_main_karne_ekleme_kapisi`, İstanbul saati 18:45'i
geçince CI'da kırmızı oluyordu — kayıt `now` parametresi verilmeden duvar saatiyle atılıyordu).

## 2) Public grup için teknik açıklar (öncelik sırasıyla)

### P0 — Bugün bloke eden maddeler

1. **DM olmadan bot tamamen pasif.** `notifier.__init__`: token **veya** `TELEGRAM_CHAT_ID` yoksa
   `enabled=False`; bu durumda kanala/grupa gerçek gönderim yapılmaz (mock log). Yani "sadece public
   grup" kurulumu mümkün değil; bir sahip DM'i tanımlı kalmak zorunda. Karar: grup hedefini DM'den
   bağımsız bir gönderim yolu yapmak.
2. **Kanal gönderimi DM başarısına bağlı.** `notifier._gonder` (1188+): DM `HTTP 200` almazsa kanal
   adımına hiç gelinmez. Sahip botu bloklarsa / DM 403 alırsa **public grup da susar**. Grup için
   bağımsız gönderim (kendi kapıları, kendi hata sayacı) gerekir.
3. **Gruplarda komut dinlenmiyor.** `telegram_commands.py:264`: `chat_id != allowed_chat_id` →
   sessizce yok sayılır. Tek `allowed_chat_id` var; çok sohbet/yetki modeli yok.
   (İyi haber: `komut_coz` `/komut@BotAdı` biçimini zaten destekliyor — grup için şart.)

### P1 — Grup açılmadan önce yapılması gerekenler

4. **Hedef başına kap/retry yok.** Saatlik/günlük kap, cooldown ve mühür DM yolunda; `send_to_channel`
   tek deneme yapar, hata sayar ve bırakır. Telegram'ın pratik sınırı grup başına ~20 mesaj/dk'dır;
   grup + kanal + DM üçe çıkınca hedef başına kuyruk/pacing gerekir.
5. **Digest ve karne public'e kapalı.** 18:45 izleme digest'i ve Cuma karnesi yalnız DM'e gidiyor.
   Bu, YAPILACAKLAR.md'deki **B9** maddesinin de özü: "kanala ne gitsin?" kararı verilmeden
   grup açılırsa grup sadece 2 tip mesaj + 2 özet görür (çok seyrek).
6. **Yetki modeli yok.** Grup ID'sini `TELEGRAM_CHAT_ID` yaparsan **her üye** `/panel` (tüm evreni
   yeniden hesaplar) ve `/tara` çalıştırabilir → kaynak kötüye kullanımı. Üye bazlı rol
   (herkes / yalnız adminler / hiç kimse) ve komut başına yetki gerekir.
7. **Kanal mesajı = DM mesajı.** `send_to_channel(message)` aynı metni gönderir; metinde iç izleme
   notları olabiliyor ("teyit bekleniyor", "retest tutarsa yapı güçlenir"). Public dil için ayrı,
   yalnız olgu bildiren bir "public şablon" katmanı önerilir.
8. **Grup onboarding'i yok.** Sabitlenmiş karşılama/kurallar mesajı, günlük tekrar eden davet
   linki paylaşımı, moderasyon yok.

### P2 — Konfor

9. Çok hedef (DM + kanal + grup) tek env listesiyle (`TELEGRAM_HEDEFLER=dm:123,kanal:-100...,grup:-100...`).
10. `/durum` çıktısına hedef başına gönderim sayacı eklemek.
11. Kanal tarafına da "özet geldi/gidemedi" kalıcılığı (şu an yalnız DM özeti tekilleşiyor).

## 3) Dil durumu

**Bugün:** tüm kullanıcı-görünür metin Türkçe ve Python içine gömülü (yaklaşık satır dağılımı):

| Dosya | Türkçe içerikli satır |
|---|---|
| `main.py` (komut/özet/karne metinleri) | 664 |
| `notifier.py` (alarm şablonları) | 319 |
| `karne.py` | 105 |
| `reporting/format.py` (panel/digest + `STATE_TR`) | 82 |
| `telegram_commands.py` | 68 |
| `reporting/panel.py` | 36 |

**İyi olan:** `STATE_TR` tek kaynak (`reporting/format.py:31`) — alarm, panel ve digest aynı Türkçe
durum adını kullanıyor; tarih/sayı biçimi de TR (Oca/Şub, `%72`). Yani "karışık dil" sorunu yok.

**Eksik olan:** dil seçimi (i18n) yok. `format_message` içinde 14 state için `if/elif` bloklarıyla
satır satır metin üretiliyor; ikinci dil eklemek bugün kopyala-yapıştır demek olurdu.

**Uluslararası grup hedefleniyorsa öneri:** `reporting/messages.py` (veya `i18n.py`) altında
`tr`/`en` sözlükleri + `LANG` env'i (hedef bazlı: `LANG_DM=tr`, `LANG_PUBLIC=en`). Çevrilecek yüzey
5 fonksiyondan ibaret: `notifier.format_message`, `notifier.format_daily_summary`,
`reporting.format.format_deferred_alert_summary` + `panel_*`, `karne.karne_metni`,
`main.KOMUT_YARDIM`. Durum/desen adları zaten sözlükten geldiği için onlar da tek yerden çevrilir.

## 4) Önerilen sıra (grup açılışı için)

1. **Faz A — Hedef bağımsızlığı:** kanal/grup gönderimini DM'den ayır (P0-1, P0-2), hedef başına
   kap + retry + hata sayacı (P1-4). Bot DM'i olmadan da gruba yayın yapabilmeli.
2. **Faz B — Etkileşim:** çok sohbetli komut dinleyici + rol modeli (P0-3, P1-6);
   grup için `privacy mode` notu ve `/komut@BotAdı` desteği doğrulaması.
3. **Faz C — İçerik ve dil:** B9 kararı (grup ne görsün?), public şablon katmanı, dil sözlüğü,
   sabitlenmiş karşılama metni (P1-5, P1-7, P1-8, dil).
4. **Faz D — Açılış:** grup kurulumu (bot üye/admin, davet linki), ilk hafta gözlem, `PUBLIC_STATES`
   ve kalite eşiklerinin gerçek trafikle ayarı.

## 5) Kararlar (2026-10-02 görüşmesi)

| Konu | Karar |
|---|---|
| Dil | **Yalnız Türkçe** — i18n katmanı yapılmayacak, mevcut metinler korunur |
| Yapı | **Tek public supergroup** (ayrı kanal yok); bot alarmları yayınlar, sahibi ara sıra kendi mesajını yazar |
| Komut yetkisi | **Yalnız grup adminleri**; üyeler yayını görür, komut çalıştıramaz |
| Kurulum | Bot gruba **üye olarak** eklenir (yönetici yapılması GEREKMEZ, bkz. §7.1); env'de yalnız bot token + grubun chat_id'si tutulur |
| İçerik politikası | **AÇIK** — B9 kararı, uygulamadan önce konuşulacak (aşağıdaki seçenekler) |

### Açık konu: gruba hangi içerik gitsin? (B9)

Bugün gruba/kanala giden: `FORMASYON_TAMAMLANDI` + `RETEST_BASARILI` (global kalite ≥ 80) ve
09:55/18:45 temel özet. Gitmeyen: `KIRILIM_TEYITLI` (DM'de anında gidiyor), 18:45 izleme
digest'i, haftalık karne.

| Seçenek | İçerik | Artı | Eksi |
|---|---|---|---|
| A · Mevcut | Tamamlanan + retest ≥ 80 + 2 özet | Sıfır risk, en temiz | Çok seyrek; bazı günler 0 mesaj → grup ölü görünür |
| B · Teyitli dahil | A + `KIRILIM_TEYITLI` (TF bazlı eşik: 80/78/75/70) | Grubun görmek isteyeceği asıl olay; kalite kapısı zaten var | Anlık mesaj sayısı artar (günde birkaç) |
| C · İzleme dahil | B + sıkışma/kırılım adayı | Bilgi yoğun | Gürültü: günde 10-30 satır; gruplar için spam hissi |
| D · Özet ağırlıklı | 09:55 + 18:45 toplu özet + yalnız en güçlü 1-2 anlık | Gürültüsüz, büyük kitleye uygun | Anlık heyecan yok; gecikmeli bilgi |

**Öneri (tartışmaya açık):** **B + D karışımı** — anında yalnız `KIRILIM_TEYITLI`,
`FORMASYON_TAMAMLANDI`, `RETEST_BASARILI` (TF bazlı kalite eşikleriyle); izleme adayları günde
tek toplu bültende (18:45) ve **public'e özel, iç notlardan arındırılmış** metinle. Ayrıca
`PUBLIC_MIN_QUALITY` tek global eşik yerine DM'deki gibi TF bazlı olmalı ve grup için ayrı,
daha sıkı bir saatlik/günlük bütçe tanımlanmalı (örn. saatte ≤ 6, günde ≤ 25).

Karar verilmesi gereken iki nokta:
1. Yukarıdaki A/B/C/D'den hangisi (veya karışımı)?
2. Sahibin "ara sıra mesajı" kendi hesabından mı yazılacak (bot işi yok), yoksa bot üzerinden
   duyuru olarak mı gönderilsin (admin-only `/duyuru <metin>` komutu eklenir)?


## 6) Mesaj hacmi analizi (02.10.2026 gerçek gün)

Kullanıcının iletisi koddan sayıldı: **28 alarm + 2 özet = 30 mesaj** (DM yolu).

| Kategori | Adet | Not |
|---|---|---|
| 🏁 FORMASYON_TAMAMLANDI | 11 | KCHOL, ISMEN(×2), TAVHL, SNGYO, BIMAS, AYDEM, EREGL, THYAO, GARAN, TTRAK |
| ❌ BASARISIZ_KIRILIM | 9 | **Alarmların %32'si negatif** — public grup için itibar riski |
| ✅ KIRILIM_TEYITLI | 5 | TTRAK(×2), BRSAN, SKBNK, ODAS |
| 🎯 RETEST_BASARILI | 3 | EREGL, ISMEN, AKSEN |
| Özet/digest | 2 | 09:55 özeti + dünkü kaçırılan 18:45 özeti |

**Hacmin sebebi:** 4 zaman dilimi × 4 anlık state × TF bazlı eşik (1h:80 / 2h:78 / 4h:75 / 1d:70).
Tek fiyat hareketi 4 mesaj üretiyor (ISMEN gün içinde 4, TTRAK 4, KCHOL 3 kez bildirildi).
Kod içi politika değerleri son commit'te **değişmedi** (ALERT_STATES, eşikler, 4 saat cooldown,
20/saat + 120/gün kap aynı); son commit yalnız mum kapanış zamanlamasını düzeltti — yan etkisi
günün son 2h/4h kovasının (18:00) artık analiz edilmesi, yani akşam birkaç mesaj artabilir.

**Gruba mevcut public politikasıyla gidecek olan:** yalnız `FORMASYON_TAMAMLANDI`/`RETEST_BASARILI`
+ kalite ≥ 80 → yukarıdaki günden **9 alarm + 2 özet ≈ 11 mesaj**. `KIRILIM_TEYITLI` eklenirse
≈ 16-18. İzleme adayları da eklenirse 30+ (önerilmez).

## 7) Gruba eklerken çıkabilecek sorunlar (kontrol listesi)

### Kritik — bugün kodda böyle

1. **Botu grup yöneticisi yapmak sohbeti bozar.** Yönetici botlarda Telegram gizlilik modu devre dışı
   kalır ve bot **tüm grup mesajlarını** alır; kodda ise komut olmayan HER metne yardım metni cevabı
   var (test: `test_telegram_commands.py::test_komut_olmayan_metin_yardim_metni_gonderir`). Yani
   "grup sohbeti → bot her mesaja /yardim basıyor" durumu doğar.
   **Not:** Botun gruba mesaj atması için admin olması **gerekmez** (üye olması yeterli; yalnız kanalda
   admin şart). Admin yapmayın; komut yetkisi için `getChatAdministrators` (önbellekli) veya env'deki
   admin listesi kullanılmalı.
2. **Admin tespiti:** `getChatMember` yalnızca "bot sohbette yöneticiyse diğer kullanıcılar için
   garanti" (Bot API). Bu yüzden admin-kapısı için önerilen yol: `getChatAdministrators` + 5-10 dk
   önbellek; alternatif `TELEGRAM_ADMIN_IDS` (tek env).
3. **Grup → supergroup yükseltmesi `chat_id`'yi değiştirir**; kodda `migrate_to_chat_id` işleme yok →
   kayıtlı ID sessizce ölür. Çözüm: grup public ise `@kullanici_adi` ile gönder (API kabul eder) ya da
   taşınma güncellemesini yakala.
4. **Grup başına 20 mesaj/dakika** (Telegram Bots FAQ) + sohbet başına ~1 msg/sn. Bugünkü iletide
   11:30'da 9 mesaj aynı anda gitti; volatil günde 20+ olursa 429 alınır. `send_to_channel`'da
   pacing/retry/429 yok (DM `send_text` yolunda var).
5. **4096 karakter sınırı:** `send_to_channel` `kirp()` kullanmıyor → uzun özet 400 dönebilir.
6. **Sessiz kesinti:** bot gruptan atılırsa veya gönderim sürekli 403 alırsa hiçbir uyarı yok;
   hedef bazlı gönderim sağlığı eklenmeli.

### İçerik / algı

7. ❌ `BASARISIZ_KIRILIM` alarmların ~%32'si. Public grupta "bot sürekli yanılıyor" algısı yaratır;
   ya gruba hiç gitmesin ya akşam bülteninde toplu verilsin.
8. **Aynı hisse × 4 TF** tekrarı (ISMEN 4, TTRAK 4): grup için "hisse başına tek mesaj / aynı mum
   kapanışını tek mesajda birleştir" kuralı gürültüyü ~%60 azaltır.
9. `👀 Diğer izleme adayları` kuyrukları her alarmın altına ekleniyor; grup için gereksiz uzunluk.
10. `⏰ Kaçırılan kapanış özeti (01.10 18:45)` gibi eski damgalı telafi mesajları grupta "bozuk" görünür.
11. 09:55 özetindeki `📈 Gün: 0 hisse tarandı, 0 bildirim gönderildi` satırı sayaçların gece
    sıfırlanmasından geliyor (sabah henüz tarama yok) → grupta "bot ölü" izlenimi. Önceki günün
    toplamı gösterilmeli ya da satır kaldırılmalı.
12. Footer (`yatırım tavsiyesi değildir`) yalnız 4 state'te var; ❌ ve 👀 mesajlarında yok.
13. Forum/konu (topics) açık gruplarda bot mesajları "General"a düşer; belirli konuya göndermek için
    `message_thread_id` desteği gerekir (kodda yok).

### İşletim

14. Komutlar tek sohbete kilitli: grubu `TELEGRAM_CHAT_ID` yaparsan **kendi DM komutların susar**
    (çok sohbet desteği yok) — ya çok sohbet ya ayrı `TELEGRAM_KOMUT_CHAT_ID`.
15. Aynı token'la ikinci kopya → grupta çift mesaj; 409 koruması yalnız yoklama modunda.
16. Saatlik/günlük kap (20/120) yalnız DM yolunu sayıyor; grup hedefi için ayrı bütçe gerekir.
17. Grup public olacaksa: sabitlenmiş karşılama + "bu bir AL/SAT aracı değildir" + Telegram'ın
    "bot has access to messages" etiketi için şeffaflık metni hazırlanmalı.
