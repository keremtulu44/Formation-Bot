# Alarm sistemi denetimi — DM ve public (22 Ekim 2026)

> **Kapsam:** `main.py` alarm dalı, `notifier.py` (kart, mühür, cooldown, public
> kuyruk/bülten), `notification_delivery.py` (kalıcı outbox), `notification_context.py`
> (kart blokları). İnceleme anı: `37bc976` (dal `arena/20902601-formation-bot`).
> **Yöntem:** kod okuma + örnek kayıtlarla metin üretimi + 1597 testlik tam paket.
> Bu belge bulguları ve **yapılan düzeltmeleri** kaydeder; açık maddeler §6'da.

---

## 1. Akış — kim, hangi kapıdan geçiyor

### DM (kişisel sohbet)

```
motor → state politikası → outbox tekrarı → mühür → cooldown (4 sa)
      → günlük 120 / saatlik 20 kap → içerik kapısı (bağlam aynıysa kısa kart)
      → kalıcı outbox (JSON + Supabase) → metin → görseller (4 kare)
```

Kapanış/pencere kapıları (main tarafı): `son_bar_kapandi`, kapanış teyidi
(`_closed_formation_event_confirmed`), geçersizleşme için "teyit teslim edildi mi"
(`_invalidation_confirmation_delivered`). Kritik stateler saatlik kaptan muaf.

### Public (grup)

```
motor → state ∩ PUBLIC_STATES → kalite eşiği (TF bazlı) → public tekrar mührü
      → kuyruk (azami 12) → bülten (3300 kr) → mesaj başına 2,0 sn tempo
      → kuyruktan düş → metnin ardından 1 kare + üst TF karesi
```

Bütçe DM'den ayrı: **6 mesaj/saat, 25 mesaj/gün**. DM kapalıyken public çalışır;
DM'in cooldown/kap engeli public'i bağlamaz.

---

## 2. Bu turda kapatılan boşluklar

| # | Bulgu | Etki | Düzeltme |
|---|---|---|---|
| 1 | Alarm TF'sinde MS satırı yoksa kartta `◈ … yapı` hiç basılmıyordu | Public bültende yapı bloğu boş; kırılımın yönü okunamıyor | `_kart_yapi_ozet` sırası: alarm TF → public görselindeki üst TF (1h/2h→4h, 4h→1g) → kalan üst TF'ler. Satır kendi etiketiyle yazılır (`◈ 4s yapı …`) |
| 2 | DM mührü `tekrar` dediğinde `before_send` hiç çalışmıyordu | Public kuyruğu dolmuyor; gruba hiç gitmemiş olay (ağ hatası, bütçe, restart) bir daha denenmiyordu | `_public_kurtar`: yalnız **public'te kaydı olmayan** olay için bağlam hazırlanır; DM'e ikinci kez gitmez |
| 3 | DM geçersizleşme kapısı ayrı `elif` bloğuydu | Kapı kapandığında bağlam + public kuyruğu tamamen atlanıyor, grupta teyit "geçerli" kalıyordu | Kapı ana dala taşındı: yalnız DM push'unu atlar, bağlam hazırlanır, kararı public kendi kapısı verir |
| 4 | Geçersizleşme kalite eşiğine takılıyordu | Teyit eşiğini geçmiş olayın iptali, kalite sonradan düştü diye bastırılıyordu → sinyal sonsuza kadar geçerli | `KIRILIM_GECERSIZLESTI` kalite kapısından muaf (DM + public) |
| 5 | Kuyrukta bekleyen teyit + geçersizleşme | Teyit sonradan gidiyor, geri alma kalıcı kayboluyordu | İkisi birlikte düşer (`Public: teyit henüz gönderilmemişti …`) |
| 6 | MS motoru arızası kartta `⚠️` satırı olarak basılıyordu | Kart karar belgesi; altyapı arızası alarm metnini kirletiyordu (karar D) | Kart basmaz; `/durum`a `⚠️ MS (piyasa yapısı) motoru: N hissede hata · son: … · alarm kartı etkilenmez` (hisse bazlı sayaç) |

Test karşılığı: `test_public_grup.py` §9-12 (üst TF yedeği, mühür sonrası public,
DM kapısı yapısal güvencesi, kalite muafiyeti, bekleyen teyit),
`test_notification_context.py` (3 test), `test_kart_metin.py` (MS arızası kartı
kirletmez + sayaç).

---

## 3. DM tarafı — denetim sonucu

**Doğru çalışan (değişmedi):**

* Mühür state + formation kimliği bazında; TTL bar süresine ölçekli
  (`_muhur_ttl_saat`), kimlikli olayda 7 gün. Slot flicker'ı mührü silmez.
* Cooldown anahtarı `(hisse, formasyon, TF, state)` — geçersizleşmenin kendi
  cooldown'u var, teyidin cooldown'una takılmaz.
* Teslim: metin ve görsel tek FIFO'da; **önce tüm kareler hazırlanır**, sonra
  metin, sonra albüm. Hata → 30 sn sonra yeniden, olay kaybolmaz.
* Saatlik kap kritik stateleri (teyit/retest/geçersizleşme) engellemez.
* İçerik kapısı yalnız KISALTIR (`▪ yapı/bölge/hacim değişmedi`), mesajı
  düşürmez; mühür tek sahip kalır.
* Kuyruk: engellenen olay `_acil_kuyruk`ta bekler, tarama sonunda azami 5
  tanesi denenir; süre aşımı/taşma sayaçları `/durum`da.

**Düzeltilen:** §2/3, §2/4, §2/6.

**Not (tasarım gereği):** DM geçersizleşmesi yalnız teyit **teslim edilmişse**
gider; aksi hâlde 18:45 özetine "sessiz geçersizleşme" olarak sayılır. Bu kural
korundu — ama artık bu kapı public'i durdurmuyor.

---

## 4. Public tarafı — denetim sonucu

**Doğru çalışan (değişmedi):**

* DM'den bağımsız hedef, bütçe ve sayaçlar; DM kapalıyken de yayın yapar.
* Tekrar mührü `hisse|TF|state|formation_id`, 7 gün; MTF birleştirme 4 saat
  (`related`: farklı TF + aynı yön + aynı formasyon ailesi).
* Bülten: olay **ekleyerek** dolar; sığmayan olay sonraki bültene kalır
  (sessiz kesme yok). Başlıktaki sayı metne giren olayı söyler.
* Yasal uyarı bültede **tek kez**; kartın kendi uyarısı düşürülür.
* Kare: 1 + üst TF, metnin ardından, kare başına tempo, dosya her durumda silinir.
* Kalıcı durum: kuyruk + mühürler + günlük/saatlik sayaçlar restart'ta geri yüklenir.

**Düzeltilen:** §2/1, /2, /3, /4, /5.

**Bilinen sınır:** kare dosyaları diske yazılmadan gönderildiği için restart
sonrası kuyrukta kalan olay **metinle** gider, karesi olmadan. Sayaç tutulmuyor;
istenirse kareler `_public_grafik` yerine kuyruk kaydına yol olarak yazılabilir.

---

## 5. Ölçümler (örnek kayıtlarla)

| Çıktı | Satır | Karakter | En geniş satır |
|---|---|---|---|
| DM teyitli kart | 25 (19 dolu) | 524 | 253,5 px |
| Public teyitli kart | 24 (18 dolu) | 495 | 253,5 px |
| Public geçersizleşme kartı | 21 (15 dolu) | 401 | 260,5 px |
| 1 olaylı public bülten (üst TF yedeğiyle) | 24 (18 dolu) | 453 | 253,5 px |
| 12 olaylık bülten | 2 mesaj (6+6) | 2844 / mesaj | 253,5 px |

Telefon bütçesi `_kart_esik_px() = 283`; hiçbir satır aşmıyor. Public bültende
`◇` sayısı olay başına **2** (DM 3). 12 olaylık bültede yasal uyarı 2 mesajda
2 kez (her mesajda bir kez) — kural "bülten başına bir kez".

---

## 6. Açık maddeler (bilinçli olarak yapılmadı / sırada)

| # | Madde | Neden duruyor |
|---|---|---|
| 1 | `/tara HISSE` çıktısında **tam 1-2-3 beklenti** bloğu | Beklenti satırları domain çıktısına dayanıyor; manuel tarama `send_alerts=False` ile koşuyor, yani bağlam hiç üretilmiyor. Bağlanması için tek hisselik taramada domain motorlarının bir kez koşup kayda yazılması gerekir (motor bedeli + yeni test seti) |
| 2 | `/durum` metninin tamamen sadeleştirilmesi | Operatör paneli; `cooldown`, `digest`, `eşik altı` gibi terimler teşhis için kısa. Kart/`/olcum` sade dil kuralına tabi, `/durum` değil. MS satırı bu turda eklendi |
| 3 | `/formasyonlar` listesi | Hâlâ `kalite 81/100`, `alarm eşiği 80 altında` gibi teknik etiketler taşıyor; kart 7 bloğa geçtiği için liste ile kart arasında dil farkı var |
| 4 | Public karelerinin restart sonrası kaybı | Metin gidiyor, görsel gitmiyor; sessiz (sayaç yok) |
| 5 | `format_public_tekil` boş kart dönerse | Kuyruk başındaki bozuk kayıt turu kilitleyebilir (kayıt kuyrukta kalır, sonraki tur denenir); pratikte `stock_name` zorunlu olduğu için görülmedi. 22 Ekim akşamı bülten kaldırıldı → tek-olay biçimleyici |

---

## 7. Nasıl doğrulanır

```bash
# kart metinleri (DM/public/geçersizleşme) + ölçüm
.venv/bin/python -m pytest -q test_kart_metin.py test_public_grup.py \
    test_notification_context.py

# tüm paket (22 Ekim: 1597 passed, 43 skipped)
.venv/bin/python -m pytest -q

# yapılandırma kapıları
.venv/bin/python deploy_check.py
```

Kart ölçümü için hazır betik: `scripts/diagnostics/` altındaki ölçüm araçları
(`telegram_measure.genislik`) veya `gun_simulasyonu.py`.
