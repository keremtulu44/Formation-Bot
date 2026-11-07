# 50-hisse direnç/destek araştırması — doğrulama

## Kapsam ve veri

- [Seçim](selection.json), eski 100-hisselik destek evreni ile önceki direnç
  evreninin kesişiminden sabit SHA256 sırasıyla 50 isimdir; hisse bazında önceki
  sonuçlar seçime girdi olarak kullanılmadı. Bu, eski kolayda örneklemin seçilim
  yanlılığını devralır. Veri daha önce incelendiğinden 2026 kör doğrulama değildir.
- Replay 50/50 hisseyi işledi, hata yok. 10.097 adet destek/direnç 4s olayı,
  10.494 günlük native olay ve 94.705 eski-soruya-benzer checkpoint oluştu.
  Geçersiz ve sağdan sansürlü gözlemler oran paydalarından çıkarılmış, sayıları
  veri/özetlerde tutulmuştur; tüm kapanış zamanları İstanbul saatidir.
- Seçili arşivlerde 25.000 günlük ve 53.528 4s bar var; 776 eksik/içeriği
  tamamlanmamış 4s kova, 357 tamamen eksik 4s kova ve toplam 3 şüpheli günlük
  bar belirlendi. Kalite filtresi kapsanan ilgili geçmiş/ufku sansürler. Bu
  sayımların olaya etkisi dönem ve ölçüme göre farklıdır, tüm seriyi silmez.
- Tam 24-bar yollarda 1.789 kırılma adayından 1.373'ü geçerlidir. Sadece 2026
  direncinde 459 kırılmanın 371'i geçerli 24-bar yol oluşturur. **Hisse sayısı,
  olay sayısı ve geçerli alt grup paydası birbirinin yerine kullanılmamalıdır.**

## Başarılı kontroller

1. [Eş-kural verifier](verification.json): `OK`; kaynak karşılaştırma manifestindeki
   349 arşiv dosyası hash'i ve 9 kaynak hash'i kontrol edildi (349, mevcut
   kaynak manifestindeki bütün dosya sayısıdır; 50 seçili hisse sayısı değildir).
   DOCO'da A01/B04/C02/F01 eski-değerlendirici yakınlaştırması ve 166/333/499
   uzunlukta nedensel-prefix kontrolleri geçti. 61 aday eşleşmeden 53 geçerli çift.
2. [Yol verifier](path_verification.json): `OK`; manifest ve 1.373 geçerli yol
   kontrol edildi. DOCO'da 15 destek ve 22 direnç yolu orijinal fiyatlarla ayrıca
   karşılaştırıldı; aynı-bar ihtimalleri karar gibi sıralanmadı.
3. [Odak verifier](focused_verification.json): `OK`; 50'li seçimi tekrar kurdu;
   plan, kod, girdi ve çıktı hash'lerini kontrol etti; 16 F01 ve 4 temas/kapanış
   alt grubunu, 4.741 geçerli B04 satırının kümesini ve 205 sabit-çizgi yolunun
   eşlenmesini kontrol etti. DOCO için 94 B04 kapanış sonucu ile 8 sabit çizgi
   yolunu orijinal fiyatlardan bağımsız tekrar saydı. Ayrıca başlangıçta yeni
   direncin üzerinde fiyat görülen altı 2026 olayının **tamamı** orijinal fiyat
   ve teyitli çizgi kimliğinden yeniden kontrol edildi: DMSAS, DYOBY, EFOR,
   GARAN, HATSN, KFEIN.
4. `.venv/bin/python -m pytest -q test_stabil_*.py --disable-warnings --maxfail=1`:
   **81 geçti**. İlgili araştırma ve test dosyalarında Ruff: **All checks passed**.
   Sabit çizgide eşit kapanışın kesin alt/üst kapanış sayılmaması, yön aynalaması
   ve aynı-bar belirsizliği ayrıca birim testlerinde ele alındı.

[Karşılaştırma manifesti](manifest.json), [yol manifesti](path_manifest.json),
[sabit-çizgi manifesti](fixed_line_manifest.json) ve [odak manifesti](focused_manifest.json)
plan/kod/girdi/çıktı hash'lerini taşır. İnsan okunur [odak raporu](RAPOR_50.md),
[genel tablolar](toplu_bulgular.md), [kırılma yolları](yol_bulgulari.md) ve
[fiyat-koşulsuz sabit çizgi yolları](sabit_cizgi_yollari.md) ayrı verilmiştir.

## Yorum sınırları

- Yakınlık bandına girme `TEST`, gerçek temasla aynı değildir. Gerçek temas
  aralığın çizgiyi kapsamasıdır; gap'le çizgiyi atlamak temas sayılmaz. Temas
  mumunda güvenli kapanış ve sonraki ±1 4s ATR hareketi ayrı ölçülür; temas
  mumunun içindeki işlem sırası bilinmez.
- Destek güvenli kapanışı çizgiye eşit/üst, direnç güvenli kapanışı eşit/alttır.
  Eşitlik, **kesin altına/üstüne geçti** diye sunulmaz. Sabit çizgi ek özetinde
  kesin taraf geçişi ayrıca sayıldı. Kırılma yolunda ters adım ölçüsü >0,01 fiyat
  birimidir; yeni çizginin sonraki değişimi native kimlikle izlenir.
- 4/8/16/24 barlar sonuç ölçüm pencereleridir; canlıya yeni bir onay veya
  bekleme eklenmedi. Dalların orijinal 24-bar pencerede kalan süreleri değişkendir;
  hiç bar kalmaması ayrıca gösterilir. Tekrarlanan olaylar ve aynı piyasa günleri
  bağımsız değildir; sağkalım veya yatırım getirisi hesaplanmamıştır.
- F01'de kullanılan aday düz rejim, günlük kapanışın güvenli tarafta olmasını
  zaten içerir. Sabit native çizgi ek kontrolü bu fiyat koşulunu **giriş
  filtresi yapmaz**; ancak sabit bir stepline segmenti kullanıcının görsel
  “yatay” rejimiyle aynı ilan edilemez. İlk yukarı taşınmada fiyat yeni
  direncin üstündeki dal yalnız 6 olay / 6 hissedir. Bu kullanıcının dizisini
  doğrulamaya veya genellemeye yetmez.
- B04 yeni/uzun düz grupları aynı 0–2,5 günlük ATR mesafe bandındadır ama
  olaylar **eşleştirilmemiştir**; checkpoint'ler örtüşebilir. Yaş temelli
  araştırma proxy'si canlıya yeni bir bekleme kuralı olarak önerilmez.
- Ters native günlük çekirdek, canlı 4s sinyallerin tamamının matematiksel
  tersi olduğuna dair kanıt değildir. Kullanıcının görsel tanımı, çok küçük
  örneklem ve önceden görülmüş veri sınırlamaları sürmektedir. Bunlar bir işlem
  önerisi veya canlı aktivasyon kanıtı değildir.

## Tekrar doğrulama

Depo kökünde bağımlılıklar kurulduktan ve aynı hash'li arşivler mevcutken:

```bash
.venv/bin/python -m research.stabil_support_resistance_verify --output docs/arastirma/stabil_direnc_50_model_testi_2026_11_06
.venv/bin/python -m research.stabil_support_resistance_path_verify --output docs/arastirma/stabil_direnc_50_model_testi_2026_11_06
.venv/bin/python -m research.stabil_resistance_50_verify --output docs/arastirma/stabil_direnc_50_model_testi_2026_11_06
.venv/bin/python -m pytest -q test_stabil_*.py --disable-warnings --maxfail=1
```

Ek sabit-çizgi çalışmasının planı ana sonuçlardan sonra ve ek koşudan önce
hazırlandı; bkz. [ek yol planı](EK_YOL_PLANI.md). Hiçbir görsel, BOS filtresi,
canlı direnç, alarm veya dağıtım değişikliği bu çalışma kapsamında yapılmadı.
