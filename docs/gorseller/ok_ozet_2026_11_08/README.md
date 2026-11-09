# OK SİSTEMİ — görsel set (2026-11-08)

Bu klasör bir **indekstir**: tek sayfalık özet panosu + değişikliklerin kanıt görselleri.
Üretici: `research/ok_ozet_pano.py` · `PYTHONPATH=. .venv/bin/python research/ok_ozet_pano.py`

## 1. Pano

| Dosya | Ne gösteriyor |
|---|---|
| `00_pano.png` | Tek sayfa: 4 kare (iki katman, hacim, ◇ seyreltme) + ok sözlüğü + sayılar + tabanlı ölçüm sonucu |

## 2. Kanıt görselleri (kaynak klasörler)

### `docs/gorseller/ok_duzeltme_2026_11_08/` — iki katman birlikte + renk + sözlük (§8)
10 sembol, her karede **destek (yeşil) ve direnç (turuncu)** birlikte.
`ikikatman_aefes_uzak_uyari.png` · `ikikatman_aghol_ust_uste.png` · `ikikatman_agrot_uc_atr.png` ·
`ikikatman_aksen_tekrar.png` · `ikikatman_sise_kademe.png` · `ikikatman_thyao_gun_ici.png` ·
`ikikatman_cemas_yogun.png` · `ikikatman_alark_bes_bar.png` · `ikikatman_garan_dikey.png` ·
`ikikatman_akbnk_geri_alim.png` · sayımlar: `ikikatman_ornekler.json`
Üretici: `research/stabil_ok_ornek_gorseller.py`

### `docs/gorseller/ok_hacim_kapisi_2026_11_08/` — hacim şartı kalktı (§9)
Aynı kare, iki kod hâli: `hacim_once_*.png` / `hacim_sonra_*.png` + `karsilastirma_*.png`
(ALARK 1→2, AGHOL 1→2, CEMTS 2→3, AEFES 1→2, DOCO 2→3 dolu ▲).
Üretici: `research/stabil_hacim_kapisi_gorseller.py` (`once` · `sonra` · `karsilastir`)

### `docs/gorseller/ok_cizgi_seyreltme_2026_11_08/` — ◇ seyreltildi (§10)
Aynı kare, iki kod hâli: `cizgi_once_*.png` / `cizgi_sonra_*.png` + `karsilastirma_cizgi_*.png`
(ALARK 7→3, AGROT 6→2, AGHOL 4→2, CEMAS 3→1). ▲ okları birebir aynı.
Üretici: `research/stabil_cizgi_seyreltme_gorseller.py` (`once` · `sonra` · `karsilastir`)

## 3. Ölçümlerin kaynağı

| Betik | Ne ölçüyor | Süre |
|---|---|---|
| `research/stabil_ok_bayrak_replay.py` | ▲ bayrakları (kötü haber mi) | ~6 dk |
| `research/stabil_ok_taban_replay.py` | ▲ — tabanlı (kontrol'lü) üç yansıtma | ~6 dk |
| `research/stabil_direnc_taban_replay.py` | ▼ — tabanlı (kontrol'lü) üç yansıtma | ~40 sn |

Sonuçlar: `docs/arastirma/OK_SISTEMI_2026-11-08.md` §11 · §12 · §13.
