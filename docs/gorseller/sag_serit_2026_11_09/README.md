# Sağ fiyat şeridi — gerçek veriyle önce / sonra

Bu örnekler `backfill_data` arşivinin **16 Ekim 2026** kesitidir; canlı fiyat
değildir. Dört sembol × dört TF, üretim grafik sistemiyle yeniden çizildi.
Önceki grafiğe ve yeni grafiğe aynı satırdan bakabilirsiniz:

| Sembol | 1s önce → sonra | 2s önce → sonra | 4s önce → sonra | 1g önce → sonra |
|---|---|---|---|---|
| AKBNK | [önce](../gercek_veri_denetimi_2026_10_16/AKBNK_1h.png) → [sonra](AKBNK_1h.png) | [önce](../gercek_veri_denetimi_2026_10_16/AKBNK_2h.png) → [sonra](AKBNK_2h.png) | [önce](../gercek_veri_denetimi_2026_10_16/AKBNK_4h.png) → [sonra](AKBNK_4h.png) | [önce](../gercek_veri_denetimi_2026_10_16/AKBNK_1d.png) → [sonra](AKBNK_1d.png) |
| ASTOR | [önce](../gercek_veri_denetimi_2026_10_16/ASTOR_1h.png) → [sonra](ASTOR_1h.png) | [önce](../gercek_veri_denetimi_2026_10_16/ASTOR_2h.png) → [sonra](ASTOR_2h.png) | [önce](../gercek_veri_denetimi_2026_10_16/ASTOR_4h.png) → [sonra](ASTOR_4h.png) | [önce](../gercek_veri_denetimi_2026_10_16/ASTOR_1d.png) → [sonra](ASTOR_1d.png) |
| ASELS | [önce](../gercek_veri_denetimi_2026_10_16/ASELS_1h.png) → [sonra](ASELS_1h.png) | [önce](../gercek_veri_denetimi_2026_10_16/ASELS_2h.png) → [sonra](ASELS_2h.png) | [önce](../gercek_veri_denetimi_2026_10_16/ASELS_4h.png) → [sonra](ASELS_4h.png) | [önce](../gercek_veri_denetimi_2026_10_16/ASELS_1d.png) → [sonra](ASELS_1d.png) |
| GARAN | [önce](../gercek_veri_denetimi_2026_10_16/GARAN_1h.png) → [sonra](GARAN_1h.png) | [önce](../gercek_veri_denetimi_2026_10_16/GARAN_2h.png) → [sonra](GARAN_2h.png) | [önce](../gercek_veri_denetimi_2026_10_16/GARAN_4h.png) → [sonra](GARAN_4h.png) | [önce](../gercek_veri_denetimi_2026_10_16/GARAN_1d.png) → [sonra](GARAN_1d.png) |

## Yapılanlar

- Son fiyat dolu renkli çip olarak kalır; destek ve direnç etiketleri de diğer
  seviye etiketleri gibi ince renkli çerçeveyle ayrışır. Mevcut renk anlamları,
  fiyatlar, kutu dolum bilgileri ve yapı adları değiştirilmedi.
- Kaydırılan etiketlerin lider çizgisine sabit piksel boşluğu bırakıldı; çizgi
  hâlâ ilgili gerçek fiyat seviyesine bağlanır. Son fiyat yerinden kaydırılmaz.
- Uzun etiketler `…` ile kesilmek yerine satıra sarılır; birleşen etiketlerdeki
  tekrarlı ve farklı parçalar da korunur. PH/PL gibi yapı rolü, son fiyatla aynı
  seviyedeyken sırf fiyat tekrar ediyor diye artık gizlenmez.
- 16 örneğin tümü üretildi; sağ şerit metaverisinde bu örneklerde sıfır yer
  darlığı atlaması ve sıfır kaynak kotası elemesi kayıtlı (`sonuclar.json`).

**Sınır:** Var olan odak görünümü ve şerit kaynak kotaları değiştirilmedi;
aşırı yoğun bir karede fiziksel yer yetersizliği veya önceki kota politikası
hâlâ etiket eleyebilir. Dolayısıyla her olası karede tüm adayların ekranda
olduğu garanti edilmez; sayılar metaveride bildirilir. Bu değişiklik yeni bir
veri veya sinyal filtresi eklemez. Görsellerde formasyon adayı yoktur.

Üretim: `python scripts/stabil_grafik_denetim.py --output <dizin> --symbols
AKBNK ASTOR ASELS GARAN --tfs 1h 2h 4h 1d`. Kaynak hashleri ve diğer 17
sembollük örnekler [önceki incelemede](../gercek_veri_denetimi_2026_10_16/README.md).
