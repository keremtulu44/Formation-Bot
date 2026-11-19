# NATIVE 1h/2h/4h/1d REPLAY VERİ PLANI — 2026-11-18

> **Durum:** Kod + Termux akışı hazır · **Commit:** `96bd20b` · **CI:** run
> `44508629441` **success** (10 dk 9 sn) · **Canlı çekim:** kullanıcının Termux
> cihazında yapılacak · **Replay:** bu turda **YOK**, önce veriler gelecek.
> **Ajan kanıtı:** ağsız testler + kod; ajan canlı Yahoo/TradingView/Supabase/
> Telegram/Render çağrısı yapmadı.

## 1) Sorun ve karar

170+ sembolün eski replay'inde yalnız `1h` + `1d` native çekilmiş, `2h`/`4h`
`research.arsiv.tf_frame` içinde `data.resample_ohlcv` ile 1h barlarından
türetilmişti. 1h açılış müzayede barlarının hacmi ve sağlayıcıların gerçek 2h/4h
kova ızgaraları farklı olduğu için bu türetim **hacim/fiyat kayması** üretiyordu.
Kullanıcı bunu replay girdisinden çıkarmak istedi.

Kullanıcı seçimleri:

| Karar | Seçim |
|---|---|
| Kaynak | **Karma:** `1h`/`1d` Yahoo, `2h`/`4h` TradingView/tvDatafeed native |
| Çıktı | Tüm `CSV.gz` + manifest/probe/rapor **commit + push** |
| Replay | **Hayır, önce veriler gelecek**; replay sonra ayrı turda |

Yahoo `2h`/`4h` intervalini desteklemez; repoda bu aralıkları gerçek bar olarak
veren doğrulanmış kanal `scripts/tvdatafeed_client.py` üzerinden tvDatafeed WS'tir.
`borsapy` 2h/4h vermez. `BRENT` BIST exchange'inde native 2h/4h karşılığı
olmadığı için doğrulanmış sembol listesine alınmaz.

## 2) Yeni kaynak/TF sözleşmesi

| TF | Sağlayıcı | Provider interval | Dosya | Manifest etiketi |
|---|---|---|---|---|
| `1h` | `yahoo` | `1h` | `<SEM>_1h.csv.gz` | `kaynak=yahoo`, `native=true` |
| `2h` | `tvdatafeed` | `in_2_hour` | `<SEM>_2h.csv.gz` | `kaynak=tvdatafeed`, `native=true` |
| `4h` | `tvdatafeed` | `in_4_hour` | `<SEM>_4h.csv.gz` | `kaynak=tvdatafeed`, `native=true` |
| `1d` | `yahoo` | `1d` | `<SEM>_1d.csv.gz` | `kaynak=yahoo`, `native=true` |

Ortak sabit: `scripts/backfill/native_kaynak.py::KAYNAK_PLANI`. Aynı plan
`research/arsiv.py::KAYNAK_PLANI`, `manifest.json`, `probe_sonucu.json` ve
`kaynak_raporu.json` içinde taşınır; testler bu eşitliği kilitler.

Yeni `manifest.json` alanları:

- `surum: "native-1"`
- `arsiv_modu: "native"`
- `native_zorunlu: true`
- `zaman_dilimleri: ["1h","2h","4h","1d"]`
- `kaynak_plani` + `kaynak_plani_ozeti`
- `tv_dagitim` (doğrulanmış `tradingview-datafeed==2.1.1`)
- her kayıt: `kaynak`, `native`, `provider_symbol`, `provider_interval`,
  `bar_sayisi_istek` / `period`, `tv_exchange`

`kaynak_raporu.json` TF × kaynak × durum sayımlarını, beklenen/eksik native
dosyaları ve `resample_kullanildi=false` bayrağını yazar.

## 3) Kod değişiklikleri

| Dosya | Değişiklik |
|---|---|
| `scripts/backfill/native_kaynak.py` | Yeni: kaynak planı, TV sembol eşlemesi, lazy ortak istemci, UTC→İstanbul, OHLCV normalizasyonu, WS hata sınıflandırması |
| `scripts/backfill/yahoo_backfill.py` | Varsayılan `--interval 1h,2h,4h,1d`, `--tv-bar-sayisi`, `--tv-exchange`; Yahoo/TV dalları; iki sağlayıcılı probe; native etiketli manifest; `kaynak_raporu.json`; `atlanmali_mi` kaynak/native doğrulaması; gerçek `--retry-failed` |
| `research/arsiv.py` | `KAYNAK_INTERVAL` identity; `arsiv_modu`, `arsiv_kaynak_plani`; `arsiv_sembolleri(native_only=True)` dört dosya şartı; `tf_frame(..., legacy_resample=False)` strict native okuma |
| `scripts/backfill/arastirma_kosu.py` | Replay planı `native_only=True`, `tf_frame(..., legacy_resample=False)`, rapor notlarında kaynak/TF etiketleri |
| `scripts/backfill/dz_yukleme.py` | Strict native çerçeve, `dz_bars` 4 TF etiketi, `kapsam_raporu.json` içinde `arsiv_modu/kaynak_plani/native_zorunlu/resample_kullanildi` |
| `requirements-termux.txt`, `setup-termux.sh` | `tradingview-datafeed==2.1.1` + `websocket-client==1.9.2` pinleri ve dağıtım doğrulaması |
| `docs/kurulum/TERMUX_BACKFILL.md` | Mevcut yerel klon için pull → kurulum → probe → pilot → tam çekim → doğrulama → commit/push → ajana haber; replay yok |
| Testler | `test_native_kaynak.py` yeni; `test_yahoo_backfill.py`, `test_arastirma_olcum.py`, `test_arsiv_canli_ayrimi.py`, `test_dz_yukleme.py` native/legacy ayrımıyla güncellendi |

Geriye dönük uyumluluk: eski manifestli arşivlerde doğrudan `tf_frame` çağıran
eski yardımcı scriptler 2h/4h için açık `legacy_resample=True` fallback'ini
kullanabilir. **Yeni replay bu fallback'i kullanmaz**; native manifestte
varsayılan bile strict'tir.

## 4) Termux akışı (kullanıcı cihazı)

Ayrıntılı kopyala-yapıştır komutlar:
[`docs/kurulum/TERMUX_BACKFILL.md`](../kurulum/TERMUX_BACKFILL.md).

Özet:

1. `cd ~/Formation-Bot`, `DAL="$(git branch --show-current)"` ile aktif Arena
   dalını al, `git fetch` + `git pull --rebase`. Belgeye sabit dal yazılmaz.
2. `pkg install python-numpy python-pandas`, `pip install -r requirements-termux.txt`,
   `dogrulanmis_surum()` kontrolü.
3. `--probe` → `probe_sonucu.json` + `dogrulanmis_semboller.txt`.
4. `--limit 10` pilot → dört dosyanın başlık/bar_time kontrolü.
5. `termux-wake-lock` + tam çekim (`--tv-bar-sayisi 1500`).
6. §5 doğrulama bloğu: `DOĞRULAMA OK` görmeden push yok.
7. `git add backfill_data/` → commit → `git push origin "$DAL"` → ajana haber.

**Replay komutu bu belgede bilerek yoktur.** Kullanıcı "Hayır sadece veriler
gelecek önce" dedi; `arastirma_kosu.py` / `dz_yukleme.py` veriler push edildikten
sonra ayrı turda koşulacak.

## 5) Eski raporun statüsü

[`DZ_REPLAY_SONUCLARI_2026-10-28.md`](DZ_REPLAY_SONUCLARI_2026-10-28.md) 177
sembol / 708 seri / 354 CSV.gz sonuçlarını **eski türetimli** arşivle üretmiştir.
Tarihsel kayıt olarak korunur; 2h/4h hacim/fiyat kayması içerdiği için yeni
native replay'in sonucu olarak kabul EDİLMEZ. Native veriler geldikten sonra
raporlar yeniden üretilmelidir.

## 6) Kabul kriterleri

- [x] 1h/2h/4h/1d için ayrı native çekim yolu var; 2h/4h 1h'den resample edilmiyor.
- [x] Manifest/probe/rapor kaynak + TF + native etiketlerini taşıyor.
- [x] Arşiv okuyucusu/replay/rapor scriptleri strict native dosyaları okuyor.
- [x] Eski türetimli kayıtlar `atlanmali_mi` ile yeniden çekiliyor.
- [x] Termux kurulumu TV pinleri + dağıtım doğrulaması içeriyor.
- [x] Ağsız testler 2h/4h resample çağrılmadığını, TV kurulumu yokken fail-closed durduğunu kilitliyor.
- [ ] Canlı çekim kullanıcının Termux'unda yapılacak.
- [ ] `backfill_data/` commit/push edilecek.
- [ ] Replay, veriler ajana geldikten sonra ayrı turda koşulacak.

## 7) Kanıt sınırı

Bu belge kod/test/doküman teslimidir. Ajan canlı Yahoo veya TradingView
çağrısı yapmadı; 170+ sembolün gerçek bar sayıları, TV WS erişimi, Termux
çalışma süresi ve push sonrası commit hash'i kullanıcı cihazındaki koşudan
gelecektir. Fiili Render deploy, PR veya canlı Telegram/Supabase çağrısı yoktur.

## 8) Doğrulama (2026-11-19)

| Kapı | Sonuç |
|---|---|
| Statik | `ruff check .`, `pip check`, `compileall`, `bash -n setup-termux.sh`, `git diff --check` temiz |
| Hedefli testler | `test_native_kaynak.py` + 7 ilgili dosya: **256 passed** |
| Tam pytest | **4585 passed / 43 skipped** · 513,07 sn · `DATA_DIR=/tmp/fb-native-data` |
| İlk tam koşu | 1 doküman testi sabit Arena dalı nedeniyle kırmızı; `DAL="$(git branch --show-current)"` ile düzeltildi |
| Commit | `96bd20b` · 17 dosya · 1617+/423- |
| CI | `44508629441` **success** · Python 3.12 · 10 dk 9 sn · 10/10 adım |

Ağsız testler şunları kilitler: 2h/4h için `resample_ohlcv` çağrılmaz; native
dosya eksikse `FileNotFoundError`; TV kurulumu yokken `main` 2 döner; probe iki
sağlayıcıyı birlikte doğrular; manifest/probe/rapor kaynak + TF + native
etiketlerini taşır; `dz_bars` dört TF'yi olduğu gibi yazar. Canlı 170+ sembol
çekimi, `backfill_data/` push'u ve replay hâlâ kullanıcı cihazında/sonraki
turda bekliyor.
