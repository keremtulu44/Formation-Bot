# Reproducible ASTOR context sample

- Snapshot cutoff: `2026-10-16T13:30:00+03:00`; last completed H4 close: `183.20`.
- The selected H4 archive contains `1075` completed bars through the cutoff; later bars are not passed to the four standard domain engines.
- Stabil receives the archive frames with `as_of_close=2026-10-16T13:30:00+03:00` and returns its native as-of output.
- The replay candidate anchor is a bar-open label at `2026-10-16T13:30:00+03:00`; its candle closes at `2026-10-16T17:30:00+03:00`, after the cutoff.
- Therefore no replay trigger, strength/quality fields, confirmation, or outcome from that candidate row is included in this packet.
- Replay findings below are separate research knowledge. Each one is labeled with report/data timing; post-cutoff findings were not knowable at this snapshot.
- `trigger` is intentionally null: this example demonstrates an on-demand historical request, not a delivered alarm.

## Readable context packet

# ASTOR 4h · domain context
Kesit: 2026-10-16T13:30:00+03:00 · tür: historical_sample · referans kapanış: 183,20 · fiyat zamanı: 2026-10-16T13:30:00+03:00
Tamamlanmış mum sayısı: 1075.
Tetikleyici: manuel/on-demand istek; alarm olayı eklenmedi.
## Piyasa yapısı · 4h
Dış: STATE_BEARISH (aşağı), kalite 86/100; son EVENT_SWEEP yukarı @ 2026-10-16T06:30:00+00:00, ilişki=CURRENT, geçerlilik=VALID, seviye 176,00
İç: STATE_BEARISH (aşağı), kalite 84/100; son EVENT_BOS aşağı @ 2026-09-15T06:30:00+00:00, ilişki=CURRENT, geçerlilik=VALID, seviye 282,50
Korunan/zayıf seviyeler: external_protected_high=306,75; external_weak_low=176,00; internal_protected_high=297,75; internal_weak_low=235,20
Replay bağlamı (bu sembolün olasılığı değildir):
- 4h dış BOS takip ölçümü: Seçili 4h EXTERNAL BOS grubunda n=3.387 olay için yön uyumu %98,0, rapor tanımındaki CALISTI oranı %71,0, devam-yok %7,5 ve ters yön %0,9 idi.
  Kapsam: 176 sembol / 704 seri; TF=4h; dönem=2025-05-07 .. 2026-10-19 intraday arşivi; birim=onaylanmış Market Structure olayı; run_id=replay-2026-10-21.
  Zaman: kayıt=2026-10-21; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.
  Örneklem: n=3.387 seçilmiş 4h dış BOS olayı.
  Yöntem: Ölçüm çapası confirmed event_bar'dır; candidate_bar değildir. Sonraki 12 native mumdaki sonuçlar ATR ile normalize edilmiştir.
  Sınır: Bu hücre yalnız 4h dış BOS'tur; iç yapı, CHOCH, sweep ve diğer TF'ler farklıdır. Direction alignment ile forward CALISTI ayrı ölçülerdir; biri diğerinin garantisi değildir. BIST havuzundaki geçmiş olaylar mevcut sembolün başarı olasılığı değildir. İşlem maliyeti, emir gerçekleşmesi veya portföy getirisi ölçülmedi.
  Kaynak: docs/arastirma/REPLAY_OZET_2026-10-21.md §8; docs/arastirma/ARASTIRMA_HATTI.md §'Ölçüm sözleşmesi'
## Hacim / katılım · 4h
Veri/çıktı durumu: PARTICIPATION_UP_BREAK_SUPPORTED
durum: PARTICIPATION_UP_BREAK_SUPPORTED
RVOL: 2,247×
göreli işlem değeri: 2,040×
hacim sınıfı: HIGH
sermaye sınıfı: HIGH
motor kalitesi: 38,9/100
efor/sonuç: NEUTRAL
katılım aşaması: CLOSED
kırılım aşaması: SUPPORTED
kırılım seviyesi: 119,70
emilim aşaması: NONE
yüksek çatışma: False
tek mum şoku: False
Replay bağlamı (bu sembolün olasılığı değildir):
- Hacim etkisi koşula göre farklı yönlü: 4h zone-temas grubunda Q4 yüksek RVOL tepkisi Q1'den düşüktü (%61,0 vs %70,1); ayrı 4h MS-event grubunda Q4 devamı Q1'den yüksekti (%69,5 vs %66,1).
  Kapsam: 176 sembol / 704 seri; TF=4h; dönem=2025-05-07 .. 2026-10-19 intraday arşivi; birim: zone=temas epizodu; MS=onaylanmış Market Structure olayı; rapor tablosunda run_id kaydedilmemiş.
  Zaman: kayıt=tarih yok; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Rapor tarihi/run_id tabloda yok; ölçüm dönemi kapsamda 2026-10-19'a kadar uzanır.
  Örneklem: 4h zone-temas: Q1 n=6.740, Q4 n=11.928; 4h MS-event: Q1 n=5.233, Q4 n=8.248. Kohortlar ayrı ve toplanamaz.
  Yöntem: RVOL çeyrekleri olay ailesine göre ayrı hesaplanmıştır. Zone-temas tepkisi ve MS-olayı devamı farklı kohort ve farklı ölçüm sorularıdır.
  Sınır: Bu iki karşıt sonuç tek bir 'yüksek hacim iyi/kötü' kuralına indirgenemez. Q1/Q4 arşiv kovalarıdır; canlı RVOL eşlemesi yaklaşık olabilir. MS-event n'si ile zone-touch n'si aynı birim değildir ve toplanamaz. Hacim verisinin bazı sembol/etiket kalitesi ayrıca sınırlıdır. 2026-10-28 tarihli 177 sembol/708 seri DZ yenilemesi ayrı bir popülasyondur; bu bulgu onunla birleştirilmemiştir.
  Kaynak: docs/arastirma/ARASTIRMA_BULGULARI.md §'Hacim — koşullandırma değişkeni'; docs/arastirma/ARASTIRMA_SONUCLARI.md §'Hacim'; docs/arastirma/AMPIRIK_REFERANS.md §'RVOL çeyreği yaklaşıktır'
## Order Block · 4h
Veri/çıktı durumu: OK
Kayıt: 26; aktif kayıt: 25.
En yakındaki 5 aktif OB (tam liste JSON native alanındadır):
- bearish 194,60–199,20; oluşum 2026-10-14T10:30:00+00:00; imbalance=True; dolum sınırı=194,60
- bearish 203,90–214,50; oluşum 2026-10-09T10:30:00+00:00; imbalance=True; dolum sınırı=207,60
- bullish 149,00–155,70; oluşum 2026-02-06T10:30:00+00:00; imbalance=True; dolum sınırı=152,90
- bullish 145,60–151,10; oluşum 2026-01-22T06:30:00+00:00; imbalance=True; dolum sınırı=149,00
- bullish 138,60–149,60; oluşum 2026-01-21T10:30:00+00:00; imbalance=True; dolum sınırı=145,60
Replay bağlamı (bu sembolün olasılığı değildir):
- OB + FVG ortak temas tepkisi: 240.484 temas epizodunda, beklenen yönde en az 1 ATR tepki oranı zaman dilimine göre %65,0–%66,5 aralığındaydı.
  Kapsam: 176 sembol / 704 seri; TF=1h, 2h, 4h, 1d; dönem=2025-05-07 .. 2026-10-19; birim=OB/FVG temas epizodu; run_id=replay-2026-10-21.
  Zaman: kayıt=2026-10-21; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.
  Örneklem: n=240.484 temas epizodu; OB ve FVG birlikte.
  Yöntem: Temas epizodu başına, çapadan sonraki native mumların fiyat yolu ATR ile ölçüldü; CALISTI eşiği beklenen yönde >=1 ATR uzanımdır.
  Sınır: Sonuç OB ve FVG temaslarını birlikte özetler; aileye özel oran değildir. Zaman dilimleri arası aralık tek bir sabit oran değildir. Havuz düzeyindeki tarihsel sıklık bu sembolün olasılığı değildir. Maliyet, pozisyon, emir gerçekleşmesi veya kârlılık ölçülmedi.
  Kaynak: docs/arastirma/REPLAY_OZET_2026-10-21.md §3; docs/arastirma/ARASTIRMA_HATTI.md
- Order Block temas ve yaşam döngüsü: 131.901 OB zone'un %10,7–%13,3'ü TF'ye göre en az üç temas epizodu gördü; zone düzeyinde fiyat ihlali oranı %85,4–%93,6 aralığındaydı.
  Kapsam: 176 sembol / 704 seri; TF=1h, 2h, 4h, 1d; dönem=2025-05-07 .. 2026-10-19; birim=OB zone; temas ayrıca epizot olarak sayılır; zone n=131901; temas epizodu n=197521; run_id=replay-2026-10-21.
  Zaman: kayıt=2026-10-21; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.
  Örneklem: n=131.901 OB zone; ayrıca n=197.521 temas epizodu.
  Yöntem: OB zone yaşam döngüsü native bar bar izlendi; terminal fiyat ihlali ölçüldü. OB için native_full_fill alanı yapısal olarak False olduğundan geçilme metriği native_price_violation'dır.
  Sınır: TF aralıkları birbirinden ayrı hücrelerdir; toplam oran diye okunmamalı. Fiyat ihlali, kalıcı bariyer olmadığını anlatır; tek temas tepkisini silmez. Bunlar geçmiş BIST havuzunun betimsel sayımlarıdır, ASTOR/SNGYO'ya özel değildir.
  Kaynak: docs/arastirma/REPLAY_OZET_2026-10-21.md §2–4; docs/arastirma/ARASTIRMA_SONUCLARI.md §1–2; docs/arastirma/ARASTIRMA_HATTI.md §'Bulunan iki survivorship tuzağı'
## FVG · 4h
Veri/çıktı durumu: OK
Geçmiş formasyon kaydı: 179.
Boğa yönünde aktif FVG kaydı yok.
Ayı yönünde aktif FVG kaydı yok.
Replay bağlamı (bu sembolün olasılığı değildir):
- OB + FVG ortak temas tepkisi: 240.484 temas epizodunda, beklenen yönde en az 1 ATR tepki oranı zaman dilimine göre %65,0–%66,5 aralığındaydı.
  Kapsam: 176 sembol / 704 seri; TF=1h, 2h, 4h, 1d; dönem=2025-05-07 .. 2026-10-19; birim=OB/FVG temas epizodu; run_id=replay-2026-10-21.
  Zaman: kayıt=2026-10-21; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.
  Örneklem: n=240.484 temas epizodu; OB ve FVG birlikte.
  Yöntem: Temas epizodu başına, çapadan sonraki native mumların fiyat yolu ATR ile ölçüldü; CALISTI eşiği beklenen yönde >=1 ATR uzanımdır.
  Sınır: Sonuç OB ve FVG temaslarını birlikte özetler; aileye özel oran değildir. Zaman dilimleri arası aralık tek bir sabit oran değildir. Havuz düzeyindeki tarihsel sıklık bu sembolün olasılığı değildir. Maliyet, pozisyon, emir gerçekleşmesi veya kârlılık ölçülmedi.
  Kaynak: docs/arastirma/REPLAY_OZET_2026-10-21.md §3; docs/arastirma/ARASTIRMA_HATTI.md
- FVG temas sıklığı: 55.145 FVG zone'un 12.680'i (%23,0) gözlenen arşivde hiç temas almadı; 3+ temas yalnız 4 zone'da (%0,007) görüldü.
  Kapsam: 176 sembol / 704 seri; TF=2h, 4h, 1d; dönem=2025-05-07 .. 2026-10-19; birim=FVG zone; temas ayrıca epizot olarak sayılır; zone n=55145; temas epizodu n=42963; hariç=1h (bu replay hattı 1h FVG üretmiyor); run_id=replay-2026-10-21.
  Zaman: kayıt=2026-10-21; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Replay özeti 2026-10-21 olarak tarihli; kapsam intraday arşivini 2026-10-19'a kadar verir.
  Örneklem: n=55.145 FVG zone; temas ölçümünde 42.963 epizot; 3+ temaslı 4 zone.
  Yöntem: FVG zone'ları native lifecycle boyunca, temas epizodu sayısıyla izlendi. FVG tekrar temas oranları zone düzeyinde; temas tepkisi ortak OB+FVG temas tablosundan ayrı tutulur.
  Sınır: FVG replay kapsamı 2h/4h/1d'dir; 1h için sonuç yoktur. Arşiv penceresinde hiç temas almamak gelecekte de temas olmayacağı demek değildir. Bir sembolün mevcut FVG'si için olay-bağımsız olasılık üretmez.
  Kaynak: docs/arastirma/REPLAY_OZET_2026-10-21.md §2, §4; docs/arastirma/ARASTIRMA_SONUCLARI.md §1
## Stabil · 4h
Veri/çıktı durumu: OK
Son kapanış 183,20; destek ilişkisi=destek üstünde.
Destek=172,10, taban=165,51; seviye zamanı=2026-10-15T18:30:00+03:00, geçerlilik=ACTIVE, dinamik=CONTRACTING, ilerleme=REBASED_LOWER, uzaklık=6,45% / 0,67 ATR; destek yaşı=6 mum.
Trend bağlamı: weekly=WEEKLY_NOT_UP (hazır=True, kullanılabilir=True); daily=DAILY_PULLBACK_TOO_DEEP (hazır=True, kullanılabilir=True); h4=H4_BUYERS_EMERGING (hazır=True, kullanılabilir=—)
Rol hazırlığı: daily_support=READY; weekly_trend=READY; daily_trend=READY; h4_trend=READY
Son mum davranışı: rejim=HORIZONTAL_AFTER_DROP, temas sayısı=0, hacim oranı=2,220×, geri-alım türü=intrabar_sweep_reclaim.
Replay bağlamı (bu sembolün olasılığı değildir):
- Stabil desteğinde bağımsız temas sırası (C02): 8×4h tam ufukta ilk/ikinci/3+ temas gruplarının medyan korunan kapanış değişimi sırasıyla -0,066 / +0,155 / -0,376 ATR idi; 3+ grup küçük ve yoğundur.
  Kapsam: sembol aralığı=AEFES .. KONTR (seçilmiş arşiv hisseleri, alfabetik); aday rejim eşlemesi kullanıcı teyitli değil; birim=bağımsız destek-temas olayı; arada en az 0,35 günlük ATR; 4h kesiti n=107441; ilk görülen destek olayı n=10417; soru n=48; tablo satırı n=642; run_id=stabil-bhv48-2026-11-01.
  Zaman: kayıt=2026-11-01; veri sonu=bilinmiyor; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Manifest 2026-11-01'de üretildi; kaynak veri sonu manifestte kayıtlı değil.
  Örneklem: Toplam n=1.976; tam 8×4h ufuk n=1.943; sansürlü n=33; ilk/ikinci/3+ gruplar n=1.773/137/33.
  Yöntem: Arşiv Stabil davranış replay'i tamamlanmış 4h kesitleri, nedensel günlük/haftalık girdiler, girişte sabitlenen günlük ATR ve açık sağ-sansürleme kullanır. C02, aralarında en az 0,35 günlük ATR bulunan bağımsız temasları sayar.
  Sınır: 3+ temas kovası n=33 ve tek sembol payı %81,8; genellenebilir sonuç gibi okunmamalı. İlk arşiv epizodunun temas yaşı bilinmeyebilir; unknown başlangıçlar dışlanır. Bu 100-sembol davranış araştırmasıdır; anlık alarmın ya da canlı bildirimin kaydı değildir. Aday dikey/yatay rejim kullanan B01–B06 bölümleri kullanıcı teyidi bekler; bu pakette kural gibi sunulmaz. Manifest kaynak/veri hashlerini, kesin veri kesim zamanını ve tam native checkpoint paketini içermiyor.
  Kaynak: docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_YANITLARI.md §STB-BHV-C02; docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_MANIFEST.json; research/stabil_replay.py; research/stabil_bhv48.py
- Stabil canlı-evren geri-alım systematic arşiv testi: Arşivde bulunan 50/53 canlı non-macro sembolde 284 sinyal / 75,9 hafta: sonraki 4h kapanışta destek üstünde kalma %91,5; 8×4h medyan kapanış değişimi +0,262 ATR idi.
  Kapsam: 50 sembol / 50 seri; TF=4h; dönem=2025-05-07 .. 2026-10-19; birim=6 bar cooldown sonrası Stabil geri-alım olayı; rapor tablosunda run_id kaydedilmemiş.
  Zaman: kayıt=tarih yok; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Sonuç JSON'ı çalışma tarihini yazmıyor; veri aralığı 2026-10-19'da biter.
  Örneklem: Toplam sinyal n=284; getirilerin her ufkundaki geçerli alt-n aggregate JSON'da ayrıca yayımlanmamıştır.
  Yöntem: Tarihsel arşiv çalışması tamamlanmış 4h mumlarda Stabil geri-alım davranışını ölçer; sinyaller arasında 6 mum cooldown uygulanır. Sonraki-mumda tutunma, bir sonraki 4h kapanışının sinyal destek seviyesine göre kontrolüdür; 8×4h kapanış değişimi giriş ATR'siyle ölçülür.
  Sınır: 53 canlı non-macro sembolün yalnız 50'si arşivdeydi; XU50, XBANK ve XUSIN yoktur. Sonraki mum destek tutunması ve ATR-normalize kapanış değişimi betimsel fiyat yolu ölçüleridir; gerçekleşmiş işlem/kârlılık değildir. Erken/geç yarı medyanları (+0,426 ve +0,020 ATR) farklıdır; toplu değeri sabit kabul etmeyin. Bu systematic çalışma 100-sembol/48-soru davranış replay'inden ayrıdır ve onunla birleştirilemez. Aggregate JSON'da kesin koşu tarihi, kaynak hashleri, sinyal bazlı native paket, emir/dolum/maliyet verisi yoktur.
  Kaynak: docs/arastirma/stabil_live_systematic_results.json; research/stabil_live_systematic.py; domain_engines/stabil/signals.py
## Formasyon alarmına ilişkin arşiv bağlamı
- Formasyon kırılımında zone ve MS-rol eşleşmeleri: FRM-19'da kırılımda zone bulunan grup %75,9, zone bulunmayan %77,0 tamamlandı (-1,1 puan; ayrı örneklem). FRM-20'de rol uyumlu grup %79,6, uyumsuz %73,2 idi.
  Kapsam: 176 sembol / 704 seri; birim=formasyon/kırılım kohortu; FRM-19 ve FRM-20 alt grupları farklıdır; formasyon n=33964; sağdan sansürlü/açık=171; rapor tablosunda run_id kaydedilmemiş.
  Zaman: kayıt=tarih yok; veri sonu=2026-10-19; SONRAKİ ARAŞTIRMA; tarihsel kesitte bilinmiyordu. Bu araştırma kaydı/veri dönemi snapshot as_of tarihinden sonradır; 2026-10-16 tarihli tarihsel kesitte o anda biliniyormuş gibi kullanılamaz.
  Zaman notu: Rapor tarihi/run_id yazılmamış; formasyon doğum aralığı 2026-10-19'a kadar uzanır.
  Örneklem: Toplam 33.964 formasyon; FRM-19: zone var n=11.905 / yok n=20.232; FRM-20: rol uyumlu n=17.103 / uyumsuz n=14.857. Alt gruplar ayrı kohorttur.
  Yöntem: Raporun tanımladığı formasyon kohortları ve güven aralıkları kullanılmıştır; iki karşılaştırmanın paydaları farklıdır ve toplanamaz.
  Sınır: Kohort ilişkisi canlı bir nedeni veya gelecek sonucu göstermez. FRM-19 zone-var/yok karşılaştırmasının olay birimi OB/FVG temas replay'iyle aynı değildir. FRM-20, rapordaki en yakın rol uyumu karşılaştırmasıdır; tek başına MS olay replay'i değildir.
  Kaynak: docs/arastirma/FORMASYON_SONUCLARI.md §FRM-19–20; docs/arastirma/KOLON_SOZLUGU.md §13

Bu paket açıklayıcı bağlamdır; al/sat, pozisyon, fiyat hedefi veya işlem tavsiyesi üretmez. Canlı alarm kararı ve domain motorlarını değiştirmez.
