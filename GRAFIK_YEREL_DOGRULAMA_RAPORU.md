# Grafik sistemi — yerel inceleme ve doğrulama

Tarih: 14 Ekim 2026. Yalnız yerel değişiklik; commit/push/PR/merge/deploy yok. Canlı Render, Yahoo veya Telegram çağrısı yapılmadı. Sırlar ve `.env` incelenmedi/değiştirilmedi. Test çalıştırıcısında `load_dotenv` devre dışı bırakıldı; test taşıması/sağlayıcısı monkeypatch edildi.

## 1. Değişiklik öncesi veri yolu haritası ve ölçüm

`main._komut_grafik` → `grafik_uret.kare_uret(zone=True)` → `_veri_dizini(None)` → yeni `StockDequeManager(data_dir=...)` → JSON/seed okuma → resample → domain motorları → snapshot → PNG → `notifier.grafik_dosya_gonder`.

Komut önceden listener içinde senkron çalışıyordu; kabul yanıtı yoktu. Botun `_deque_manager_ref` nesnesi kullanılmıyordu. `_veri_dizini` kendi env/repo fallback'ini uygularken tarayıcı `config.DATA_DIR` varsayılanını kullanıyordu.

Aşağıdaki değerler değişiklikten **önce**, ayrı Python süreçleriyle ölçüldü. Render satırı yalnız `RENDER=true` ile yerel ortam simülasyonudur; canlı sunucu ölçümü değildir.

| Ortam | config.DATA_DIR = StockDequeManager varsayılanı | grafik_uret._veri_dizini(None) |
|---|---|---|
| DATA_DIR/RENDER yok, bu sandbox | `/home/user/.formation-bot/data` | `/home/user/Formation-Bot/bot_data` |
| RENDER=true, DATA_DIR yok | `/tmp/formation-bot-data` | `/home/user/Formation-Bot/bot_data` |
| DATA_DIR=/tmp/fbdata | `/tmp/fbdata` | `/tmp/fbdata` |
| DATA_DIR=relative/path | `/home/user/Formation-Bot/relative/path` | `relative/path` (cwd'ye bağlı) |

`SEED_DATA_DIR` bu ölçümlerde `/home/user/Formation-Bot/bot_data`. `StockDequeManager._okuma_yolu`: önce aktif veri dizini, yalnız dosya yoksa seed; mevcut fakat bozuk aktif JSON yerine sessizce seed'e geçmez. Seed yalnız okuma yedeğidir. `save_to_disk` saatlik JSON'u yöneticinin `data_dir/<SEM>.json` yoluna, günlük kayıt `save_gunluk_to_disk` ile `<SEM>_gunluk.json` yoluna yazılır. Supabase hidrasyonu aynı yöneticinin belleğini doldurur.

Ana tarayıcı `main_loop` içinde `StockDequeManager(persistent_store=...)` kurar; tarama/yükleme saatlik cache'i bu yöneticide birleştirir ve aktif dizine kaydeder. Grafik komutunun bu belleği görmemesi, diskten eski/eksik veri okumasına ayrıca yol açıyordu. Günlük cache'in bellekte olup henüz dosyada olmaması da aynı nedenle görünmezdi.

`/opt/render/project/src/bot_data/SEM.json` aramasının koddan doğrulanan nedeni: env DATA_DIR yokken grafik üreticinin `__file__` yanındaki `bot_data` fallback'i. Render'daki gerçek DATA_DIR/env/disk durumu bu oturumda erişilmedi; yol uyuşmazlığı **koşulludur**, tüm kurulumlarda varmış gibi iddia edilmez. Açık mutlak DATA_DIR verilmişse yollar zaten eşitti.

Repodaki AKBNK/THYAO dosyaları 360 kayıt; son saatlik mum `2026-09-25T17:30:00+03:00`. `SEM.json` yok. Bu seed bugün güncel piyasa verisi değildir. Gerçek seed üzerinde yerel resample ölçümü: 1h=360, 2h=200, 4h=120, 1d=40 mum; günlük derin dosya yok. CLI tarihsel cache çizebilir; `/grafik` ise artık yaş kapısını uygular ve bu eski seed'i başarı diye göndermez.

## 2. Uygulanan komut akışı

1. Sembol/TF doğrulanır. TF belirtilmişse yalnız **bir sembol × bir TF**; belirtilmemişse yalnız o sembolün dört TF'si. Evren taraması, lifecycle alarmı veya sağlayıcı fetch'i yok.
2. Handler `ArkaPlanYaniti` ile hemen “Grafik isteği alındı, hazırlanıyor” döner. Listener kabul mesajı teslimi (varsa dayanıklı cevap kuyruğunun onayı) başarılı olduktan sonra işi başlatır. Teslim başarısızsa callback korunur, retry'da handler yeniden çalışmaz; başlatma idempotenttir.
3. Tek daemon worker; aynı sembol/TF çakışması açık yanıtla reddedilir. Farklı grafik işi de sınırsız thread/kuyruk yaratmaz: mevcut iş bitince tekrar istenir. Genel tarama meşguliyet kapısı yalnız `/grafik` ve `/g` için atlanır; diğer komutların davranışı değişmez.
4. Mevcut `_deque_manager_ref` varsa aynı bellek/cache katmanından kopya frame alınır; yoksa ortak `config.DATA_DIR` üzerinden yüklenir. Günlük derin veri varsa önce o kullanılır, yoksa saatlik resample. Kaynak gerçek dosya yolu veya bellek/dizin olarak raporlanır.
5. Kapanmamış mumlar domain motorlarına verilmeden çıkarılır. Komut yaş kapısı, mevcut 120 dk/seans içi ve 14 gün/seans dışı politikasını seçilen TF'nin **son mum kapanışından** hesaplanan yaşa uygular. Eski/eksik veri açıklamalı hata verir; sentetik fallback yoktur.
6. `zone=True` seçilen TF'de mevcut domain runner'ı kullanır, formasyon lifecycle'ını taramaz. Frame kopyadır. Runner'ın kendi seri-kilitli OB/FVG süreç içi registry'si kullanılır; motorların bütünüyle ayrı bir subprocess/registry'de çalıştığı iddia edilmez. Formasyon kaydı verilmediyse bant uydurulmaz; bu uyarı sonuçta görünür.
7. 60 sn hedefi aşılırsa timer, “henüz bitmedi” ve cache/resample, seçilen TF motorları, PNG/kilit veya DM sendPhoto aşamasını bildirir. Bu **sert iptal timeout'u değil**, aşama bildirimidir. İş kapsamı sınırlıdır; listener motor/render süresini beklemez. Matplotlib global durumu otomatik/manuel çizimler arasında ortak kilitle korunur.
8. Fotoğraf başarıyla teslim edilirse “Bitti”; başarısızsa sendPhoto nedeni, çizim reddi veya hata aşaması/türü; dört TF'de kısmi başarı ayrı ifade edilir. Son bar/kaynak/eksik katmanlar raporlanır. PNG, üretim reddi/kısmi dosya/istisna/gönderim başarısı veya hatasında silinir; atomik geçici yazım dosyası da temizlenir.

**Fetch kararı:** Ortak `fetch_yfinance_1h` yolu mevcut, ama güvenli temposu `scan_all_stocks` tarafından oluşturulan tarama-başına pacer üzerinden çalışıyor; süreç-geneli ortak provider kuyruğu değil. Soğuk/eski cache 60d, rutin cache 5d ister. Rate-limit/ağ hatasında tek retry öncesi 30–60 sn backoff; istekler arası 0,9–1,5 sn, her 10 istekte 10–15 sn mola. `history` çağrısına burada toplam grafik deadline'ı geçirilmez. Yeni grafik thread'inden ikinci pacer/fetch çağırmak taramayla eşzamanlı rate-limit koruması sağlamaz ve yaklaşık bir dakika sözü verilemez. Bu nedenle bağımsız fetch icat edilmedi; eksik/eski cache açık hata olarak sonlandırılır.

## 3. Demo ile gerçek veri doğrulaması birbirinden ayrı

`--demo` artık açıkça **cache okumadan** deterministik sentetik frame üretir. Gerçek cache bulunsa dahi demo sentetiktir; kaynak `demo (sentetik)` olarak işaretlenir. StockDequeManager kurulmaz, JSON yazılmaz. Demo PNG hedefi `bot_data` altında ise işlem reddedilir (çözümlenmiş yol kontrolü).

Demo yalnız snapshot/render→PNG zincirini ve istenirse sentetik frame üzerindeki motor/katman çizimini doğrular. Gerçek JSON doğruluğu/tazeliği, DATA_DIR/seed fallback, Supabase hidrasyonu, Yahoo, tarama köprüsü veya Telegram teslimini **doğrulamaz**.

Yerel ayrı CLI dumanları (çıktılar /tmp'de, Git'e eklenmedi):

| Yol | Sonuç |
|---|---|
| SEM 4h --demo, zone yok | 180 mum PNG; 49,4 KB; çizim 641,2 ms; kaynak demo (sentetik) |
| AKBNK 4h --veri-dizin bot_data, demo/zone yok | tarihsel gerçek cache; 120 mum PNG; 52,4 KB; çizim 561,2 ms; gerçek kaynak yolu meta'da |

Bu süreler yalnız yerel **çizim** süresidir; canlı komut veya Telegram uçtan uca süre garantisi değildir. İkinci duman eski gerçek verinin çizilebildiğini gösterir; bugün taze olduğunu göstermez.

## 4. Otomatik alarm görselleri — veri, sıra, hedef ve gözlem

Mevcut akış korunur:

`_attach_domain_context` → `_grafik_koprusu` → `payload.grafik_verisi` → başarılı `_gonder/sendMessage` → `grafik_kuyruga_ekle` → tarama sonunda `_public_turu_kapat` ardından `_grafikleri_tur_sonunda/grafikleri_gonder` → `kareyi_yaz` → `grafik_dosya_gonder` → `foto_gonder/sendPhoto`.

- Köprü, o turdaki **tamamlanmış TF frame'leri**, aynı aktif formasyon/snapshot ve kartın domain çıktılarından kopya görüntüler kurar; motorları çizim için tekrar çalıştırmaz. Birincil TF ilk karedir. Bant/alarm indeksleri yalnız o TF'ye çizilir; ek TF'lerde uydurma bant/alarm yoktur.
- TELEGRAM_GRAFIK yok/yok değerinde otomatik görüntü yok; dört mevcut grafik env anahtarı korunur, yenisi eklenmedi. `/grafik` şalterden bağımsızdır.
- Metin HTTP 200 aldıktan sonra görüntüler bellekte kuyruğa girer. Fotoğraf **aynı sendMessage'a eklenen attachment değildir**: her kare ayrı `sendPhoto` mesajıdır, kısa kimlik caption'ı taşır; metin kartı tekrarlanmaz. İş sözleşmesi bir alarm metni + yardımcı karelerdir; Telegram sohbetinde fiziksel olarak ek fotoğraf mesajları görünür.
- Kuyruk tur sonuna kadar bekler; ilk semboldeki alarm görseli tüm sonraki sembollerin fetch/analiz ve public bültenini bekleyebilir. “Metinden sonra anında fotoğraf” veya otomatik alarmda bir dakika garantisi yoktur. Snapshot beklerken yeni cache'den yeniden kurulmaz.
- `sinir` kare bazlıdır: limit dışındaki kareler sonraki boşaltmaya kalır. Kuyruk yalnız bellektedir; restart'ta kaybolur. Notifier pasifken boşaltma görüntüleri üretmeden düşürür; disk <200 MB veya import sorunu atlama/hata sayılır. Bu mevcut davranışlar değiştirilmedi.
- Fotoğraf yalnız notifier DM chat_id hedefine gider, public bülten yolunu kullanmaz. Ek güvence olarak negatif/grup veya @hedef ve public_chat_id ile aynı hedef artık fotoğraf için reddedilir; PNG yine temizlenir. Alarm metni/public yayın politikası değişmedi.
- Fotoğraflar `max_gunluk`/`max_saatlik` metin kaplarını tüketmez. Metin, kota ve alarm tekilleştirme sözleşmesi değiştirilmedi.
- Bağlam değişmedi kısa DM güncellemesinde kare yeniden eklenmez (`grafik_atlanan_baglam`).
- Acil alarm kap/cooldown nedeniyle disk kuyruğuna alınırsa `_kuyruk_verisi` **grafik_verisi'ni atar** (DEBUG izi). Kuyruktan teslimde `_kuyruktan=True`; eski kare yeniden kurulmaz, normal olay/karesiz sayaçlarına girmez. Acil kuyruktan metin gelip görsel gelmemesi bilinçli davranıştır.

Gözlem yüzeyleri (`/durum`, `gonderim_durumu`, heartbeat ve log):

| Alan | Anlam |
|---|---|
| grafik_olay | şalter açıkken başarıyla gönderilmiş normal DM alarm metni |
| grafik_olay_karesiz | bu metinlerden payload/goruntular alamayanlar; acil kuyruk hariç |
| grafik_kopru_hata / grafik_son_neden | köprü istisna sayısı, redakte 120 karakter son neden; ilk WARNING, sonra DEBUG |
| grafik_kuyruk | bekleyen kuyruk kayıtları; kayıtlar birden fazla kare taşıyabilir |
| grafik_gonderilen / grafik_atlanan_hata | fotoğraf başarı/hataları; komut teslimi de aynı sayaçları kullanır |
| grafik_atlanan_kota | TELEGRAM_GRAFIK_ADET yüzünden kesilen kareler; metin kotası değil |
| grafik_atlanan_baglam | kısa bağlam güncellemesi nedeniyle atlanan tekrar kareler |
| grafik_ort_ms | başarılı otomatik karelerin meta çizim sürelerinin ortalaması; kuyruk/ağ beklemesi dahil değil |
| daily_stats.grafik_kare / grafik_hata | tur sonunda otomatik teslim özetinden eklenen günlük değerler |

Köprü hatası alarmı düşürmez. sendMessage hatası fotoğraf kuyruğu açmaz. Çizim reddi/PNG yokluğu/sendPhoto hatası loglanır ve sonraki kareye geçilir. Yerel testler sırayı ve sayaçları gözlemler; canlı otomatik alarm zamanları/hedefleri bu oturumda dışarıdan ölçülmedi.

## 5. Testler ve değişen dosyalar

Yeni `test_grafik_istegi.py`: ortak config/göreli path; demo cache'e dokunmama ve bot_data çıktı reddi; gerçek JSON aktif dizin önceliği/seed fallback; disk dosyası olmayan SEM için mevcut bellek kullanımı ve yalnız 4h motor çağrısı; kabul sonrası tamamlanma; eksik/eski cache; aynı/başka iş çakışması; sendPhoto hata/istisna; üretim istisnası/çizim reddinde temizlik; hedef aşımında aşama; listener kabul retry'sında tek başlatma ve tarama meşgulken grafik kabulü.

`test_grafik_teslim.py` senkron komut beklentileri asenkron sözleşmeye uyarlandı. Ek entegrasyon: sendMessage 200/403 → kuyruk → tur sonu fotoğraf, DM hedefi, PNG temizliği ve görselin metin kotasını tüketmemesi. Yanlış grup/public CHAT_ID için fotoğraf reddi. Mevcut köprü, acil kuyruk, caption/metin paritesi ve şalter testleri de kapıda çalıştı. `test_grafik_iskelet.py` gerçek kaynak yolu beklentisi güncellendi.

Son kapı, requirements.txt bağımlılıklarıyla geçici venv içinde:

```sh
# Venv PATH etkin; yalnız test harness'i load_dotenv'i devre dışı bırakır.
DATA_DIR=/tmp/fbdata python -m pytest -q
# 1038 passed, 44 skipped in 183.98s
```

İlk odaklı kapı: 155 passed. Son tam kapı yukarıdaki tüm düzeltmeleri içerir. Skipped testler pytest'in mevcut atlamalarıdır; canlı Yahoo/Telegram/Render doğrulaması yapılmış sayılmaz.

Değişen dosyalar: `grafik_uret.py`, `grafik.py`, `main.py`, `telegram_commands.py`, `notifier.py`, `test_grafik_istegi.py` (yeni), `test_grafik_teslim.py`, `test_grafik_iskelet.py`, bu rapor (yeni). Config/env/deploy dosyaları ve `bot_data/*` değiştirilmedi.

## 6. Bilinen sınırlar

- Yaklaşık bir dakika hedefi soft deadline'dır; motor/render beklerse durum bildirilir, thread zorla öldürülmez. Manuel işler sınırsız kuyruklanmaz.
- İş/callback süreç içidir: restart sırasında yarım grafik isteğinin tamamlanması için dayanıklı job outbox eklenmedi. Telegram durum mesajı da dış servis arızasında ulaşamayabilir; hata loglanır, sahte teslim başarısı üretilmez.
- Yöneticiden frame alırken tarama eşzamanlı deque değiştirirse okuma istisnası açık aşama/tür hatası olarak sonuçlanır; tarama verisine veya cache'e grafik için yazılmaz.
- Gerçek cache okuma ve local render doğrulandı; canlı provider tazeliği ve gerçek DM teslimi bu oturumun güvenlik kapsamı dışında bırakıldı.
