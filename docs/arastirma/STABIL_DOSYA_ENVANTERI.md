# Stabil dosya envanteri ve kurtarma listesi

**2026-11-01 gerçek dosya kontrolü.** [Ana rehber](STABIL_REHBERI.md).

## Şimdi mevcut ve kalıcı repo dosyaları

| Dosya | Köken / doğrulama |
|---|---|
| [05_stabil.txt](../../domain_engines/05_stabil.txt) | Özgün yükleme, bayt/hash eşitliği doğrulandı |
| [Kaynak notu](../../domain_engines/STABIL_KAYNAK_NOTU.md) | Yeni belge; TXT entegrasyon yerine geçmez |
| [Ana rehber](STABIL_REHBERI.md) | Yeni giriş ve durum sayfası |
| [Replay yöntemleri](STABIL_REPLAY_HATLARI.md) | Mevcut genel hat + önceki Stabil yöntem kaydı |
| [Davranış modeli](STABIL_DAVRANIS_MODELI.md) | Konuşmadan yeniden kayıt; doğrulanmış piyasa kuralı değil |
| [48 soru](STABIL_DAVRANIS_SORULARI.md) | Konuşmadan yeniden kayıt; eski dosyanın bayt-kopyası değil |
| [Çalışma geçmişi](STABIL_CALISMA_GECMISI.md) | Tarihsel sonuçların kanıt sınırıyla kaydı |

Şu an çalışan diğer domainler MS, hacim/katılım, FVG ve OB'dir. TXT'nin
varlığı beşinci runtime entegrasyonunun mevcut olduğu anlamına gelmez.
Arşivde 177 adet 1H ve 177 adet 1D dosyası var; bu sayı önceki Stabil'in
100 sembol planını ve kullandığı veri hashlerini yeniden kurmaz.

## Önceki oturumda raporlanan, bugün bulunamayanlar

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

Git incelemesinde bu checkout'un HEAD'i `385c9bd5dd1537d49de2ff2797754d35d01fdb9d`
idi; reflog/erişilemeyen nesnelerde eski Stabil çalışması bulunmadı. Bu,
başka bir bilgisayar veya arşivde olmadığı anlamına gelmez.

## Kurtarma — öncelik sırası

1. Önceki workspace/export veya kaynak dal/commit arşivini temin et; mevcut
   dosyaları silme, sonuç üretmek için hemen motoru tekrar çalıştırma.
2. Önce **tam native paketi + final JSON + manifest + plan/sembol listesi**
   kurtar. Paket üye hashlerini ve veri/kod kökenini doğrula.
3. Runtime ve replay kaynaklarını/testlerini geri al; özgün TXT ile matematik
   eşitliğini ve prefix nedenselliğini test et. Sadece observer eklerine izin ver.
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
