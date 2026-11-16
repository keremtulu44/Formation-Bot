# Grafik adımları + Stabil ok replay fikirleri — 2026-11-15

## A. Önceki önerilerin adım adım uygulanması

Önce doğrulama: bazı öneriler kodda zaten vardı (hacim paneli FAZ 1'de
bilinçli kaldırılmış, RVOL rozeti taşıyor; footer üretimde kareden çıkarılmış;
etiket çakışması için `_sag_sirali_yerlesim` + lider çizgisi; renk körü modu;
hedef projeksiyonu). Bunlar geri alınmadı. Eksik olanlar uygulandı:

| Adım | Durum | Ne değişti |
|---|---|---|
| 1. Dinamik sağ şerit | ✅ | `_sag_serit_px_hesapla`: en uzun aday etikete göre 84–195 px (mobil ≤230). Etiketsiz karede mum alanı ~%10-15 büyür. `meta["kare"]["sag_serit_px"]` |
| 2. VERİ EKSİK rozeti | ✅ | `son_bar_ts` yoksa kırmızı **VERİ EKSİK**, son mum açıksa turuncu **SON MUM AÇIK** köşe rozeti; `meta["veri_rozeti"]`. Replay'de yok (tarih bilinçli gizli) |
| 3. Ok türü taşıma | ✅ | Snapshot artık `reclaim_turleri/momentum_turleri` (destek) ve `donus_turleri/momentum_turleri` (direnç) taşır |
| 4. Ok kademesi (destek) | ✅ | Bkz. §B — replay'e dayalı görsel kademe, filtre değil |
| 5. Hacim paneli / footer / çakışma / renk körü | ⏸ zaten var | FAZ 1 kararları korunarak geri alınmadı; gerekçe bu dosyada |

Örnekler: `docs/gorseller/ornek_ok_kademesi_2026_11_15.png`,
`docs/gorseller/ornek_veri_rozeti_2026_11_15.png`

## B. Stabil oklar — kayıtlı replay'i gerçekten okuyarak

Kaynak: `docs/arastirma/stabil_ok_replay_2026_11_05/events.csv.gz`
(174 hisse, 4.775 olay; geçerli 555 ▲, 8 bar, MFE<0,5 ATR = zayıf tepki).
Yeniden koşu: `python scripts/stabil_ok_kalite_analizi.py`

### Ölçülen (baz zayıf %24,9)
| Grup | n | Zayıf % | +1 ATR önce % |
|---|---:|---:|---:|
| `upward_rebase_momentum` | 75 | **17,3** | **58,7** |
| `close_reclaim` (çok mumlu dahil) | 255 | 23,1 | 46,3 |
| `long_base_breakout` | 63 | 28,6 | 49,2 |
| `intrabar_sweep_reclaim` | 162 | **29,6** | 51,2 |
| Rejim `HORIZONTAL_AFTER_DROP` | 213 | 29,6 | 45,5 (−1 önce %51,2) |
| Yalnız FVG yakın (OB değil) | 56 | 32,1 | 46,4 |
| Çizgiye 0,1–0,5 ATR | 134 | 20,1 | 53,0 |

### Uygulanan fikir (görsel kademe — sinyal kararı DEĞİL)
Replay gözlemsel olduğu için ok bastırma/filtre yapılmadı; yalnız grafik
vurgusu kademelendi:
- çok mumlu/kapanış geri alımı: **dolu ▲ tam** (gid `…-reclaim`)
- fitil süpürmesi: **dolu ▲ küçük+soluk** (alpha 0,55, `…-reclaim-supurme`)
- `upward_rebase_momentum`: **içi boş ▲ büyük** (`…-momentum`)
- `long_base_breakout`: **içi boş ▲ küçük+soluk** (alpha 0,60, `…-momentum-taban`)
- Eski (türsüz) snapshot: önceki görünüm korunur.
- **Direnç tarafına uygulanmadı:** direnç oklarının ayrı replay'i yok;
  destek ölçümünü aynaya varsaymak bu çalışmanın kendi kuralına aykırı.
  Önce `stabil_resistance_replay` ile aynı tablo çıkarılmalı.

### Replay'in REDDETTİĞİ fikirler (uygulanmadı, gerekçesiyle)
- **Hacim filtresi/rozeti kademesi:** düşük %25,3 ≈ yüksek %24,6 (fark
  +0,6 puan, bootstrap %95 GA −8,8…+10,3). "Sessiz günde oku soluklaştır"
  veriye dayanmıyor.
- **Gövde büyüklüğü kademesi:** gövde >0,6 ATR daha kötü (%26,8).
  "Büyük gövde = güçlü ok" sezgisi replay'de yok.
- **Bastırılmış adaylar kalan oklardan kötü değil:** dikey bastırılan eski
  adaylar %20,5 zayıf / %53,4 +1 önce — kalan ▲ %24,9 / %49,7. Farklı
  popülasyonlar; "dikey bastırmayı gevşet" sonucu çıkarılamaz ama
  ▼ uyarısının düşüş sinyali gibi sunulması da desteklenmiyor (mevcut
  ◇ tasarımı doğru yön).

### Sonraki replay fikirleri (ölçülmeden uygulanmayacak)
1. Direnç okları için aynı events tablosu (`donus_turleri` artık snapshot'ta;
   replay üretimi sıradaki iş).
2. `HORIZONTAL_AFTER_DROP` rejiminde okları soluklaştırma hipotezi: fark
   büyük (%29,6 ve −1 ATR önce çoğunlukta) ama rejim proxy'si ve saat
   karıştırıcısı (17:30/18:00 barları daha zayıf) ayrıştırılmadan uygulanmaz.
3. "Yalnız FVG yakınken ek işaret" hipotezi (%32,1, n=56): payda küçük,
   OB ile birlikteyken fark kapanıyor (%25,9) — önce birleşik tablo.
4. 1s/2s ok replay'i hiç yok; 4s/1g bulgusu kısa TF'ye taşınmaz.
5. Bastırılan adayların daha iyi performansı: nedensel olmayan seçim
   farkı mı, dikey proxy yanlış pozitif mi — kullanıcı görsel etiketiyle
   (STABIL_REPLAY_HATLARI'ndaki açık soru) ölçülmeli.

## C. Test
- Yeni: `test_grafik_serit_ve_ok_kademesi.py` (3 test)
- Grafik + stabil grafik köprüsü/entegrasyon/teslim: 340 test geçti
  (pinli ortam: pandas 2.2.2 — önceki pandas 3.x sahte arızaları yok).
