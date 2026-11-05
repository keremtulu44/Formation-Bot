# Stabil dosya envanteri ve kurtarma listesi

**Tarihsel snapshot: 2026-11-01.** Aşağıdaki “bulunamayan” kayıtlar yalnız o günkü
workspace/HEAD için geçerlidir. 2026-11-04'te güncel branch yeniden kontrol
edildi; güncel durum aşağıdaki ek bölümdedir. [Ana rehber](STABIL_REHBERI.md).

## 2026-11-04 güncel checkout yeniden kontrolü

| Yol | Bugünkü durum |
|---|---|
| `domain_engines/stabil/` + `domain_engines/runner.py` | Mevcut; `run_stabil_domain` `as_of_close` ve `isolated` destekli |
| `research/arsiv.py` + `backfill_data/ASTOR_1d.csv.gz`, `ASTOR_1h.csv.gz` | Mevcut; yerel gerçek ASTOR arşivi, 4h `tf_frame` ile türetilir |
| `research/stabil_replay.py`, `research/stabil_bhv48.py` | Mevcut; 100-sembol causal replay builder ve 48-soru aggregate evaluator |
| `test_stabil_domain_and_integration.py`, `test_stabil_momentum_arrow.py` | Mevcut; runtime/parity/integration regression tests |
| `scripts/diagnostics/stabil_api_poc.py`, `test_api_readonly_contract_poc.py` | Mevcut; local-only read-only HTTP PoC; public API değil |
| `docs/arastirma/stabil_100_sonuclar/STABIL_DAVRANIS_48_*` | Mevcut aggregate manifest/JSON/CSV/Markdown; manifest 100 sembol, 107.441 checkpoint, 10.417 first-seen event, 48 soru, 642 satır; exact data cutoff ve source hash yok |
| `docs/arastirma/stabil_live_systematic_results.json` | Mevcut; ayrı 50/53 canlı non-macro systematic çalışma |
| `STABIL_DAVRANIS_100_NATIVE_2026-10-31.tar.gz`, flat `docs/arastirma/STABIL_DAVRANIS_48_YANITLARI.md`, `.json.gz`, `STABIL_DAVRANIS_48_SONUC_OZETI.md` | Bu exact historical paths/archive yok. Aggregate rapor `stabil_100_sonuclar/` altındadır; tam native package hâlâ eksik. |

`test_api_readonly_contract_poc.py` 2026-11-03'te **7 passed** oldu. Bu doğrulama
API kontratındaki arşiv kesiti/look-ahead davranışıyla sınırlı; eski 100 sembollük
paketi, 48 soruluk araştırmanın sonuçlarını veya canlı deploy'u doğrulamaz.

## 2026-11-01 snapshot'ta mevcut ve kalıcı repo dosyaları

| Dosya | Köken / doğrulama |
|---|---|
| [05_stabil.txt](../../domain_engines/05_stabil.txt) | Özgün yükleme, bayt/hash eşitliği doğrulandı |
| [Kaynak notu](../../domain_engines/STABIL_KAYNAK_NOTU.md) | Yeni belge; TXT entegrasyon yerine geçmez |
| [Ana rehber](STABIL_REHBERI.md) | Yeni giriş ve durum sayfası |
| [Replay yöntemleri](STABIL_REPLAY_HATLARI.md) | Mevcut genel hat + önceki Stabil yöntem kaydı |
| [Davranış modeli](STABIL_DAVRANIS_MODELI.md) | Konuşmadan yeniden kayıt; doğrulanmış piyasa kuralı değil |
| [48 soru](STABIL_DAVRANIS_SORULARI.md) | Konuşmadan yeniden kayıt; eski dosyanın bayt-kopyası değil |
| [Çalışma geçmişi](STABIL_CALISMA_GECMISI.md) | Tarihsel sonuçların kanıt sınırıyla kaydı |

Aşağıdaki eski envanterin kapsamı 2026-11-01 snapshot'ıdır. O tarihte “TXT'nin
varlığı beşinci runtime entegrasyonunun mevcut olduğu anlamına gelmez” ve
“başka domainler çalışıyor” denmişti; güncel 2026-11-04 checkout'ta Stabil
runtime ve testleri bulunduğu için bu eski cümleler bugünkü durum olarak
kullanılmamalıdır. Arşivde 177 adet 1H ve 177 adet 1D dosyası bulunduğuna dair
eski kayıt, önceki Stabil'in 100 sembol planını/hashlerini yeniden kurmaz.

## Önceki snapshot'ta raporlanan, o gün bulunamayanlar

Aşağıdakiler **dosya adı sicili**, tıklanabilir teslimat veya çalışma komutu değildir.

| Beklenen yol/öğe | Kaybedilen doğrulama / kullanım |
|---|---|
| `domain_engines/stabil/` | Native paket, adapter/history observer'ları, registry/scan bağlantıları |
| Stabil'e özgü testler, chart/card değişiklikleri | 77 test raporu ve four-TF görsellerin bugünkü yeniden kontrolü |
| `research/stabil_replay.py`, `stabil_kosu.py`, `stabil_sorular.py` | İlk optimize 100 sembol/27 soru hattı |
| `research/stabil_olay_duzelt.py` | Event sequence düzeltimi |
| `research/stabil_davranis.py`, `stabil_davranis_finalize.py` | 48 soru ve kayıtlı native üzerinde son türetim |
| `research/stabil_davranis_paket.py` | Taşınabilir paket ve geri kurma |
| `docs/arastirma/STABIL_100_*` | İlk 27 sorunun rapor/plan/hash/sonuç belgeleri |
| `docs/arastirma/STABIL_DAVRANIS_48_SONUC_OZETI.md` | Önceki okunur nihai özet |
| `docs/arastirma/STABIL_DAVRANIS_48_YANITLARI.md` | 4.074 satırlık tam nihai cevap tabloları |
| `docs/arastirma/STABIL_DAVRANIS_48_YANITLARI.json.gz` | Makine yanıtları; önceki kayıtta 3.538.754 bayt |
| `docs/arastirma/veri/STABIL_DAVRANIS_100_NATIVE_2026-10-31.tar.gz` | Native checkpointler, fiyatlar, soru indeksi, manifest; önceki kayıtta 80.735.612 bayt |
| Önceki paket denetim sidecar'ı | 719 üye hash ve THYAO 4107 geri kurma kaydı |
| `var/stabil_davranis_100_20261031`, `/home/user/stabil-replay-100-20261031` | Önceki native/ham çalışma dizinleri, log/planlar |
| Onaylanan PNG ve `1bf1b5d` commit nesnesi | Önceki görsel/yerel commit; bu checkout nesnelerinde bulunamadı |

2026-11-01 incelemesinde o zamanki workspace HEAD'i
`385c9bd5dd1537d49de2ff2797754d35d01fdb9d` idi; bu oturumdaki mevcut branch
HEAD'i `cb50d2d` tabanındadır. Eski reflog/erişilemeyen nesne bulgusu da yalnız
2026-11-01 snapshot'ına aittir; başka bir bilgisayar/arşivde bulunmadığı anlamına
gelmez.

## Kurtarma — öncelik sırası

1. Yalnız gerçekten eksik olan tarihsel workspace/export veya kaynak dal/commit
   artefaktlarını ara; mevcut runtime, test veya sonuç dosyalarını silme.
2. Önce **tam native paketi + final JSON + manifest + plan/sembol listesi**
   kurtar. Paket üye hashlerini ve veri/kod kökenini doğrula.
3. Güncel runtime/testler mevcut; özgün TXT hash/parity ve prefix nedenselliğini
   bugünkü testlerle yeniden doğrula. Eksik tarihsel observer/replay araçlarını
   yalnız ayrı ihtiyaç olarak kurtar; live feature eklemesi sanma.
4. Tam yanıtlar/paket geri kurma testini motor çağırmadan dene; eksik sonuçları
   native kayıtlarından türet. Ancak native de kayıpsa yeniden koşu gereksinimini bildir.
5. Raporları kaydedilen snapshot/tablolarla karşılaştır; burada tarihsel diye
   işaretlenen sayıları doğrulanmış artefaktlara bağla. Dosya adı benzerliği yetmez.
6. Sonuçları repo boyut sınırlarına/ignore politikasına uygun kalıcı arşivde tut;
   manifest, erişim yeri ve geri kurma talimatını buraya ekle.

## Kapsam koruması

Bu kayıt kurtarma/belgelemedir. Push/deploy, DB değişikliği, alarm filtresi,
canlı araştırma biriktirme, kullanıcı emir yetkisi veya yeni işlem kuralı değildir.

## Bu turdaki belge kontrolleri

2026-11-01'de stdlib tabanlı yerel kontrol çalıştırıldı:

- Yeni belgeler ve mevcut belgelere eklenen satırlardaki **90 yerel bağlantı**:
  hedefler mevcut; kırık bağlantı yok. Deponun tüm eski linkleri denetlenmedi.
- Özgün TXT: 75.710 bayt / 1.637 satır ve kayıtlı SHA256 ile eşleşme.
- Soru taslağı: A01–H06 aralığında 48 benzersiz tablo kimliği; kimliklerin
  mevcut olması eski kod/metin eşlemesini doğrulamaz.
- Arşiv dosyaları: 177 adet 1H + 177 adet 1D; eski plan hash kontrolü değil.
- `git diff --check`: geçti. Bu tur native/entegrasyon testleri çalıştırılmadı;
  önceki 77 test başarısı yeniden doğrulanmış sayılmıyor.
