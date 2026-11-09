# ◇ ikinci tur — 20 → 50 bar (8 Kasım 2026)

`docs/arastirma/OK_SISTEMI_2026-11-08.md` **§14.3 (ölçüm)** ve **§14.6 (uygulama)**'nın kanıtı.

Karar: zayıf ◇ soğuması **20 → 50 bar**. Yalnız `weak_reclaim` / `touch_from_below` denemelerine
uygulanır; güçlü ◇, ▲ okları ve momentum **değişmedi**.

## Sayılar (günlük 50 sembol · 25.051 bar · üretim kodu çalıştırıldı)

| Ölçüm | 20 bar (önce) | 50 bar (sonra) |
|---|---|---|
| ◇ toplam | 486 | **364 (−%25)** |
| Sembol başına medyan | 10 | **7** |
| En yoğun sembol | 15 | **13** |
| Dolu ▲ | 195 | **195** |
| Momentum ▲ | 51 | **51** |

## Kareler
| Dosya | İçerik |
|---|---|
| `karsilastirma_cizgi_*.png` | Aynı kare, iki kod hâli: üstte 20 bar (§10), altta 50 bar. ▲ okları birebir aynı |
| `cizgi_once_*.png` / `cizgi_sonra_*.png` | Karşılaştırmanın tam kareleri |
| `cizgi_once.json` / `cizgi_sonra.json` | Kare başına işaret sayıları (◇ / dolu / momentum) |

5 örnek karede ◇ 14 → 12; fark kısa pencerede küçük, uzun geçmişte birikiyor (486 → 364).

## Yeniden üretmek için
```bash
export GORSEL_KLASOR=docs/gorseller/ok_cizgi_ikinci_tur_2026_11_08
export GORSEL_ONCE_ETIKET="ÖNCE · ◇ 20 barda bir (§10)"
export GORSEL_SONRA_ETIKET="SONRA · ◇ 50 barda bir (~2,5 ay)"
PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_gorseller.py once
PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_gorseller.py sonra
PYTHONPATH=. .venv/bin/python research/stabil_cizgi_seyreltme_gorseller.py karsilastir
```
(`once` = `HEAD` sürümü; bu klasörün kareleri HEAD 20 bar iken üretildi.)
