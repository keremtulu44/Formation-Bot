# Bot güvenlik ve çalışma kontrolü — 6 Kasım 2026

Bu not, yerel arşiv ve izole testlerde yapılan değişiklikleri özetler. Gerçek Telegram, Yahoo veya Supabase uçlarıyla canlı uçtan uca doğrulama değildir.

## Düzeltilen başlıklar

- **HTTP/webhook:** HTTPS webhook adresi ve sırlar doğrulanır; `/test` için `HEAD` mesaj göndermez; güvenlik başlıkları, gövde boyutu, tekil `Content-Length`, desteklenmeyen `Transfer-Encoding` ve eksik gövde kontrolleri vardır. `X-Forwarded-For` yalnız `HEALTH_TRUSTED_PROXY_CIDRS` ile açıkça güvenilen proxy zincirinde dikkate alınır, aksi hâlde soket adresi kullanılır. İstek sayacı sınırlı ve süreç içidir.
- **Telegram yetki ve teslim:** DM için pozitif sayısal hedef ve özel sohbet aranır. Grup komutlarında gerçek sohbet hedefiyle yönetici doğrulanır; `sender_chat`, anonim/bot kimliği veya farklı sohbet eşleşmesiyle yetki verilmez. Geçici yönetici doğrulama/cevap kayıt hataları ve bekleyen cevaplar webhook'ta `503` ile tekrar denemeye bırakılır; grup cevap hedefi korunur.
- **Grafik ve albüm:** Geçerli dosya/boyut sınırları ve sembolik bağlantı koruması var. Kesin reddedilmiş albüm fotoğrafları tek tek denenebilir; timeout, ağ, 429 veya 5xx belirsizse tekli tekrar yapılmaz. Eğitim sorusu belirsiz teslimde aktifleşmez ve kullanıcıya belirsizlik bildirilir. Grafik dosya yazımları atomik değiştirme kullanır.
- **Kalıcılık ve gizlilik:** Yerel JSON kayıtları atomik yazılır ve süreç içi kilitlerle korunur; public grafik snapshot'ları JSON'a uygun biçimde kaydedilip yüklenir. Supabase toplu sorgusunda anahtar alıntılama ve dönen satır filtresi sıkılaştırıldı. Hata ve loglarda sırların maskelenmesi korunur.
- **Stabil:** Dikey destek üzerinde yukarı çıkma denemesi `▲` yerine `▼` risk uyarısı olur. Yakın zamanda yukarı basamak yapmış fakat kırık destek rejimine geçmiş gerçek AEFES olayı da regresyon testidir. [Ayrıntı ve sınırlar](STABIL_DIKEY_UYARI_2026-11-05.md); [arşiv replay raporu](../arastirma/stabil_ok_replay_2026_11_05/RAPOR.md).

## Doğrulama

- Tam pytest: **3.541 başarılı, 43 atlanan** (izole ortam, 454,60 sn). Toplu tablo çıktısı ekleme değişikliğinden sonra rapor birim testleri ayrıca yeniden geçti.
- Bağımsız CI betikleri: `test_tarama_zamani.py` **102/102**; `test_triangle.py`, `test_breakout.py`, `test_flag.py`, `test_pennant.py` başarılı.
- İzole gerçek giriş noktası duman testi (`BOT_HEALTH_SMOKE_ONLY=1`): `GET /health` **200**, `HEAD /health` **200 ve boş gövde**, `/ready` **503**, yapılandırılmamış `/test` ve `POST /webhook` **404**. Smoke modunda sağlayıcı/tarama döngüleri bilerek kapalı olduğundan `/ready=503` beklenir. `nosniff`, `DENY`, `no-store` başlıkları gözlendi.
- Bağımlılıklar `requirements.txt` ve `requirements-dev.txt` ile kuruldu; ortam **Python 3.11.2**, proje hedefi **3.12**. 3.12 üzerinde çalıştırma ve gerçek dış servis entegrasyonları bu kontrolde doğrulanmadı.

## Önemli kalan sınırlar

- Yerel kilitler/dedup ve yanıt tekrar koruması tek süreçtedir; çoklu replika, süreç çökmesi veya yeniden başlatmada dağıtık kilit/exactly-once sağlamaz. Dosya sistemi veya JSON yazımı başarısızsa yeniden başlatma sonrası garanti yoktur.
- Albüm belirsizliğinde tekli fotoğraf fallback yapılmaması yinelenmeyi azaltır ama gönderim kaybı mümkün olabilir. Canlı dayanıklı bildirim outbox'ı belirsiz yanıt sonrası **albümün tamamını yeniden deneyebilir**: at-least-once davranışla çift albüm mümkündür. Tekrar eden metin teslimi de ağ belirsizliğinde tamamen dışlanamaz.
- HTTP rate limit süreç içidir; proxy zinciri yanlış güvenilirse gerçek IP ayrımı bozulur. Soket timeout tek başına yavaş veri damlatma/slowloris savunması değildir; internete açık dağıtımda ters proxy bağlantı ve hız limitleri ayrıca yapılandırılmalıdır.
- Grafik/ok araştırması arşiv ve gözlemsel proxy verileridir; çizimde dikeylik için kullanıcının bağımsız görsel etiketleri yoktur ve `▼` düşüş garantisi değildir. Kaynak veri eksik seanslar ve sağlayıcı düzeltmeleri bakımından bağımsız olarak doğrulanmamıştır.
