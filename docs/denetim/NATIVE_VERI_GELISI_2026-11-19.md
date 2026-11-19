# NATIVE 1h/2h/4h/1d Arşivinin Gelişi ve Doğrulanması

> **Konu:** 176 sembol için dört zaman diliminin de kendi sağlayıcısından
> **native** çekilmiş OHLCV serilerinin Termux'tan aktif dala gelişi, dosya
> düzeyinde doğrulanması ve replay'e hazır durumu.
> **Durum:** `Kayıt` · **Tarih:** 2026-11-19 · **Kapsam:** Veri gelişi + doğrulama.
> **Dahil değil:** replay koşusu, PR, fiili Render deploy, canlı servis çağrısı.

Verilerin kendisi `backfill_data/` içindedir; bu belge **veriyi yeniden üretmez**,
yalnızca gelen arşivin ne olduğunu, hangi commit'lerle geldiğini ve hangi
kontrollerden geçtiğini kaydeder. Ajan tarafında canlı Yahoo/TradingView çağrısı
yapılmadı; çekim kullanıcının Termux yerel klonunda gerçekleşti.

---

## 1) Özet kartı

| Başlık | Sonuç |
|---|---|
| Sembol | **176** doğrulanmış, **10** kalıcı/engelli |
| Zaman dilimleri | `1h`, `2h`, `4h`, `1d` — dördü de **native** |
| Kaynak planı | `1h`/`1d` = Yahoo/yfinance · `2h`/`4h` = TradingView/tvDatafeed |
| TV dağıtımı | `tradingview-datafeed==2.1.1`, `hazir=True` |
| Native dosya | **704 / 704**, `eksik_dosya_sayisi=0` |
| Resample | **`resample_kullanildi=False`** — 2h/4h 1h'den türetilmedi |
| Probe | `probe_sonucu.json`: **176 geçerli / 10 geçersiz** |
| Liste | `dogrulanmis_semboller.txt`: **176 satır, 176 benzersiz** |
| Manifest son koşu | **704 `ok`**, `gecici=0`, `kalici=0`, ban koruması durdurmadı |
| Süre / boyut | `3579.6 sn` (~59.7 dk) · `backfill_data/` **20M** |
| Replay | **Hazır ama koşulmadı**; ayrı turda |

---

## 2) Gelen commit'ler

| Commit | Tarih (UTC+03) | Açıklama | İçerik |
|---|---|---|---|
| `8a18fbd` | 2026-11-19 16:24 | `backfill: 1h/2h/4h/1d native OHLCV 176 sembol (Yahoo + TradingView) — Termux` | 708 dosya: 176 × 4 CSV.gz + eski 1h/1d güncellemeleri + `manifest.json`, `probe_sonucu.json`, `kaynak_raporu.json`, `dogrulanmis_semboller.txt` |
| `6cb80eb` | 2026-11-19 16:45 | `backfill: native probe` | Commit adı yanıltıcı: probe dosyası `8a18fbd` içinde gelmişti; bu commit yalnızca 9 alakasız debug/backup dosyası ekledi (§7) |

Ajan çalışma alanı bu turda `6cb80eb` üzerine hizalandı; `git status` temiz,
upstream aktif dalı izliyor, PR açılmadı.

---

## 3) Dosya envanteri

| Dosya | Sayı | Not |
|---|---:|---|
| `*_1h.csv.gz` | 177 | 176 native + kalıcı 10 kümeden kalan 1 eski 1h dosyası |
| `*_2h.csv.gz` | **176** | TradingView `in_2_hour`, native |
| `*_4h.csv.gz` | **176** | TradingView `in_4_hour`, native |
| `*_1d.csv.gz` | 177 | 176 native + kalan 1 eski 1d dosyası |
| `dogrulanmis_semboller.txt` | 176 satır | Strict native replay'e girecek liste |
| `probe_sonucu.json` | 176/10 | 12 sembol yeniden probe ile kurtarıldı |
| `manifest.json` | 176 sembol | `surum=native-1`, `arsiv_modu=native`, `native_zorunlu=True` |
| `kaynak_raporu.json` | 704/704 | `resample_kullanildi=False`, `eksik_dosya_sayisi=0` |

`1h`/`1d` sayısının 177 olması bilinçli bir sapma değildir: eski 2 TF arşivinden
kalan 1h/1d dosyaları diskte durur. `research/arsiv.py` native modda **dört
dosyanın kesişimini** aldığı için replay'e **176 sembol** girer; fazla eski
dosyalar kullanılmaz. Dört dosyası olan kesişim,
`dogrulanmis_semboller.txt` ile birebir aynıdır.

---

## 4) Doğrulama tablosu

| Kontrol | Beklenen | Gelen dosyada |
|---|---|---|
| `probe_sonucu.json` | 176/10, karma plan | **176/10**, `{"1h":"yahoo","2h":"tvdatafeed","4h":"tvdatafeed","1d":"yahoo"}` |
| `tv_dagitim.surum` | `2.1.1` | **`2.1.1`**, `hazir=True` |
| `dogrulanmis_semboller.txt` | 176 benzersiz | **176 / 176** |
| `kaynak_raporu.arsiv_modu` | `native` | **`native`** |
| `kaynak_raporu.native_zorunlu` | `True` | **`True`** |
| `kaynak_raporu.sembol_sayisi` | 176 | **176** |
| `beklenen / diskteki / eksik` | 704 / 704 / 0 | **704 / 704 / 0** |
| `resample_kullanildi` | `False` | **`False`** |
| Kayıt özeti | 176 × 4 `ok` | `1h\|yahoo\|ok:176`, `1d\|yahoo\|ok:176`, `2h\|tvdatafeed\|ok:176`, `4h\|tvdatafeed\|ok:176` |
| `manifest.son_kosu.sonuclar` | 704 `ok` | **`ok:704`**, `atlandi=0`, `gecici=0`, `kalici=0`, `diger=0` |
| `ban_korumasi_durdurdu` | `False` | **`False`** |
| Strict dörtlü kesişim | 176 = liste | **176 = liste**, `BRENT` yok |
| Kurtarılan örnekler | listede | `TCELL`, `TOASO`, `DOAS`, `SNGYO`, `CANTE` **var** |
| Kalıcı örnekler | 2h/4h yok | `IDEAS`, `IPEKE`, `BAHSK`, `TEKYO` için `_2h.csv.gz` **yok** |

### Kalıcı/engelli 10 sembol

`BRENT` + Yahoo 1h/1d boş dönen 9 sembol:

```text
BAHSK · BRENT · DOAR · GTZYO · HTKMK · IDEAS · IPEKE · IZDMC · KLSRN · TEKYO
```

`IDEAS`/`IPEKE` TradingView'de veri döndürse bile Yahoo tarafı `1h`/`1d`
sağlamadığı için karma native sete alınmadı. `BRENT`, BIST exchange'inde native
2h/4h karşılığı olmadığı için zaten plan dışıdır.

### Yeniden probe ile kurtarılan 12 sembol

İlk probe'da `tv: boş veya geçersiz sağlayıcı verisi` ile düşen, ikinci kısa
probe'da **12/0** ile tamamen kurtarılan semboller:

```text
CANTE · DARDL · DOAS · KONYA · MAGEN · MIATK
MPARK · PASEU · SELEC · SNGYO · TCELL · TOASO
```

Böylece ilk `164 geçerli / 22 geçersiz` sonucu, **176 geçerli / 10 geçersiz**
hâline geldi ve 170+ hedefi korundu.

---

## 5) Örnek CSV kontrolü — `TCELL`

| Dosya | Satır | İlk `bar_time` | Ardışık fark |
|---|---:|---|---|
| `TCELL_2h.csv.gz` | 1500 | `2025-09-08 13:00:00+03:00` | 120 dk · 120 dk · gece 960 dk · 120 dk |
| `TCELL_4h.csv.gz` | 1500 | `2024-11-18 13:00:00+03:00` | 240 dk · gece 960 dk · 240 dk · 240 dk |
| `TCELL_1h.csv.gz` | 3254 | `2025-06-11 09:30:00+03:00` | 60 dk × 4 |
| `TCELL_1d.csv.gz` | 503 | `2024-11-19 00:00:00+03:00` | 1440 dk · hafta sonu 4320 dk |

Tüm satırlarda `bar_time` biçimi **`YYYY-MM-DD HH:MM:SS+03:00`**; `T` ayracı
yok. Kolonlar `bar_time,open,high,low,close,volume`. 2h/4h dosyaları kendi
sağlayıcı aralığıyla (`in_2_hour` / `in_4_hour`) üretilmiş native barlardır;
1h'den `resample_ohlcv` ile türetilmiş bir kopya değildir.

---

## 6) Replay sözleşmesi ve sınırlar

- `research/arsiv.py` native manifestte `arsiv_sembolleri(native_only=True)`
  ile dört dosyanın kesişimini alır; eksik 2h/4h dosyası varsa sembol sessizce
  replay'e alınmaz.
- `tf_frame(..., legacy_resample=False)` 2h/4h için kendi `_2h.csv.gz` /
  `_4h.csv.gz` dosyasını ister; yoksa `FileNotFoundError` verir.
- Eski [`DZ_REPLAY_SONUCLARI_2026-10-28.md`](../arastirma/DZ_REPLAY_SONUCLARI_2026-10-28.md)
  177 sembol / 708 seri sonucunu **1h'den türetilmiş** 2h/4h ile üretmiştir;
  tarihsel kayıt olarak kalır, native replay sonucu olarak **kabul edilmez**.
- `arastirma_kosu.py` ve `dz_yukleme.py` strict native yüzeyleri hazırdır.
  **Replay bu turda koşulmadı**; kullanıcı daha önce *"Hayır sadece veriler
  gelecek önce"* dediği için replay komutu veriler geldikten sonraki ayrı tura
  bırakıldı. Bu belgede de replay komutu bilerek yoktur.
- Ajan canlı Yahoo/TradingView/Supabase/Telegram/Render çağrısı, fiili Render
  deploy veya PR yapmadı. Bu turda **tam pytest / CI watch** da çalıştırılmadı;
  yapılan iş dosya, JSON ve gzip CSV okumaları ile dokümantasyondur.
- Bağlı uygulamalar kapalıydı ve kullanılmadı.

---

## 7) Temizlik notu (henüz uygulanmadı)

`6cb80eb` commit'i veriyle ilgisiz 9 dosyayı tracked hâle getirdi:

```text
debug_candidate_validation.py
debug_random_batch.py
debug_random_batch.py.before_current_state
debug_random_candidate.py
debug_random_candidate.py.before_current_output
patterns.py.before_current_binding
patterns.py.before_current_integrity
patterns.py.before_current_integrity_function
upper_boundary
```

Toplam ~277 KB; `py_compile` temiz, hızlı anahtar kelime taramasında gizli
anahtar bulunmadı. Veri doğrulamasını etkilemezler; repo temizliği için ayrı
bir commit ile silinmeleri önerilir. **Bu dokümantasyon turunda silinmediler**;
silme için kullanıcı onayı bekleniyor.

---

## 8) Kanıt yöntemi

1. `git fetch` ile aktif dalın remote ucu alındı; ajan çalışma alanı eski
   graft commit'ine düşmüştü. `git add -A` + `git diff --cached --quiet 4bca50f`
   ile yerel dosyaların önceki kod commit'iyle **birebir aynı** olduğu
   doğrulandıktan sonra `git reset --hard` ile `6cb80eb`'e hizalandı; veri
   kaybı yok.
2. `backfill_data/` altındaki JSON raporları `json` modülüyle okundu.
3. CSV.gz dosyaları `gzip` + `csv` ile açıldı; `bar_time` biçimi regex ile,
   ardışık farklar `datetime.fromisoformat` ile kontrol edildi.
4. Strict native sembol kesişimi, dört `*_<tf>.csv.gz` kümesinin
   `set.intersection` sonucu olarak hesaplandı ve doğrulanmış listeyle
   karşılaştırıldı.
5. Markdown bağlantıları ve `git diff --check` kontrol edildi.

---

## 9) İlgili belgeler

| Belge | Rolü |
|---|---|
| [`TERMUX_BACKFILL.md`](../kurulum/TERMUX_BACKFILL.md) | Çekim/probe/pilot/tam koşu/doğrulama/push akışı |
| [`NATIVE_TF_REPLAY_PLANI_2026-11-18.md`](../arastirma/NATIVE_TF_REPLAY_PLANI_2026-11-18.md) | Native replay kararı, kabul kriterleri ve veri sonrası durum |
| [`VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md`](../tasarim/VERI_KAYNAGI_VE_TF_PLANI_2026-11-16.md) §7 | Canlı üretim ↔ araştırma replay ayrımı |
| [`GENEL_KONTROL_2026-11-18.md`](GENEL_KONTROL_2026-11-18.md) §12–13 | Kod zinciri ve bu veri gelişinin denetim kaydı |
| [`DZ_REPLAY_SONUCLARI_2026-10-28.md`](../arastirma/DZ_REPLAY_SONUCLARI_2026-10-28.md) | Eski türetimli sonuçların legacy uyarısı |
| [`../README.md`](../README.md) | Belge haritası ve güncel durum tablosu |

---

## 10) Sonraki adım

Native seriler **hazır**. Replay, kullanıcı ayrı turda istediğinde
`arastirma_kosu.py` / `dz_yukleme.py` strict native yüzeyleriyle koşulacak ve
`DZ_REPLAY_SONUCLARI_2026-10-28.md` yerine yeni native sonuç belgesi üretilecek.
Bu kayıt, *"veriler geldi ve doğrulandı"* noktasını kapatır; *"replay yapıldı"*
iddiası içermez.
