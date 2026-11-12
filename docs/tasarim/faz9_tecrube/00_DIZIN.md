# FAZ9 Tecrübe Sistemi — Ana Dizin (00_DIZIN)

> Bu klasör sistemin "öğrenme hattı"nın girişidir. Aşağıdaki sırayla okumak
> yeterlidir. Her satır ne olduğu ve neden önemli olduğuyla birlikte verilmiştir.

## Bu sistem nedir?

BIST grafiklerini **sırayla konuşan bir motor** gibi yorumlayıp plan üreten
`senaryo` motorunun (brifing sözleşmesi) geçmiş veri üzerinde **gölge zincir
replay** ile ölçülmesi ve ölçüm sonuçlarının **cümle/sahne tecrübesine**
dönüştürülmesi hattı. Canlı sistem değişmez; tüm iş gölge defter → ölçüm →
kapı (gate) disipliniyle yürür. "Önce ölç, karar sonra."

## Okuma sırası (sırayla)

| # | Dosya | Nedir? |
|---|---|---|
| 1 | `docs/tasarim/SENARYO_MOTORU_BRIFING_SOZLESMESI_2026-11-09.md` | **Ana sözleşme**: brifing modeli, TYR, işlem yaşam döngüsü, kırmızı çizgiler. Her kararın felsefi dayanağı. |
| 2 | `docs/tasarim/faz9_tecrube/FAZ9_PLAN_VE_SONUCLAR.md` | **FAZ9 planı + tüm sonuçlar**: ön-kayıtlar (§5 B-1, §7 B-turu), Tur A, B-1 RED, FAZ9-C düzeltmeli baz, B2/B3/B4 sonuçları. |
| 3 | `docs/arastirma/faz9_tecrube/TECRUBE_ENVANTERI.md` | **69 genel ders (A–I)** + B-1/B-turu ekleri. Domain cümlesi yazılacaksa önce burası (uydurma yasağı). |
| 4 | `docs/arastirma/faz9_tecrube/CUMLE_SICILI_SAHNE.md` | İlk cümle sicili + sahne ölçümü (dinamik EXPANDING/CONTRACTING/FLAT, kademe yönü ayrımları). |
| 5 | `docs/arastirma/ZARAR_TESHISI_A50_2026-11-11.md` | FAZ8 zarar teşhisi: domain izin formatı ayırt etmiyor, asıl ayrım giriş zamanlamasında, ön-gözlem filtreleri elendi. |
| 6 | `docs/tasarim/FAZ8_ANA50_EVRENI_2026-11-10.md` | FAZ8 kapısı: ilk7/7 geçişin (K2=+5,03) protokolü ve evren tanımı. |
| 7 | `docs/arastirma/ANA50_DETAYLI_SONUCLAR_2026-11-11.md` (+ `DIGER70_TEŞHIS`, `TEPEDEN_KLASIK`) | FAZ8 finansalları: n412, PF2,12, net+175,5A, kârlı%55,8 (SZINTI: sızıntılı tetik — §7.1'e bak). |
| 8 | `docs/tasarim/TAHMIN_KATMANI.md` §4 | Ölçüm→cümle kuralları (doğrulanmış iddia nasıl yazılır). |

Destek: `docs/arastirma/AMPIRIK_REFERANS.md` (ölçüm disiplini),
`docs/rehber/MASTER_PROMPT.md` (proje devri rehberi).

## Klasör düzeni

```
docs/tasarim/faz9_tecrube/        ← bu dizin + FAZ9 plan/sonuç belgesi (yaşar)
docs/arastirma/faz9_tecrube/      ← Envanter + Cümle Sicili (yaşar)
docs/arastirma/sonuclar/golge_zincir/
    ana50_semboller.txt            ← ana50 sembol listesi (tekrarlanabilirlik)
    kapi_karari_*.json             ← kapı kararları (b1, b2, b3, b4, faz9c_baz)
    olcum_faz8/                    ← Eski (sızıntılı) FAZ8 ölçümü — tarihsel
docs/arastirma/sonuclar/golge_zincir_faz9a/   ← FAZ9-A defteri (gzip, kayıt)
sonuclar/golge_zincir_faz9c_baz/   ← FAZ9-C düzeltmeli baz replay çıktısı
sonuclar/golge_zincir_faz9c_b2|b3|b4/  ← B-turu koşuları
research/golge_{zincir,olcum,kapi,inceleme,tecrube_rapor}.py  ← hat betikleri
```

## Temel komutlar

```bash
# Replay (ana50, bayraksız = düzeltmeli baz davranışı)
SEMBOLLER=$(tr '\n' ',' < docs/arastirma/sonuclar/golge_zincir/ana50_semboller.txt | sed 's/,$//')
python -m research.golge_zincir --semboller "$SEMBOLLER" --cikti sonuclar/<ad> [--b2-uyari|--b3-hedef|--b4-karakterli]

# Ölçüm → Kapı
python -m research.golge_olcum --defter sonuclar/<ad>/golge_defter.jsonl --cikti sonuclar/<ad>/olcum
python -m research.golge_kapi --olcum sonuclar/<ad>/olcum/olcum_ozet.json --cikti sonuclar/<ad>/kapi_karari.json

# Testler (G5 as-of kesme testleri dahil)
python -m pytest test_senaryo_zincir.py test_senaryo_plan.py -q   # hedefli
python -m pytest -q                                               # tam suite
```

## FAZ9 durum tablosu

| Adım | Mekanizma | Durum | Karar |
|---|---|---|---|
| Tur A | Aktif bildirim + sahne etiketi (yalnız kayıt) | ✅ bitti | Değişmezlik kanıtı:412/0/0,0 |
| FAZ9-C | G5 gelecek-sızıntısı düzeltmesi (as-of `i+1`) | ✅ bitti | Baz =200 plan,6/7 (K1=43) — danışmanla birebir |
| B-1 | CONTRACTING filtresi | ✅ bitti | **RED** (K1 47<50, net −62,1A) — Envanter §I |
| B-2 | Kademe-yukarı TYR uyarısı (`--b2-uyari`) | §7.3 ön-kayıt ✓ | sonuç: bkz. §7.6+ |
| B-3 | Formasyon üst sınırı hedef adayı (`--b3-hedef`) | §7.4 ön-kayıt ✓ | sonuç: bkz. §7.6+ |
| B-4 | Karakterli stop (`--b4-karakterli`) | §7.5 ön-kayıt ✓ | sonuç: bkz. §7.6+ |

## Kırmızı çizgiler (özet — sözleşme §10)

Ana sistem değişmez · çıktı = plan, sinyal değil · her karar-değişikliği
ön-kayıt + K1–K6 kapıyla ölçülür · eşikler değiştirilemez · sıfat yok sayı
var · uydurma yasağı · kapatılmış kollar yeniden denenmez (exit-side, stop
buffer, H≥25, rejim-AY filtresi, ön-gözlem giriş filtreleri) · **canlıya
bağlantı yok (kırmızı çizgi8)**.

*Son güncelleme: FAZ9-C baz + B-turu koşuları — FAZ9_PLAN_VE_SONUCLAR.md §7.*
