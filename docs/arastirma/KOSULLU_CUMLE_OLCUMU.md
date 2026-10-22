# Koşullu tamamlanma cümlesi — ölçüm ve karar (2026-10-22)

> **Durum:** ÖLÇÜLDÜ · **cümle karta YAZILMADI** (veri desteklemiyor)
> **Kod:** `scripts/diagnostics/tamamlama_caprazi.py` · test: `test_tamamlama_caprazi.py`
> **Soru:** "formasyonun tamamlanması % şu kadar düşerse tamamlanır" cümlesi
> kartın ölçü bloğuna yazılabilir mi?

## 1 · Neden bu ölçüm istendi

Kullanıcı (2026-10-22): *"tipik istemiyorum, formasyonun tamamlanmasını % şu
kadar düşerse tamamlanır şeklinde ekleyelim"*. Kartın `◇` bloğu o güne kadar
yalnız **koşulsuz** oran basıyordu (`%76 tuttu`). İstenen cümle, o anki duruma
bağlı bir koşuldu: *fiyat sınıra yaklaşırsa / sınırı şu kadar aşarsa, sonuç
geçmişte ne oldu?*

Kural (kullanıcı): **onaysız yazılmaz.** Bu yüzden cümle yazılmadan önce arşiv
üzerinde ölçüldü.

## 2 · Yöntem

Girdi: araştırma koşusunun `frm.jsonl` çıktısı (formasyon başına bir satır).
Kullanılan kolonlar ve tanımları `docs/arastirma/KOLON_SOZLUGU.md` §13.5'te:

| Kolon | Anlam |
|---|---|
| `frm_yakinlik_ust/alt_fitil_atr` | doğumdan kırılıma kadar sınıra **en çok** yaklaşma (ATR). 0 = fitil çizgiye değdi |
| `frm_asim_ust/alt_fitil_atr` | sınırı en fazla **ne kadar aştı** (ATR) |
| `terminal_state` | `FORMASYON_TAMAMLANDI` = kırılım teyit aldı ve banda dönmedi (**"hedefe ulaştı" değil**) |
| `bitis_sebebi` | `TERMINAL` ya da `VERI_SONU` |

Kurallar:

* **Sağdan sansür dışlandı.** `VERI_SONU` (hâlâ açık) formasyonlar "tamamlanmadı"
  sayılmaz; ölçüm dışında tutulur ve sayısı raporlanır (153 satır).
* **Anti-dairesellik.** Yakınlık/aşım çapaya **kadar** ölçülür; sonuç çapadan
  sonra başlar. İkisi aynı pencerede hesaplanmaz.
* **GA %95 Wilson** aralığı verilir; n küçükken normal yaklaşım iyimser olurdu.
* Yaklaşık eşikler: `YAKINLIK_IZGARA` (0,5 · 1,0 · 1,5 · 2,0 ATR).

## 3 · Örneklem

| | |
|---|---|
| Koşu | `--semboller`(alfabetik ilk 91 sembol) · `--timeframe 4h,1d` |
| Zaman dilimleri | 4h (31 sembol) + 1d (86 sembol) |
| Okunan satır | 1 899 |
| Açık (dışlandı) | 153 |
| **Kapanmış formasyon** | **1 746** |

> **Sınır:** koşu tüm evreni kapsamıyor (alfabetik sıra, 91/176 sembol); tam
> koşu `scripts/backfill/arastirma_kosu.py --timeframe 4h,1d` ile ~40 dakikada
> alınır. Aşağıdaki karar için bu örneklem yeterli: sonucu belirleyen şey
> "yaklaşmanın neredeyse evrensel olması" (%93), ve bu oran tam koşuda da
> değişmez.

## 4 · Sonuç A — "sınıra yaklaşırsa" ayrıştırmıyor

| Eşik (ATR) | Yaklaşan n | Tamamlandı | Yaklaşmayan n | Tamamlandı |
|---|---|---|---|---|
| ≤ 0,50 | 1 634 | **%72,1** [69,9; 74,2] | 112 | %82,1 |
| ≤ 1,00 | 1 720 | %72,7 [70,5; 74,7] | 26 | %76,9 |
| ≤ 1,50 | 1 743 | %72,7 [70,6; 74,7] | 3 | (n<50, yazılmaz) |
| ≤ 2,00 | 1 746 | %72,7 [70,6; 74,8] | 0 | — |

**Okuma:** formasyonların **%93'ü** ömrü boyunca sınıra 0,5 ATR'den fazla
yaklaşıyor. Yani "yaklaştı" koşulu neredeyse her olayda doğru; ayırt edici bir
bilgi taşımıyor. "Yaklaşmayan" grup 112 gözlemle hem küçük hem de **daha
yüksek** tamamlanma gösteriyor — beklenenin tersi, ve fark GA içinde kalıyor
(örneklem gürültüsü).

Bu hâliyle cümle şöyle olurdu: *"sınıra 0,5 ATR yaklaşırsa %72 tamamlanır"* —
oysa koşulsuz oran da %72,7. Cümle hiçbir şey eklemiyor.

## 5 · Sonuç B — "şu kadar aşarsa" tek yönlü ve zayıf

| Aşım (ATR) | n | Tamamlandı | GA %95 |
|---|---|---|---|
| 0,01–0,25 | 340 | %73,5 | [68,6; 77,9] |
| 0,25–0,50 | 268 | %70,1 | [64,4; 75,3] |
| 0,50–1,00 | 297 | %67,7 | [62,2; 72,7] |
| 1,00–2,00 | 177 | %73,4 | [66,5; 79,4] |
| ≥ 2,00 | 166 | **%83,1** | [76,7; 88,1] |

**Okuma:** ilişki **monoton değil**. 0,5–1,0 ATR bandında tamamlanma *düşüyor*
(%67,7), 2 ATR üstünde yükseliyor (%83,1). Yalnız son kova ile ilk kova
arasındaki ~10 puan GA sınırında ayrışıyor; aradaki bantlar ters yönde.

Ayrıca "≥ 2 ATR aştıysa %83 tamamlanır" cümlesi **geç kalır**: fiyat sınırı 2 ATR
aştığında kırılım zaten olmuştur. Kullanıcının istediği "giderse tamamlanır"
cümlesi bir **beklenti** cümlesi; bunu ancak öncül (kırılımdan önce ölçülen)
değişkenle kurmak anlamlı olur ve öncül değişkenler (yakınlık) ayrıştırmıyor.

## 6 · Karar

**Koşullu cümle karta yazılmadı.** Gerekçe tek cümle: ölçülen iki koşuldan
birincisi (yakınlık) evrensel, ikincisi (aşım) monoton değil ve geç kalıyor.
Karta yazılsaydı, okuyanın "demek ki..." diye kuracağı çıkarım veride yoktu —
yani cümle **uydurma** olurdu. Kullanıcının kuralı: *"onaysız yazılmaz"*.

Kart bunun yerine ne yapıyor:

* FRM ailesi: `◇ 100 kırılımın 76'sı tuttu` + `◇ tutunca ~1,05 TL (≈%2,6)`
  (koşulsuz taban + tutanların lehte tepe hareketi),
* n<300 kesitlerde oran yerine `◇ nadir (162) · yorum yok`.

## 7 · Bu cümleyi yazmanın gerçekten mümkün olacağı yol

Bugünkü ölçüm "sonuç" ile "koşul"u aynı satırda tutuyor; cümle kurmak için
**zaman boyutlu risk kümesi** gerekir:

1. Her bar için `at_risk` durumu (formasyon canlı, kırılım henüz yok) ve o
   bardaki yakınlık ölçülür → sağdan sansürlü hayatta kalma modeli.
2. Öncül değişkenler: yakınlık (ATR), sıkışma, temas sayısı, hacim çeyreği,
   yapı uyumu — çok değişkenli, tek değişkenli tablolar değil.
3. **Örneklem dışı** doğrulama (zaman bölmeli): 2025-05→2026-03 eğitim,
   2026-04→2026-10 test. Aksi hâlde cümle arşive "uydurulmuş" olur.
4. Kalibrasyon eğrisi: "%60" dediğinde gerçekten %60 mı?

Bu dört adım tamamlanmadan kartta koşullu olasılık yazılmayacak. Ölçüm betiği
(`scripts/diagnostics/tamamlama_caprazi.py`) bu iş için başlangıç noktası olarak
duruyor; şu an "yazma" değil "yazma" kararını belgeliyor.

## 8 · Yeniden üretim

```bash
# 1) ölçüm çıktısı (tam evren, iki zaman dilimi)
.venv/bin/python scripts/backfill/arastirma_kosu.py \
    --timeframe 4h,1d --cikti arastirma_cikti --rapor-atla

# 2) çapraz tablo + aşım kovaları
.venv/bin/python scripts/diagnostics/tamamlama_caprazi.py \
    --dizin arastirma_cikti --asim
```
