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

## 5) Karar bekleyen sorular

1. Grup hangi dilde olacak: **yalnız Türkçe** mi, **Türkçe + İngilizce** (uluslararası) mu?
2. Grup tipi: **duyuru ağırlıklı supergroup** mu (üyeler yazabilir), yoksa **grup + ayrı kanal** mı?
3. Üyeler bot komutu kullanabilsin mi: **herkes**, **yalnız adminler**, yoksa **hiç kimse** (salt okunur yayın)?
4. Gruba hangi içerik gitsin: **mevcut politika** (tamamlanan + retest, kalite ≥ 80) mi, yoksa
   **kırılım teyitli/adayı da dahil** daha zengin akış mı?
