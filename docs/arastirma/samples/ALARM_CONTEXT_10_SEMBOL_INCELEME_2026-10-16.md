# 10 sembol alarm-context JSON denemesi ve yorum notları

**Kesit:** `2026-10-16T13:30:00+03:00` · **TF:** `4h` · **sembol sayısı:** `10` · **native runner:** izole (`isolated=True`).

Bu, 10 farklı sembolde tam domain JSON paketini birer birer üretme denemesidir. Aynı kapalı H4 kesit tarihi kullanıldı; 13:30 etiketiyle başlayan yeni mumun kapanışı 17:30 olduğundan o mumun içeriği anlık domain çıktısına dahil edilmedi.

## Replay eklentisi kontrolü

- Her paketteki `replay_evidence` alanında domain bazlı kaynaklı aggregate bulgular var. Bunlar 176 sembol/704 seri ve başka ayrı araştırma evrenlerinden gelir; tek sembole ait olasılık değildir.
- Bu denemede ayrıca `replay_evidence.symbol_specific` eklendi: sembolün 4h aday satırlarının tamamı (`replay_events`) ve `VALID + nonoverlap=true` ölçüleri 174 sembol/696 seri, 2026-10-30 raporundan alınmıştır.- Sembol-özel replay verisi `2026-10-19`'a kadar sürer ve raporu `2026-10-30` tarihlidir. Bu nedenle 2026-10-16 kesitinde `available_at_snapshot=false`; canlı context'e/özet yoruma geriye dönük bilgi diye katılmadı.
- Bu replay aday/deneme sonuçları gerçek alarm/Telegram teslimi, işlem getirisi veya kalıcı başarı olasılığı değildir. `end_atr`, başlangıçta sabit ATR ile yönlü onuncu kapanış farkıdır; işlem maliyeti ve emir gerçekleşmesi ölçülmez.
- Replay CSV SHA-256: `f4956cd10f0588b6aedb8a972f5cb3739609e040f4f7ee1c9b27f66c0e8bc0d9`.

## Hızlı karşılaştırma

| Sembol | Kapanış | Domain durumu | MS dış | VP | Aktif OB | Aktif FVG boğa/ayı | Stabil trend | 4h aday / valid-nonoverlap | Medyan end ATR* |
|---|---:|---|---|---|---:|---:|---|---:|---:|
| ASTOR | 183.20 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_UP_BREAK_SUPPORTED · RVOL 2.247 | 25 | 0/0 | weekly=WEEKLY_NOT_UP, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_BUYERS_EMERGING | 21/16 | -1.232 |
| THYAO | 276.75 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_LOWER_ABSORPTION_INVALIDATED · RVOL 1.428 | 16 | 0/1 | weekly=WEEKLY_NOT_UP, daily=DAILY_STRUCTURE_BROKEN, h4=H4_BUYERS_EMERGING | 27/25 | -1.140 |
| GARAN | 133.90 | 5/5 available | STATE_TRANSITION_DOWN/NEUTRAL | PARTICIPATION_CONFLICT · RVOL 2.503 | 15 | 0/0 | weekly=WEEKLY_NOT_UP, daily=DAILY_BEARISH_BALANCE, h4=H4_RECOVERY_CONFIRMED | 24/20 | 0.242 |
| ASELS | 351.00 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_CONFLICT · RVOL 1.707 | 25 | 0/0 | weekly=WEEKLY_TRANSITION, daily=DAILY_BEARISH_BALANCE, h4=H4_SELLING_WEAKENING | 31/27 | -0.535 |
| SISE | 37.26 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_CONFLICT · RVOL 2.092 | 10 | 0/0 | weekly=WEEKLY_NOT_UP, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_BUYERS_EMERGING | 27/22 | -0.197 |
| TUPRS | 384.50 | 5/5 available | STATE_BULLISH/yukarı | PARTICIPATION_LOWER_ABSORPTION_CONFIRMED · RVOL 1.399 | 29 | 0/1 | weekly=WEEKLY_TRANSITION, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_SELLING_WEAKENING | 33/26 | 0.300 |
| BIMAS | 401.50 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_LOWER_ABSORPTION_CONFIRMED · RVOL 2.742 | 20 | 0/0 | weekly=WEEKLY_TRANSITION, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_SELLING_WEAKENING | 25/22 | -0.462 |
| EREGL | 37.40 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_CONFLICT · RVOL 1.034 | 18 | 0/0 | weekly=WEEKLY_TRANSITION, daily=DAILY_BEARISH_BALANCE, h4=H4_BUYERS_EMERGING | 23/21 | -0.216 |
| FROTO | 70.75 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_DOWN_BREAK_SUPPORTED · RVOL 1.707 | 23 | 0/1 | weekly=WEEKLY_NOT_UP, daily=DAILY_STRUCTURE_BROKEN, h4=H4_BUYERS_EMERGING | 25/23 | 1.727 |
| SNGYO | 2.63 | 5/5 available | STATE_BEARISH/aşağı | PARTICIPATION_DOWN_BREAK_SUPPORTED · RVOL 0.868 | 12 | 0/1 | weekly=WEEKLY_NOT_UP, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_NO_RECOVERY | 11/9 | -1.224 |

\* Medyan yalnız sembolün kendi VALID ve örtüşmeyen 4h replay adaylarından; post-cutoff araştırma, getiri/probability değildir.

## Sembol bazında: mevcut, eksik ve yorum

## 1. ASTOR — 183.20 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_BEARISH/aşağı. Hacim: durum=PARTICIPATION_UP_BREAK_SUPPORTED, RVOL=2.247, katılım=CLOSED, kırılım=SUPPORTED. OB: aktif 25 / toplam 26; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 179, aktif boğa/ayı=0/0. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_NOT_UP, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_BUYERS_EMERGING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=21, VALID/nonoverlap n=16, yönlü 10. kapanış medyanı=-1.232 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `21`, outcome dağılımı `RIGHT_CENSORED=1, VALID=20`, VALID/nonoverlap n=`16`, medyan yönlü 10. kapanış `-1.232` ATR.
- 13:30 açılış etiketli aday satırı: `1`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 2. THYAO — 276.75 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_BEARISH/aşağı. Hacim: durum=PARTICIPATION_LOWER_ABSORPTION_INVALIDATED, RVOL=1.428, katılım=CLOSED, kırılım=NONE. OB: aktif 16 / toplam 16; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 159, aktif boğa/ayı=0/1. Stabil: destek ilişkisi=destek altında; trend: weekly=WEEKLY_NOT_UP, daily=DAILY_STRUCTURE_BROKEN, h4=H4_BUYERS_EMERGING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=27, VALID/nonoverlap n=25, yönlü 10. kapanış medyanı=-1.140 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `27`, outcome dağılımı `VALID=27`, VALID/nonoverlap n=`25`, medyan yönlü 10. kapanış `-1.140` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 3. GARAN — 133.90 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_TRANSITION_DOWN/NEUTRAL · STATE_BULLISH/yukarı. Hacim: durum=PARTICIPATION_CONFLICT, RVOL=2.503, katılım=CLOSED, kırılım=SUPPORTED. OB: aktif 15 / toplam 15; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 166, aktif boğa/ayı=0/0. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_NOT_UP, daily=DAILY_BEARISH_BALANCE, h4=H4_RECOVERY_CONFIRMED. Sembole özel 4h replay daha sonraki araştırmadır: aday n=24, VALID/nonoverlap n=20, yönlü 10. kapanış medyanı=0.242 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `24`, outcome dağılımı `BOUNDARY_PURGED=1, VALID=23`, VALID/nonoverlap n=`20`, medyan yönlü 10. kapanış `0.242` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 4. ASELS — 351.00 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_BEARISH/aşağı. Hacim: durum=PARTICIPATION_CONFLICT, RVOL=1.707, katılım=CLOSED, kırılım=SUPPORTED. OB: aktif 25 / toplam 25; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 191, aktif boğa/ayı=0/0. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_TRANSITION, daily=DAILY_BEARISH_BALANCE, h4=H4_SELLING_WEAKENING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=31, VALID/nonoverlap n=27, yönlü 10. kapanış medyanı=-0.535 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `31`, outcome dağılımı `VALID=31`, VALID/nonoverlap n=`27`, medyan yönlü 10. kapanış `-0.535` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 5. SISE — 37.26 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_BEARISH/aşağı. Hacim: durum=PARTICIPATION_CONFLICT, RVOL=2.092, katılım=CLOSED, kırılım=PROTECTED. OB: aktif 10 / toplam 10; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 179, aktif boğa/ayı=0/0. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_NOT_UP, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_BUYERS_EMERGING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=27, VALID/nonoverlap n=22, yönlü 10. kapanış medyanı=-0.197 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `27`, outcome dağılımı `RIGHT_CENSORED=1, VALID=26`, VALID/nonoverlap n=`22`, medyan yönlü 10. kapanış `-0.197` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 6. TUPRS — 384.50 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BULLISH/yukarı · STATE_TRANSITION_DOWN/NEUTRAL. Hacim: durum=PARTICIPATION_LOWER_ABSORPTION_CONFIRMED, RVOL=1.399, katılım=CLOSED, kırılım=PROTECTED. OB: aktif 29 / toplam 29; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 178, aktif boğa/ayı=0/1. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_TRANSITION, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_SELLING_WEAKENING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=33, VALID/nonoverlap n=26, yönlü 10. kapanış medyanı=0.300 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `33`, outcome dağılımı `RIGHT_CENSORED=1, VALID=32`, VALID/nonoverlap n=`26`, medyan yönlü 10. kapanış `0.300` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 7. BIMAS — 401.50 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_BEARISH/aşağı. Hacim: durum=PARTICIPATION_LOWER_ABSORPTION_CONFIRMED, RVOL=2.742, katılım=CLOSED, kırılım=SUPPORTED. OB: aktif 20 / toplam 20; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 178, aktif boğa/ayı=0/0. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_TRANSITION, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_SELLING_WEAKENING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=25, VALID/nonoverlap n=22, yönlü 10. kapanış medyanı=-0.462 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `25`, outcome dağılımı `VALID=25`, VALID/nonoverlap n=`22`, medyan yönlü 10. kapanış `-0.462` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 8. EREGL — 37.40 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_TRANSITION_UP/NEUTRAL. Hacim: durum=PARTICIPATION_CONFLICT, RVOL=1.034, katılım=CLOSED, kırılım=PROTECTED. OB: aktif 18 / toplam 18; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 170, aktif boğa/ayı=0/0. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_TRANSITION, daily=DAILY_BEARISH_BALANCE, h4=H4_BUYERS_EMERGING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=23, VALID/nonoverlap n=21, yönlü 10. kapanış medyanı=-0.216 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `23`, outcome dağılımı `VALID=23`, VALID/nonoverlap n=`21`, medyan yönlü 10. kapanış `-0.216` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 9. FROTO — 70.75 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_BEARISH/aşağı. Hacim: durum=PARTICIPATION_DOWN_BREAK_SUPPORTED, RVOL=1.707, katılım=CLOSED, kırılım=SUPPORTED. OB: aktif 23 / toplam 24; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 171, aktif boğa/ayı=0/1. Stabil: destek ilişkisi=destek altında; trend: weekly=WEEKLY_NOT_UP, daily=DAILY_STRUCTURE_BROKEN, h4=H4_BUYERS_EMERGING. Sembole özel 4h replay daha sonraki araştırmadır: aday n=25, VALID/nonoverlap n=23, yönlü 10. kapanış medyanı=1.727 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `25`, outcome dağılımı `RIGHT_CENSORED=1, VALID=24`, VALID/nonoverlap n=`23`, medyan yönlü 10. kapanış `1.727` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## 10. SNGYO — 2.63 · 1075 tamamlanmış H4 mum

- Kesit `2026-10-16T13:30:00+03:00`; bu kesitteki H4 kapanış sayısı `1075`; arşivdeki H4 satır sayısı `1079`.
- Domain durumları: `market_structure=available`, `volume_participation=available`, `order_block=available`, `fvg=available`, `stabil=available`.
- Beş domainin tamamı çıktı verdi. MS dış/iç: STATE_BEARISH/aşağı · STATE_BEARISH/aşağı. Hacim: durum=PARTICIPATION_DOWN_BREAK_SUPPORTED, RVOL=0.868, katılım=CLOSED, kırılım=SUPPORTED. OB: aktif 12 / toplam 12; tam kayıtlar JSON native bölümünde. FVG: oluşum geçmişi 143, aktif boğa/ayı=0/1. Stabil: destek ilişkisi=destek üstünde; trend: weekly=WEEKLY_NOT_UP, daily=DAILY_PULLBACK_TOO_DEEP, h4=H4_NO_RECOVERY. Sembole özel 4h replay daha sonraki araştırmadır: aday n=11, VALID/nonoverlap n=9, yönlü 10. kapanış medyanı=-1.224 ATR; tarihsel 13:30 bilgi kümesine dahil değil. Domain’ler ayrışabilir; bu özet ortak yön skoru veya al/sat sonucu üretmez.
- Replay (sonradan): toplam aday `11`, outcome dağılımı `RIGHT_CENSORED=1, VALID=10`, VALID/nonoverlap n=`9`, medyan yönlü 10. kapanış `-1.224` ATR.
- 13:30 açılış etiketli aday satırı: `0`; bar kapanışı `2026-10-16T17:30:00+03:00`; snapshot'ta tamamlanmış mı: `False`.
- İnsan tarafından okunabilir tam domain çıktısı aynı paketin `readable_text` alanında; JSON'da tam native ayrıntılar korunur.

## Deneme özeti ve dikkat edilen hatalar

- Standart domain JSON'ında beş alanın her biri ayrıca `available/not_returned/skipped/error` durumuyla yer aldı. Bir alanın `available` olması, içindeki state'in güçlü/olumlu olduğu anlamına gelmiyor.
- Alan denetimi: Market Structure `data_quality` üst düzeyde 10/10 `null`; bu eksik domain değil, engine bu alanı bildirmiyor ve external/internal scope quality değerleri mevcut. Builder null'u koruyor, yapay kalite değeri üretmiyor. VP alanı mevcut state'i taşırken OB/FVG/Stabil `OK` bildiriyor.
- 10 paketin her biri strict JSON olarak serileştirildi ve tekrar parse edildi; geleceğe ait native domain zamanları context'e sızarsa builder hata veriyor.
- Sembol replay sonuçlarıyla anlık 13:30 domain kesiti karıştırılmadı. JSON'da her sembolün tüm 4h replay event satırları ayrı evidence altında tutuldu. Özellikle ASTOR'daki 13:30 açılış etiketli aday, 17:30'da kapanacağı için yalnız sonraki replay kaydı olarak yer aldı.- Örneklem seçilmiş 10 hissedir; sektör/likidite bakımından BIST temsilî örneklemi değildir. Piyasa ve domain uyuşmazlıkları tek skora indirgenmedi.
- Bu deneme canlı akışa, Telegram'a, depolamaya veya işlem kararına bağlı değildir.
