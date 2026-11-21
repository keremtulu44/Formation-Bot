# Alarm Politikası — P6 Canlıya Alındı (2026-11-21)

**Durum:** UYGULANDI · **Karar:** `YENI_DOMAIN_ALARM_POLITIKA=P6` (varsayılan)
**Ölçüm kaynağı:** 22 seans · 50 sembol × 4 TF · 2026-10-19 → 2026-11-18
**Kod:** `bot/domain_alarm_service.py::_politika_gecer` · `config.py`
**Kapı:** canlı filtre ↔ replay formülü **300 seride 0 fark**

---

## 1. Sorun

Birleşik domain kartı (`🆕 YENİ`) her BOS/OB/FVG/formasyon/hacim tetiğinde
basılıyordu. 22 seanslık ölçümde **2.136 kart = 97 kart/seans** (günde 97 DM).
Kullanıcı geri bildirimi tek cümleydi: *"sonuç çıkmıyor"* — aslında tersi:
çok fazla kart çıkıyordu, bu yüzden hiçbiri sinyal gibi okunmuyordu.

## 2. Politika tanımları

`research/alarm_politika.py` içinde 8 politika tanımlı. Canlıya alınabilir üçü:

| Politika | Kural | Kart | Kart/seans | Yönlü isabet | Güçlü yakalama |
|---|---|---:|---:|---:|---:|
| **P0** | her tetik (eski davranış) | 2.136 | 97,09 | %67,8 | %33,3 |
| **P6** ✅ canlı varsayılan | yalnız bağlam | 785 | 35,68 | %67,1 | %12,0 |
| **P4** | katman + bağlam | 500 | 22,73 | %69,2 | %8,2 |

> **Sayı okuma notu:** yukarıdaki tablo `research/alarm_politika.py` çıktısıdır
> ve **cooldown uygulanmış** hâlidir. Aynı örneklemde ham tetik sayısı 9.087;
> cooldown + politika sonrası gerçek teslim sayısı (canlı `dispatch` ile uçtan
> uca doğrulandı): P0 **2.531**, P6 **902**, P4 **499**. Oranlar aynı
> (97/36/23 → 115/41/23), çünkü iki tablo farklı gün sayısına bölünüyor.

Diğerleri (P1/P2/P3/P5/P7: 2.061 / 47 / 1.415 / 711 / 811 kart) aynı örneklemde
ölçüldü; isabet **%67–73 bandında** kalıyor, yani politika isabeti değil **kart
sayısını** değiştiriyor. Karar bu yüzden "hangi kart kullanıcıya değer katıyor"
sorusuna indi.

### Bağlam nedir (nedensel, geleceğe bakmaz)

- `bagl_sikisma` = son 10 barın aralığı / son 50 barın aralığı.
  <1 daralma. Politika eşiği: **≥ 1.0** (sıkışma çözülmüş, genişleme başlamış).
- `bagl_gunici_kosu` = son 6 barın yönlü kapanış farkı / ATR.
  Politika eşiği: **≥ 1.0 ATR** (hareket gerçekten başlamış).

P6 = `sikisma >= 1.0` **VEYA** `kosu >= 1.0`.

### P4'ün katmanı

P3 katmanı + bağlam: yalnız `OB`, `FVG`, `BOS`, `CHoCH` kanallarından gelen
tetikler **bağlama bakılmadan sessiz**; `formasyon` ve `hacim` kanalları bağlam
ister; **hacim ≥ 5× bağlamı baypas eder** (olağandışı hacim kendi başına sinyal).

## 3. Neden P6 seçildi

- 97 → 36 kart/seans: kullanıcının "telefon susmuyor" şikâyeti çözülür.
- İsabet neredeyse sabit (%67,8 → %67,1): filtrenin kazandırdığı **kalite değil,
  sükûnet**. Bunu kullanıcı onayladı; %33,3 → %12,0 güçlü yakalama düşüşü
  bilinçli kabul edildi.
- P4 daha az kart (23) ve daha iyi isabet (%69,2) verir ama güçlü yakalamayı
  %8,2'ye indirir; BOS tek başına sessizleştiği için yapı kırılımları kaybolur.
  P6 yapı kanallarını korur, yalnız bağlamsız olanları atar.

## 4. Uygulama

```
config.py                       YENI_DOMAIN_ALARM_POLITIKA=P6 (fail-open → P0)
bot/domain_alarm_service.py      _baglam_sikisma_kosu()  → sikisma, kosu
                                 _kanallar_from_sebepler() → replay kanal kümesi
                                 _politika_gecer()       → P0/P6/P4 hükmü
                                 evaluate_...() içinde filtre (dedup'tan ÖNCE)
```

Filtre aday üretiminde çalışır; dedup/cooldown/kuyruk/teslimat yolu
değişmez. P0 dışında bir politika seçildiğinde elenen adaylar `DEBUG`
seviyesinde gerekçesiyle loglanır.

### Replay paritesi (kritik)

Canlı `_baglam_sikisma_kosu` ile replay `baglam_satiri` **birebir** aynı
formülleri kullanır:

- sıkışma: aynı pencere (son 10 / son 50 bar), aynı `index >= 50` eşiği
- koşu: aynı 6 bar, aynı Wilder-14 ATR, aynı `index >= 13` eşiği
  (replay `compute_wilder_atr` ilk ATR'yi 14. barda üretir; canlı da artık
  aynı eşiği uygular — aksi halde erken barlarda canlı üretip replay `None`
  derdi)
- `None` semantiği: sıkışma `None → 1.0` (fail-open), koşu `None → 0.0`

Doğrulama: `python -m scripts.politika_parite_kontrol --seri 300`
→ **300/300 seri, 0 fark**. Bu komut politika değişikliğinden sonra da
çalıştırılmalıdır; parite bozulursa aşağıdaki sayılar geçersizdir.

## 4b. Cooldown düzeltmesi (aynı turda, kritik)

P6 canlıya alınırken **ikinci bir hata** bulundu ve düzeltildi: dedup anahtarı
`sembol|TF|bar_open` idi. Her yeni mum yeni bir slot açtığı için
`_zaten_gonderildi` slotun `last_bar_index`'ini hiç bulamıyor,
`YENI_DOMAIN_ALARM_COOLDOWN_BAR=6` **pratikte uygulanmıyordu**. Yalnız "aynı
barı iki kez basma" çalışıyordu.

Sonuç: P6 canlıda 41 değil **~89 kart/seans** üretecekti (1.954 kart). Yani
ölçülen düşüşün yaklaşık yarısı cooldown'a aitti ve o yarı canlıda yoktu.

Düzeltme:
- `dedup_key` = `sembol|TF` (state slotu, cooldown düzeyi)
- `bar_key` = `sembol|TF|bar_open` (aynı barı iki kez basma + burst gruplaması)
- negatif indeks farkı da sessizlik sayılır (bar yeniden çekilirse)
- `_save_state` artık **atomik** (`tmp` + `os.replace`); yarım yazılmış JSON
  deploy sonrası tüm cooldown slotlarını kaybettiriyordu

Uçtan uca doğrulama (replay tetikleri → gerçek `dispatch_domain_alarm_candidates`):

| Politika | Canlı dispatch (düzeltme öncesi) | Canlı dispatch (sonrası) | Replay |
|---|---:|---:|---:|
| P0 | 7.699 | 2.531 | 2.531 ✅ |
| **P6** | 1.954 | **902** | 902 ✅ |
| P4 | 807 | 499 | 499 ✅ |

## 5. Testler

- `test_domain_alarm_politika.py` (15 test): sıkışma/koşu formülleri, kısa
  çerçeve fail-open, ATR-14 eşiği, kanal eşleme, P0/P6/P4 hükmü, bilinmeyen
  politika → P0, üç uçtan uca `evaluate` senaryosu.
- `test_stabil_resistance_delivery_e2e.py` ve
  `test_stabil_resistance_chart_integration.py`: P0'a sabitlendi — bu dosyalar
  kanal tesisatını (albüm gruplaması, dedup, metin/grafik paritesi) ölçer,
  politika seçiciliğini değil. Aksi halde gerçek arşiv adayları P6 altında
  elenip tesisat testleri yanlış yere kırılıyordu.
- Cooldown regresyonları (`test_domain_alarm_service.py`): sonraki barlarda
  susma, farklı sembol/TF'nin etkilenmemesi, eski bar anahtarlı state uyumu,
  `dedup_key`/`bar_key` semantiği.
- Tam paket: **4.756 passed / 43 skipped**, `ruff` temiz.

## 6. Geri alma

```
YENI_DOMAIN_ALARM_POLITIKA=P0     # eski davranış, tek env değişkeni
YENI_DOMAIN_ALARM_POLITIKA=P4     # daha seçici varyant
```

Deploy sonrası ilk 2–3 seansta kontrol edilecekler:

1. `🆕 YENİ` kart sayısı ≈ **36/seans** (P0'da 97 idi). Belirgin sapma varsa
   canlı ile replay örneklemi farklıdır (evren/TAZE_DK/cooldown).
2. Kaybolan kartların gerekçesi logda `politika P6 ile elendi` satırında
   `sikisma`/`kosu` değerleriyle görünür — "sinyal mi kaçtı, gürültü mü elendi"
   sorusu buradan cevaplanır.
3. Hacim ≥5× kartları hâlâ geliyor mu (P6 bunları da bağlama tabi tutar; P4
   tutmaz). Sessizleşme istenmiyorsa P4'e geçilir.

## 7. Açık kalan

- Politika **kart sayısını** düşürüyor, isabeti artırmıyor. Kalite artışı için
  ayrı iş gerekir (kanal bazlı ağırlık, seans filtresi P5, bağlam eşiklerinin
  holdout ile kalibrasyonu).
- Ölçüm 22 seans / tek dönem. Farklı rejimde (yükseliş vs yatay) kart/seans
  oranı kayabilir; `PILOTU` yeniden koşulmadan eşik değiştirilmemeli.
