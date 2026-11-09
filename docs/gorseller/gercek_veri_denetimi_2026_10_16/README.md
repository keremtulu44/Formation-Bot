# Gerçek veriyle grafik denetimi — 16 Ekim 2026 kesiti

17 sembol için dört zaman diliminde **68 grafik**, ayrıca 1s ve 2s için eski
çizim politikasıyla **34 karşılaştırma karesi** üretildi. `_once.png` önceki
Stabil görünümünü açar; diğer dosya aynı veri ve domain çıktısının yeni
varsayılan çizimidir. Kayıtlı arşiv verileridir, güncel canlı fiyat değildir.

| Sembol | 1s | 1s önce | 2s | 2s önce | 4s | 1g |
|---|---|---|---|---|---|---|
| AKBNK | [son](AKBNK_1h.png) | [önce](AKBNK_1h_once.png) | [son](AKBNK_2h.png) | [önce](AKBNK_2h_once.png) | [son](AKBNK_4h.png) | [son](AKBNK_1d.png) |
| ASELS | [son](ASELS_1h.png) | [önce](ASELS_1h_once.png) | [son](ASELS_2h.png) | [önce](ASELS_2h_once.png) | [son](ASELS_4h.png) | [son](ASELS_1d.png) |
| ASTOR | [son](ASTOR_1h.png) | [önce](ASTOR_1h_once.png) | [son](ASTOR_2h.png) | [önce](ASTOR_2h_once.png) | [son](ASTOR_4h.png) | [son](ASTOR_1d.png) |
| BIMAS | [son](BIMAS_1h.png) | [önce](BIMAS_1h_once.png) | [son](BIMAS_2h.png) | [önce](BIMAS_2h_once.png) | [son](BIMAS_4h.png) | [son](BIMAS_1d.png) |
| EREGL | [son](EREGL_1h.png) | [önce](EREGL_1h_once.png) | [son](EREGL_2h.png) | [önce](EREGL_2h_once.png) | [son](EREGL_4h.png) | [son](EREGL_1d.png) |
| FROTO | [son](FROTO_1h.png) | [önce](FROTO_1h_once.png) | [son](FROTO_2h.png) | [önce](FROTO_2h_once.png) | [son](FROTO_4h.png) | [son](FROTO_1d.png) |
| GARAN | [son](GARAN_1h.png) | [önce](GARAN_1h_once.png) | [son](GARAN_2h.png) | [önce](GARAN_2h_once.png) | [son](GARAN_4h.png) | [son](GARAN_1d.png) |
| ISCTR | [son](ISCTR_1h.png) | [önce](ISCTR_1h_once.png) | [son](ISCTR_2h.png) | [önce](ISCTR_2h_once.png) | [son](ISCTR_4h.png) | [son](ISCTR_1d.png) |
| KCHOL | [son](KCHOL_1h.png) | [önce](KCHOL_1h_once.png) | [son](KCHOL_2h.png) | [önce](KCHOL_2h_once.png) | [son](KCHOL_4h.png) | [son](KCHOL_1d.png) |
| DOCO | [son](DOCO_1h.png) | [önce](DOCO_1h_once.png) | [son](DOCO_2h.png) | [önce](DOCO_2h_once.png) | [son](DOCO_4h.png) | [son](DOCO_1d.png) |
| PETKM | [son](PETKM_1h.png) | [önce](PETKM_1h_once.png) | [son](PETKM_2h.png) | [önce](PETKM_2h_once.png) | [son](PETKM_4h.png) | [son](PETKM_1d.png) |
| SAHOL | [son](SAHOL_1h.png) | [önce](SAHOL_1h_once.png) | [son](SAHOL_2h.png) | [önce](SAHOL_2h_once.png) | [son](SAHOL_4h.png) | [son](SAHOL_1d.png) |
| SISE | [son](SISE_1h.png) | [önce](SISE_1h_once.png) | [son](SISE_2h.png) | [önce](SISE_2h_once.png) | [son](SISE_4h.png) | [son](SISE_1d.png) |
| SNGYO | [son](SNGYO_1h.png) | [önce](SNGYO_1h_once.png) | [son](SNGYO_2h.png) | [önce](SNGYO_2h_once.png) | [son](SNGYO_4h.png) | [son](SNGYO_1d.png) |
| THYAO | [son](THYAO_1h.png) | [önce](THYAO_1h_once.png) | [son](THYAO_2h.png) | [önce](THYAO_2h_once.png) | [son](THYAO_4h.png) | [son](THYAO_1d.png) |
| TUPRS | [son](TUPRS_1h.png) | [önce](TUPRS_1h_once.png) | [son](TUPRS_2h.png) | [önce](TUPRS_2h_once.png) | [son](TUPRS_4h.png) | [son](TUPRS_1d.png) |
| YKBNK | [son](YKBNK_1h.png) | [önce](YKBNK_1h_once.png) | [son](YKBNK_2h.png) | [önce](YKBNK_2h_once.png) | [son](YKBNK_4h.png) | [son](YKBNK_1d.png) |

## Yöntem ve sınırlar

- Kaynak: depodaki `backfill_data/<sembol>_1h.csv.gz` ve `..._1d.csv.gz`;
  kaynak SHA-256 değerleri `kaynak_hashleri.json` dosyasındadır. 2s/4s, depo
  resampler'ı ile saatlik mumlardan, günlük mumlar yerel günlük seriden gelir.
- Kesit 16.10.2026 18:30 TSİ; yalnız o anda kapanmış mumlar, en çok son 500
  hedef TF mumu ve o anda bilinen üst TF verileri. Market Structure, OB, FVG,
  hacim, Stabil destek ve bağımsız direnç motorları izole çalıştırıldı; son
  fotoğraf projenin grafik zincirinde çizildi. 2s FVG üretim varsayılanıdır.
- Seçim, arşivde iki kaynağı bulunan çeşitli hisselerdir; rastgele ya da
  istatistiksel olarak temsili bir örneklem olduğu iddia edilmez. Formasyon
  adayı bu incelemede hesaplanıp grafiğe verilmedi; bu görseller formasyon
  çizgili alarm karelerinin kapsamlı denetimi değildir. Her TF için tek kesit
  kullanıldı. Araştırma/performance replay'i yapılmadı.
- `sonuclar.json` her karenin kapanışını, çizilen katmanlarının metaverisini,
  uyarı ve hata alanlarını içerir. 68/68 kare üretildi; direnç kaynak durumu
  68/68 `READY` idi. Kısa TF'lerde Stabil katmanları **çizimde** gizlidir;
  4s ve 1g'de her iki katman çizildi. Bu sayılar sinyal kalitesini ölçmez.
- Arşivdeki bazı saatlik açılış mumlarının hacmi sıfırdır; grafikteki hacim
  uyarısı kaldırılmadı. 4s direnç adaptörü bu kesitlerde 20 Nisan'daki eksik
  saatlik kovadan öncesini kırptı; eksik veri tamamlanmış gibi gösterilmedi.

## Bulgu ve uygulamalar

1. Örneğin [AKBNK 1s önce](AKBNK_1h_once.png) / [sonra](AKBNK_1h.png)
   ve [ASTOR 2s önce](ASTOR_2h_once.png) / [sonra](ASTOR_2h.png): günlük
   Stabil seviyeleri kısa vadeli mumlarla aynı karede ek çizgiler ve sağ
   etiketler oluşturuyor; büyük seviye değişimleri ayrıca kadrajı genişletebiliyor.
   Varsayılan 1s/2s karelerinde Stabil destek ve direnç çizgileri, bunların okları
   ve fiyat etiketleri gizlendi. Bu görsel sadeleştirmedir; motor hesapları,
   bağlam süzgeçleri, kartlar ve alarmlar değiştirilmedi. 4s/1g korunur.
2. [ASTOR 2s](ASTOR_2h.png): önceki yerleşimde çaba/sonuç `!` işaretleri
   altta tarih eksenine taşıyordu; artık yer darsa mumun üstüne taşınır. Yapı
   olayı bulunmadığında aynı işaretlerin yanlışlıkla çizilmemesi de giderildi.
3. [ASELS 1g](ASELS_1d.png) ve [GARAN 4s](GARAN_4h.png): destek/direnç,
   yapı ve bloklar birlikte gösterilir; uzun TF'lerde katmanlar kaldırılmadı.
   Bu tek karelerin okunabilir olması her piyasa durumunu doğrulamaz.

Görseller `python scripts/stabil_grafik_denetim.py --output <ayrı-dizin>
--kisa-karsilastirma` ile yeniden oluşturulabilir. Tanı amacıyla kullanılan
`stabil_goster=True` çizim seçeneği yalnız karşılaştırma karelerinde varsayılanı
geçersiz kılar; canlı veriye veya `bot_data`'ya yazılmaz.
