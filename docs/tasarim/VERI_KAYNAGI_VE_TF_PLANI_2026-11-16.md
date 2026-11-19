# Veri kaynağı ve zaman dilimi planı (2026-11-16)

> **Uygulama durumu (2026-11-18, güncellendi):** Reaktif yedekleşme, gerçek 4s
> barı ve `veri_kaynagi` etiketi **üretim `data/fetch.py` hattına uygulandı**.
> Yahoo birincil; Yahoo boş/geçersiz dönerse `tvDatafeed` denenir, ikisi de
> başarısızsa veri uydurulmadan `None` döner. TV başarılıyken
> `frame.attrs["veri_kaynagi"] = "tvdatafeed"`, `TV_GERCEK_4S_AKTIF=1` ise gerçek
> 4s barları `resample_all_timeframes(..., df_4h_native=...)` ile türetilmiş 4s'in
> yerine geçer. Kaynak sayaçları `/health` → `veri_saglayicilari` alanında
> görünür. `borsapy` üretimde import edilmez. `TV_YEDEK_AKTIF=0` eski
> Yahoo-only davranışa döndürür. Aşağıdaki eşikler geçiş kapısı ölçümünün
> sözleşmesi olarak geçerliliğini korur; canlı ölçüm sonuçları
> `docs/denetim/GENEL_KONTROL_2026-11-18.md` §8–§9'dadır.

Hedef karar: **Yahoo birincil**, tvDataFeed **reaktif yedek** ve **4s için gerçek
bar** kaynağı. Amaç daha çok kaynak değil, doğru bar kurgusu ve tek noktaya
bağımlı kalmamak.

## 1. Zaman dilimleri: kim, nereden (hedef)

| TF | Kaynak | Not |
|---|---|---|
| 1s (1 saat) | Yahoo | Kendi başına gelir, günde 9 bar (09:30…17:30). |
| 2s | **1s'ten türetilir** | Gün başına 5 bar; son dilim kısa (**%20**). |
| 4s | **tvDataFeed (gerçek 4h)** | Yahoo ve borsapy 2s/4s vermiyor. Gün başına 2 tam bar. |
| 1g | Yahoo 1s'ten türetilir | 9 bar → 1 bar, kısa bar yok. |

Ölçülen fark (10.080 bar, 28 sembol, 40 gün):

- Türetilmiş 4s: 3.360 bar, 1.120'si kısa (**%33**) — hepsi günün son barı (17:30–18:10, 40 dk).
- Gerçek 4h (TradingView ızgarası 10:00/14:00): kısa bar **%0**, son bar seans kapanışında biter.
- Sıfır hacim: Yahoo %10,85 · TradingView tarafı genelde dolu.

## 2. Tarama temposu (TF bazlı ayrı; hedef)

| Dilim | Ne çekilir | İstek (28 sembol) |
|---|---|---|
| 10:30 | 1s | 28 |
| 14:00 | 1s | 28 |
| 14:05 | 4s (ilk 4h bar tamamlandı) | 28 |
| 17:00 | 1s | 28 |
| 18:15 | 1s + 4s + 1g | 84 |
| **Toplam** | | **~196/gün** |

Bugünkü ~513 isteğe göre yaklaşık **%62 az**. Her TF'yi her dilimde çekmek
(~5.480/gün) bilinçli olarak yapılmıyor: 10 kat istek, sıfır yeni bilgi.

## 3. Yedekleşme davranışı (hedef; üretimde henüz yok)

1. Önce Yahoo denenir (birincil).
2. Yahoo hata verirse/boş dönerse aynı turda tvDataFeed denenir.
3. tvDataFeed de olmazsa 4s **anlık olarak 1s'ten** üretilir; bar üretilir ama
   `veri_kaynagi = "turetildi"` etiketiyle işaretlenir, arayüzde ve karnede görünür.
4. Bir sonraki çekimde tvDataFeed **yine denenir** (kalıcı olarak devre dışı bırakılmaz).
5. tvDataFeed geri gelirse son türetilmiş 4s barları gerçek barlarla **düzeltilir**;
   düzeltme `veri_kaynagi` etiketinde ve durum satırında görünür.

Sessiz düşüş olmayacak: geçiş sonrası her bar hangi kaynaktan geldiğini taşır.
Bu maddeler **sözleşme taslağıdır**; mevcut ölçüm aracı üretim deque'ine yazmaz.

## 4. Geçiş kapısı (ölçüm yeşil olmadan kod devreye girmez)

| Ölçüt | Eşik |
|---|---|
| Ortak gün oranı | ≥ %98 |
| Medyan kapanış farkı | ≤ %0,05 |
| En büyük fark | ≤ %0,50 |
| Adayda kısa bar | referanstan kötü değil |
| Adayda sıfır hacim | referanstan kötü değil |

`scripts/saglayici_karsilastirma.py::karar_ver` bu kalite koşullarının ikisini de
denetler; yalnızca fiyat/bar uyumu yeşil olsa bile aday hacim veya bar kurgusu
referansı kötüleştiriyorsa `geç` dönmez.

2s/4s'te fiyat uyumu **gün ızgarasında** ölçülür: türetilmiş 4s
(09:30/13:30/17:30) ile gerçek 4h (10:00/14:00) aynı ızgarada değildir; damga
damga eşleştirme sıfır ortak bar verip sahte "red" üretir. **1g de gün
ızgarasında ölçülür:** Yahoo günlük barı `00:00 İstanbul` tarih etiketi,
TradingView günlük barı `00:00 UTC` anı (= `03:00 İstanbul`) taşır; aynı takvim
günü damga damga kesişmez. Damga eşleşmesi `DatetimeIndex.intersection` yerine
değer bazlı `isin` ile yapılır; pandas'ın `freq`'li hızlı yolu kaymış
ızgaralarda hiç var olmayan damgaları "ortak" sanıp sahte `geç` üretebiliyor.

## 5. Ölçüm komutu ve kurulum

```powershell
# PyPI çatallaması (doğrulanmış sürüm)
.\.venv\Scripts\python.exe -m pip install tradingview-datafeed==2.1.1
# Alternatif: sabit GitHub commit'i (dağıtım adı tvdatafeed==2.1.0)
# .\.venv\Scripts\python.exe -m pip install "git+https://github.com/rongardF/tvdatafeed@e6f6aaa7de43"

# Ağsız ortam teşhisi (gerçek çekme için --tanis-dene 1)
.\.venv\Scripts\python.exe -m scripts.saglayici_karsilastirma --mod tanis
# Canlı ölçüm (4s ve 1g birlikte)
.\.venv\Scripts\python.exe -m scripts.saglayici_karsilastirma --mod canli --tf 4s 1g --sembol "THYAO,GARAN,AKBNK,ASELS,EREGL" --aday tvdatafeed --adet 360
# Yahoo boş/kota döndürürse 1g çapraz kontrolü (borsapy 2s/4s desteklemez)
.\.venv\Scripts\python.exe -m scripts.saglayici_karsilastirma --mod canli --tf 1g --sembol "THYAO,GARAN" --aday tvdatafeed --referans borsapy
```

`tvdatafeed` **adıyla** PyPI paketi yoktur; aynı `tvDatafeed` import modülünü
sağlayan `tradingview-datafeed==2.1.1` PyPI'dedir. **Kıyas notu:** tvDatafeed WS
isteği `adjustment:"splits"` gönderir (yalnız bölünme düzeltmesi); bu yüzden ölçüm
aracı Yahoo'dan `auto_adjust=False, actions=False` ile **ham kapanış** ister.
Aksi halde yfinance'in temettü düzeltmesi %3–4 sabit oranlı sahte fark üretir.
Ortak istemci
(`scripts/tvdatafeed_client.py`) bu dağıtımı ve sabit GitHub commit'inin
`tvdatafeed==2.1.0` sürümünü kabul eder; ikisi de varsayılan kurulumda kapalıdır.
Kırılırsa ölçüm `red`/açık hata verir; üretim hattı etkilenmez.

## 6. Bilinçli olarak yapılmayanlar

- Canlı `data/fetch.py` / `bot/scan.py` hattına tvDatafeed yedeğini bağlamak:
  ölçüm kapısı yeşil olmadan ve kaynak etiketi/senaryo testleri yazılmadan geçiş yok.
- 2s'yi **canlı üretimde** gerçek çekmek: günde 5 bar için ayrı istek akışı; 4s kazancı zaten alınıyor. Bu madde arşiv replay'i için 2026-11-18'de aşağıdaki §7 ile revize edildi.
- Her TF'yi her dilimde çekmek: istek 4-10 katı, karşılığı yok.

## 7. Arşiv replay'i için NATIVE 1h/2h/4h/1d kararı (2026-11-18)

Canlı taramadaki yukarıdaki istek ekonomisi korunur; ancak **araştırma
replay'i** ayrı bir veri setidir. 170+ sembolde 2h/4h'nin 1h'den
`resample_ohlcv` ile türetilmesi hacim/fiyat kayması ürettiği için replay
girdisinden çıkarıldı:

- `1h`/`1d`: Yahoo/yfinance, `auto_adjust=False`, native.
- `2h`/`4h`: TradingView/tvDatafeed `in_2_hour`/`in_4_hour`, **native WS barları**.
- `research/arsiv.py`: yeni `native_zorunlu` manifestinde 2h/4h için kendi
  `_2h.csv.gz` / `_4h.csv.gz` dosyalarını okur; eksikse fail-closed.
- `scripts/backfill/arastirma_kosu.py` ve `dz_yukleme.py`: strict native çerçeve;
  eski legacy fallback yalnızca eski manifestli yardımcı çağrılarda kalır.
- `BRENT`: BIST exchange'inde native 2h/4h yok; doğrulanmış sembol setinden çıkar.

Bu karar canlı `data/fetch.py` / `bot/scan.py` zincirini değiştirmez: orada Yahoo
birincil, TV yalnızca Yahoo veri döndürmediğinde reaktif yedektir. Ayrıntı ve
Termux komutları: [`NATIVE_TF_REPLAY_PLANI_2026-11-18.md`](../arastirma/NATIVE_TF_REPLAY_PLANI_2026-11-18.md),
[`TERMUX_BACKFILL.md`](../kurulum/TERMUX_BACKFILL.md). **2026-11-19
güncellemesi:** native veriler Termux'tan push edildi ve
[`NATIVE_VERI_GELISI_2026-11-19.md`](../denetim/NATIVE_VERI_GELISI_2026-11-19.md)
ile doğrulandı (176 sembol, 704/704 dosya, resample yok). Replay hâlâ koşulmadı;
veriler geldikten sonra ayrı turda yapılacak.

### Reddedilen alternatif

- `borsapy`'yi fiyat kaynağı yapmak: üretimde import edilmiyor, 2s/4s vermiyor.
