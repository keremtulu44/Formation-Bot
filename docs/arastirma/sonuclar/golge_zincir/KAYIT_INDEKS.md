# Gölge Zincir Koşu Kayıt İndeksi (2026-11-12)

> Amaç (dış denetçi ölçütü): **repodan sıfırdan kapı hesabı ≤5 dakika** ve
> **hiçbir karar-belgesi sızıntısız/doğrulanamayan sayı sunmasın.**
> Bu dizindekiler commit'lidir; büyük `golge_defter.jsonl` gitignore'dadır
> (`.gitignore` `docs/arastirma/sonuclar/**/golge_defter.jsonl*`).

## Bağlayıcı özetler (küçük artefaktlar — commit'li)

| Koşu | Dizin | Kapı | K1 | K2 | K3 | plan | GA95 K2 | GA95 K3 |
|---|---|---|---|---|---|---|---|---|
| FAZ9-D baz176 (audit'li) | `faz9d_baz_176/` | **GEÇMEDİ (4/7)** |141 | +2,88 | −0,1197 |633 | [−7,10 ; +12,87] | [−0,407 ; +0,148] |
| FAZ9-D B4-176 | `faz9d_b4_176/` | **GEÇMEDİ (4/7)** |131 | +3,32 | −0,1073 |554 | [−7,10 ; +14,41] | [−0,387 ; +0,187] |

Her dizinde: `olcum/{plan_sonuc.csv, kor_baz.csv, olcum_ozet.json}` +
`kapi_karari.json` + `ozet.json` (boru hattı özeti).
GA'lar **rapor katmanıdır** (sembol-gruplu bootstrap, B=2000, tohum=42) —
kapı eşiği değildir; K2/K3'ün0'ı içerdiği görünür.

## Determinizm pasaportu (sha256)

| Dosya | sha256 | Boyut |
|---|---|---|
| faz9d_baz_176/golge_defter.jsonl | `933244755ee4a1e9ab1bee923c9dc84d929a1fbb708d38e541632f15b0c5906a` |333.263.270 B |
| faz9d_b4_176/golge_defter.jsonl | `14000b41ae0fc6e9d732fb173bebe505da42efb88da0e930cc7803fe2dbac76b` |333.206.990 B |
| evren176_semboller.txt | `c7dbdfe343a643f785033fba75e53a8450becbf2eeb7328d86bb450abffe2c20` |176 satır |
| ana50_semboller.txt | `0726c3bf3f046b3dde28f01cc2711a51052b57e2ee57e71d4a52d2f0c92cd242` |50 satır |

Pasaport ayrıca her `olcum_ozet.json["pasaport"]` alanındadır (python/pandas
sürümü + defter sha256 + plan/sembol sayısı) ve kapı JSON'una taşınır.

## Yeniden üretim (≤5 dakika — ölçüldü:20sn + anlık kapı)

```bash
#1) defter yoksa boru hattı (~60 dk/176 seri, arşiv backfill_data/ repo'da):
SEMBOLLER=$(tr '\n' ',' < docs/arastirma/sonuclar/golge_zincir/evren176_semboller.txt | sed 's/,$//')
python -m research.golge_zincir --semboller "$SEMBOLLER" --cikti <dizin> [--b4-karakterli]

#2) ölçüm + kapı (defter varsa):
python -m research.golge_olcum --defter <dizin>/golge_defter.jsonl --cikti <dizin>/olcum
python -m research.golge_kapi --olcum <dizin>/olcum/olcum_ozet.json --cikti <dizin>/kapi_karari.json
```

## Tarihçe notu (denetçi uyarısı gerçek oldu)

- Bu dizindeki ilk artefaktlar2026-11-1214:01 sandbox sıfırlamasında
  **kayboldu** (`sonuclar/` gitignore → temiz klon yok) — dış denetçinin
  "commit etmezseniz bir daha doğrulanamaz" uyarısı saatler içinde doğrulandı.
- **Kurtarma:** arşiv `backfill_data/` commit'li olduğundan koşular aynı
  komutla tekrar üretildi; **sonuç sayıları ilk koşularla birebir tuttu**
  (baz: hedef143/stop253/zaman237 · B4:120/211/222; kapı:141/2,88/−0,1197 ve
  131/3,32/−0,107) → determinizm fiilen kanıtlandı.
- Küçük çıktılar artık koşuyla birlikte **bu dizine** yazılır (defter hariç).

## Audit-öncesi (ana50) koşular — sayılar FAZ9 §8'de; şeritli belgeler

`kapi_karari_faz9b1.json` + `olcum_faz8/` (2026-11-11 öncesi) bu dizinde;
kaynak belgeleri sızıntı şeritlidir (bkz. §8 + GEÇERSİZ KAYNAK şeridi).
