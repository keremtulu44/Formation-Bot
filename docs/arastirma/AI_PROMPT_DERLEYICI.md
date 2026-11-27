# Yerel grafik → AI prompt derleyicisi (deneme sürümü)

Bu araç kullanıcıyla kararlaştırılan yorumlama çerçevesine göre bağımsız,
seçici bir prompt üretir. Sadece yerel veri okur; AI servisine, Telegram'a,
alarm akışına veya canlı motor state'ine bağlı değildir. Gerçek alarm kaydı
varmış gibi davranmaz. **İlk sürüm yalnızca BIST hisseleri içindir**; XAUUSD,
diğer makrolar ve endeksler bu seans modeli doğrulanmadan kabul edilmez.

## Kullanım

Repo bağımlılıklarını kurulu Python ortamında:

```bash
python scripts/diagnostics/ai_prompt_sample.py BIMAS \
  --as-of 2026-09-25T18:30:00+03:00 \
  --main-tf 4h --research-mode retrospective \
  --output docs/arastirma/ai_prompt_ornekleri/BIMAS_yeni.txt
```

`--output` verilmezse prompt stdout'a yazılır. Mevcut bir dosyanın üzerine
**yazılmaz**; yeniden denemek için farklı çıktı adı verin. Yalnız açıkça
belirtilen yerel JSON kullanılır, sağlayıcıya/seed/uzak servise başvurulmaz.
`--data-dir` başka bir yerel JSON dizini seçer. `--as-of` zorunlu ve zaman
dilimli olmalıdır. İzin verilen ana TF: `1h`, `2h`, `4h`, `1d`. CLI varsayılanı
`--format compact`; önceki ayrıntılı grafik sözleşmesi için `--format full`.
API: `render_compact_prompt(packet)` (kompakt) veya `render_prompt(packet)`
(ayrıntılı). Bu bir yerel tanı aracıdır, henüz botun AI/Telegram akışına bağlı
değildir.

## Kullanıcının ana referansı

Kullanıcının paylaştığı özgün yorum yöntemi ve BIMAS örneği
`ai_prompt/kullanici_ana_referans.txt` içinde, satır sonu boşlukları dışında
korunur. Bu metin yorumlama sistematiğinin ana referansıdır. Günlük üretimde
`ai_prompt/talimat.txt` (ayrıntılı) veya `ai_prompt/talimat_kisa.txt`
(kompakt) kullanılır; karşı kanıt, koşullu görüş, temas ve
bölge ayrımları, belirsizlikler, araştırma kapsamı ve üç başlık korunmalıdır.

Referansın grafik ve araştırma bölümleri **tarihsel örnektir**, sabit canlı
veri veya geçmişte gerçekleşmiş alarm değildir. Kullanıcının son kararıyla,
örnekteki grafikte görünmeyen iç olaylar güncel grafik verisine geri eklenmez;
replay ve araştırma ayrı etiketlenir ve araştırma zamanlaması korunur.

Üç önceki v8 örnek prompt (referans kaydı sonrası talimat güncellendiği için
güncel çıktı ile karakter karakter aynı değildir; AI yorumu değildir):

- `ai_prompt_ornekleri/BIMAS_2026-09-25_v8.txt`
- `ai_prompt_ornekleri/ALARK_2026-09-25_v8.txt`
- `ai_prompt_ornekleri/PETKM_2026-09-25_v8.txt`

Bunlar 25 Eylül 2026 yerel cache kesitleridir, güncel fiyat veya gerçek
alarm değildir. `retrospective` modundadır; sonradan üretilen araştırmalar
gelecek bilgisi olduğu açıkça etiketlenerek geriye dönük değerlendirme için
eklenir. AI cevabını bu araç üretmez.

### Otomatik kompakt üretim — 4.000 hedef / 4.500 üst sınır

`render_compact_prompt` hedefi 4.000 ve değiştirilemeyen azami sınırı 4.500'dür.
Unicode kod noktası ve UTF-16 kod birimi sayısından büyük olanı kullanır
(satır sonu dahil); bu nedenle emoji kullanan UTF-16 istemcilerinde de 4.500
birimi aşmaz. UTF-8 bayt sayısı farklı olabilir. Normal ayrıntılı prompt
veya JSON packet değişmez. CLI varsayılanı kompakt biçimdir; henüz alarm veya
AI hizmetine bağlanmış değildir. Sonucu güvenle 4.500'e indiremezse çıktı
üretmek yerine açıklayıcı hata verir, önemli verileri sessizce kesmez.

- Her TF'de grafiğin gösterdiği **tüm OB/FVG bölgeleri ve seviyeleri** korunur.
  Ham dış yapı olaylarının iki son BOS'u ve yön başına son BOS ile son CHoCH'u
  kronolojik korunur. Daha eski grafikteki olayların kaçının özet dışında kaldığı
  TF bölümünde belirtilir; bilinmeyen tür/yön/zaman sessizce atlanmaz. Bu bir
  önem sezgisidir, atlanan olayların önemsiz olduğu kanıtı değildir.
- Ana TF'deki tüm replay bölgeleri, temas grup sayısı, kullanılabilirlik zamanı,
  kalan bant ve belirsizlikler korunur. Bütçe gerekiyorsa fiyat kenarına en yakın
  bölgelere odaklanılır; her aile/yönün en yakın aktif bölgesinin ayrıntısı
  korunur. Başka bölgelerin kapanış ayrıntısı gösterilmezse belirtilir. Sonraki
  aşamada eski temas grubunun ayrıntısı çıkarılabilir; bu da belirtilir. FVG
  doğum ATR oranı günlük FVG araştırmasına uygulanabildiğinde gösterilir.
- OB/FVG ilgili genel araştırma bulguları ve strict/retrospective zamanlama
  sınırları korunur. Gerektiğinde Stabil/MS araştırması ayrıntısı açıkça özet
  dışında bırakılır. Kısa bulgu metni kaynak manifestin doğrulanmış içeriğiyle
  eşleşmiyorsa tam metne düşer; sessiz eski istatistik kullanmaz.
- Hedef aşılsa bile mevcut ayrıntı 4.500'e sığıyorsa sırf 4.000'e yaklaşmak
  için gereksiz veri azaltılmaz. Aşarsa aşamalı seçim yapılır. Son çare olarak
  her TF'de her hacim yönünün en yeni rozeti korunur; daha eski rozetler
  çıkarılırsa sayısı bildirilir. Yıl geçişleri açık tam yılla gösterilir.

28 yerel sembolün 25 Eylül 2026 4s/retrospective denetimi: 112 TF, 227 dış
olay (158 BOS, 69 CHoCH), 3+ BOS olan 14 TF. 21 eski olay (18 BOS, 3 CHoCH)
özetlenmedi; 241/241 grafik bölgesi ve 70/70 ana TF replay bölgesi korundu.
383 hacim rozetinden 8'i, sayısı açıklanarak özet dışı bırakıldı. 28/28 çıktı
3.233–4.500 karakter, 7'si ≤4.000, 21'i 4.001–4.500; 0 hata. Dört sembollük 1h, 2h ve 1d/strict seçkileri de geçti; tüm TF ve tüm tarihler
genellenmiş değildir. 28 sembolde ortalama 4.110, medyan 4.230 karakterdir.

Doğrudan üretici çıktıları: `BIMAS_2026-09-25_kompakt_v2.txt` (4.439),
`ALARK_2026-09-25_kompakt_v2.txt` (4.290), `TAVHL_2026-09-25_kompakt_v2.txt`
(4.500); bunlar tarihsel deneme, AI cevabı veya gerçek alarm değildir.

### Sade cevap ve 4.000 karakter denemeleri (elle)

`talimat.txt`, OB/CHoCH/BOS/FVG gibi yerleşik terimleri yasaklamadan açık ve
kısa cümleler ister. İç jargon yerine doğal anlatım; temas ve sonraki kapanışı
ayırma, son kapanışın orijinal bölgeye göre yerini gözetme, kısa mum hacmini
teyit saymama ve verilmeyen formasyon yönünü varsaymama kuralları bulunur.

Son elle hazırlanmış örnekler `ai_prompt_ornekleri/BIMAS_2026-09-25_denge_v3.txt`
(3.999 karakter) ve `ALARK_2026-09-25_denge_v3.txt` (3.984 karakter).
Yalnız bu kesitlere özel tarihsel, geriye dönük test metinleridir; gerçek alarm
veya otomatik üretim değildir. v2 dosyaları önceki talimatla arşivlenmiştir.
Dört TF'de gösterilen yapı olayları, OB sınırları ve hacim rozetleri korunur.
Tek sayı olarak grafikte etiketlenmeyen formasyon çizgisi fiyatları çıkarılmış;
kalite/daralma grafikteki gibi yuvarlanmıştır. Grafik bölgesi kaynak mumu ve
OB doğum ATR oranı bu taslaklarda yoktur; ham packet'ta korunur. Ana TF replay
sürdürülür; **ALARK'ın daha eski 99,15–101,40 pozitif OB'sinin temas kapanışları
4.000 sınırı için çıkarılmış ve örnekte açıkça belirtilmiştir**; diğer iki
ALARK bölgesinin ve BIMAS bölgelerinin seçili kapanışları korunur. Bu bilinçli
örnek tercihi başka kesitler için otomatik önem sıralaması değildir. Sadece OB
araştırması yer alır; kesit sonrası olduğu gösterilir.

Bu eski elle hazırlanmış örnekler otomatik kompakt üreticinin sözleşmesi
veya her sembole uygunluk garantisi değildir. Yeni model yanıtı denenmemiştir.

## Sabit blok ve tarih güvenliği

`ai_prompt/talimat.txt` yorumlama çerçevesidir; `ai_prompt/arastirma.json`
çalışmaların kaynak, tarih, kapsam ve bulgularını saklar. Prompt yalnız ana TF
ve orada görünür kanıta uygun araştırmaları ayrı başlıkta taşır: OB varsa OB;
günlük FVG varsa günlük FVG; 4s grafiğinde uygun görünür destek varsa Stabil;
4s dış BOS varsa MS. Kapsam dışı araştırma ve tekrar eden açıklamalar çıkarılır.
Ayrıntılı prompt çalışma kimliği, kompakt prompt tür/rapor/veri sonu ile kaynak
belirtir; tam dosya yolu, rapor ve veri
sonu tarihleri `packet["research"]` ve `arastirma.json` içinde korunur.
Bulgular kişiye özel olasılık değildir.

- `strict` (varsayılan): rapor ve veri-sonu kesitten önceki gün olarak
  bilinmiyorsa, ilgili çalışmanın bulgusu verilmez; belirsizlik açıkça yazılır.
- `retrospective`: yalnız seçilen ilgili çalışmaların bulguları da verilir;
  kesit sonrası/belirsiz zamanlama etiketlenir. Canlı tarihsel simülasyonda
  o tarihte biliniyormuş gibi kullanılmamalıdır.

Stabil araştırmasının veri-sonu, hacim çalışmasının yayın zamanı bilinmiyor.
Nicel Stabil bulgusu bu nedenle strict modda çıkmaz; hacim araştırması ana
TF seçimine girmez. Gerekli genel güvenlik ilkeleri talimatta korunur.

## Veri ve seçim sözleşmesi

- Önce zaman dilimli 1 saatlik mumlar `as_of` itibarıyla gerçekten kapanmış
  olanlarla sınırlanır; **sonra** 2s/4s/günlük türetilir. Varsa bağımsız
  günlük JSON ayrıca kapanışa göre kesilir. Pencerenin ilk türetilmiş kovası
  eksik olabilir. BIST son seans kovaları kısa olabilir.
- Zaman sırası/duplikasyon ve OHLCV/explicit kapanış bayrakları kontrol edilir;
  bozuk veya belirsiz mum sessizce kaldırılıp sağlıklı gösterilmez.
  Saatlik süreklilik ve beklenen kapanış gecikmesi belirtilir. Önbellekteki
  gerçek sağlayıcı bilinmez. Günlük seri bağımsız veya türetilmiş diye etiketlenir.
- Formasyon, MS, hacim, OB, FVG ve Stabil izole hesaplanır. Prompt yapı
  olaylarını motorun ham geçmişinden değil, grafiğin EXTERNAL/teyitli/geçerli
  BOS/CHoCH seçimi, zaman penceresi ve renderer ile paylaşılan son fiyat
  kadrajından alır. İç yapı, sweep, geçiş başarısızlığı ve kadraj dışı olaylar
  prompta girmez. Formasyon state'i `/grafik` yolu gibi snapshot'a eklenir.
  Formasyon kalitesi/daralması grafiğin tam sayı biçimiyle yazılır; sayıyla
  etiketlenmeyen kesin çizgi fiyatları grafik verisi olarak sunulmaz. Ana TF
  replay'inde kapanışın orijinal banda göre konumu, kapanış ve sınırlar
  biliniyorsa hesaplanır; kalan bantla karıştırılmaz. Görünür dış PH/PL/WH/WL
  seviyeleri ve bölgeler korunur. Hacimde ham son
  RVOL değeri değil, renderer'ın gerçekten çizdiği rozetler ve kaynakları
  verilir; yerel hesap motor sonucu olarak sunulmaz. Rozetlerin zamanları
  ilgili mum açılışıdır, rozet artış/kuruması fiyat yönü değildir.
  1s/2s Stabil çizgileri ve `GRAFIK_SADE` altında gizlenen katmanlar atlanır.
  Direnç katmanı ayrıca yalnız bağımsız native günlük ve saatlik kaynaktan,
  TF kapanışına kadar nedensel kontrolle hesaplanır; türetilmiş günlük veri
  native veri yerine kullanılmaz. Eksik kaynak uyarısı korunur.
  Grafik seçimi `GRAFIK_GORUNUM` ve `GRAFIK_ODAK_MESAFE_ATR` ayarlarına uyar.
  Araç her TF için planlanan normal görünümü geçici bir PNG olarak çizer,
  çizilen hacim rozetlerini meta'dan okur ve PNG'yi siler. Çizim/fallback
  başarısızlığı katmanları varmış gibi göstermez; başarısız katmanlar uyarıyla
  ayrılır. Bu işlem gerçek gönderilen görseli doğrulamaz: sonraki zaman,
  veri kaynağı veya farklı çizim seçenekleri görüntüyü değiştirebilir.
- Ham `packet` tanılama amacıyla daha geniş motor verisini tutabilir; kullanıcı
  promptu `render_prompt` veya `render_compact_prompt` çıktısıdır. Replay ve genel araştırma, grafik
  katmanları değil, açıkça ayrı etiketlenmiş türetilmiş bağlamlardır.
- Grafiğin **gösterdiği tüm** OB/FVG bölgeleri kullanılır; derleyici eskisi
  gibi ilk üçte kesmez. Grafik kendi uzaklık/aktiflik/kota filtrelerini
  uyguladığı için bu yine tüm motor kayıtları değildir. Replay yalnız aynı
  kaynak mumu, yön ve orijinal sınırlara uyan aktif kaydı eşler; aday FVG
  terfi etmiş bölge gibi sayılmaz. Eşleşmeme/hata **sıfır temas değildir**.
- OB teması orijinal sınırlara OHLC örtüşmesidir. FVG teması kendi native
  kuralıdır. Birbirini izleyen temas mumları tek epizottur; sayılar yalnız
  mevcut veri penceresi/kullanılabilir olma sonrasını kapsar. Ayrıntılı
  çıktı son iki epizodun en fazla son üç temas kapanışı ve varsa sonraki
  kapanmış mumu gösterir; kompakt çıktıda bütçe gerektiriyorsa yukarıdaki açık
  önceliklendirme uygulanır. Promptta yalnız ana TF replay özeti yazılır;
  diğer TF'lerin grafik durumları ayrıca korunur.
- Bölge yüksekliği/ATR, araştırma ile aynı yaklaşımda: orijinal bölge
  yüksekliği / kaynak-doğum mumundaki Wilder ATR(14). Hesaplanamazsa
  bilinmiyor denir. Çalışmanın bulgusu kapsam dışı TF'lere taşınamaz.
- FVG 1s desteklenmez; deneysel 2s varsayılan olarak çalıştırılmaz. İkisi
  de “FVG yok” değildir. Grafik dışındaki aktif/aday sayıları prompta verilmez;
  hata, atlama veya yetersiz kalite ise bilinmezlik olarak korunur.
- Stabil için yalnız ana TF'de aynı günlük destek görünür ve replay kimliğiyle
  eşleşiyorsa nedensel günlük temas sırası ve son iki temas günü eklenir.
  Kural: destek günlük low–high içindedir ve kapanış altında değildir; tekrar
  saymak için temas dışı bir günde kapanış en az 0,35 günlük ATR uzaklaşır.
  İlk destek kimliğinin pencere öncesi veya tekrar ortaya çıkan kimliğin
  geçmişi bilinmez; eksik ATR sıra sayısını belirsiz kılar. Destek aynı gün
  kapanışında ilk kez bilinir olmuşsa gün içi temas geçmişe dönük gözlemdir,
  önceden bilinen destek testi değildir. **Bu 4s temas replay'i değildir**;
  araştırmanın ileri getirisi, ret veya tepki sonucu hesaplanmaz.
- Ayrıntılı `render_prompt` yüksek teknik sınır kullanır; kompakt üretim 4.000
  hedef, 4.500 kesin sınır ve açık özetleme sözleşmesi kullanır. Örnekler gerçek
  alarm değildir; yeni talimatla AI cevabı test edilmedi.

## Testler

```bash
python -m pytest -q test_ai_prompt_compact.py test_ai_prompt_builder.py test_alarm_context_packet.py test_directional_zone_replay.py test_domain_engines.py test_domain_incremental_parity.py test_stabil_support_resistance_compare.py
python scripts/diagnostics/ai_prompt_compact_audit.py --as-of 2026-09-25T18:30:00+03:00
# backfill_data günlük arşivi varsa, nedensel sıra karşılaştırması:
python scripts/diagnostics/ai_prompt_stabil_parity.py --as-of 2026-09-25T18:30:00+03:00
```

Sentetik ve yerel testler dahil: dört TF, gerçek BİM temas kapanışları ve aday
yönü, FVG tekil kayıtları, ATR oranı, kesim sonrası saatlik/günlük veri
mutasyonuna dayanıklılık, kapanmamış bar, hatalı/tekrarlı mum, veri gecikmesi,
ağ kullanılmaması, araştırma zamanlaması, FVG adayları, küçük fiyat hassasiyeti,
araştırma kova sınırları ve eşleşmeyen replay. 28 yerel sembol ve 112 TF
üzerindeki kontrol ile 13.020 günlük kesitte Stabil sıra karşılaştırması
özeti `AI_PROMPT_KALITE_KONTROL_2026-11-22.md` dosyasındadır.

Bu çalışma otomatik alarm bağlama, wrapper/Gemini, model yanıtı doğrulama,
kuyruk, yeniden deneme veya Telegram gönderimi içermemektedir.

## 60 kapanmış mum: genel geçmiş denemesi (2026-11-22)

Kompakt render artık varsayılan olarak her TF'nin **kendi kapanmış mumlarını**
sayar: son mum yaş 0, 60 mumluk pencere 0–59, yaş 60 ve üstü `[E]` eski
bağlamdır. Takvim günü, diğer TF'nin mum sayısı veya henüz kapanmamış mum
kullanılmaz. 60 ve aşağıdaki iki kayıt eşikleri finansal doğrulanmış kurallar
değil, bu yerel ölçüm için başlangıç sezgisidir. CLI'da `--history-bars 80`
gibi değiştirilebilir; API'de `history_bars=None` eski, penceresiz kompakt
seçimi kullanır. `--format full` önceki ayrıntılı biçimdir. Seçim yalnız
prompttadır; packet, çizim, motor geçmişi ve alarmlar budanmaz.

- Dış yapı: Önce eski genel kompakt seçimi (son iki BOS, yön başına son
  BOS/CHoCH) yapılır. Son 60 mumda en az iki farklı tür/yön bileşimi varsa,
  aynı tür ve yönde yakın örneği bulunan eski BOS bu seçimin dışında kalabilir;
  CHoCH'lar ve yakında eşdeğeri olmayan karşı yön tutulur. Yaşı, türü, yönü
  veya zamanı belirsiz olanlar pencere kuralıyla atılmaz. Bu pencere kuralı
  tek başına geçmişi sıfırlamaz; önceki kompakt seçimin de elediği kayıt sayısı
  bölümde açıkça yazılır. Dolayısıyla yakın veri azsa tüm olaylar değil, eski
  kompaktın seçtiği karşı bağlam korunur.
- Hacim: En az iki yakın grafik rozeti varsa yaşlı ayrıntı azaltılabilir;
  en son artış ve kuruma, belirsiz yaş/yön korunur. Yakın kayıt azsa pencere
  gerekçesiyle çıkarılmaz. 4.500 bütçesi zorlanınca önceki kademeli hacim
  seçimi yakın veriyi de azaltabilir, sayı açıkça bildirilir.
- Replay: Bölge başına mevcut toplam temas sayısı, son iki grubun en çok üçer
  kapanışı ve sonraki kapanış asıl sınırdır; son iki grup gösterimi açıkça
  yazılır. Aynı bölgenin iki yakın grubu varsa daha eski ayrıntısı çıkarılabilir;
  farklı bölgedeki temas eşdeğer sayılmaz. Sayı tüm mevcut/kullanılabilir
  replay penceresine aittir. Yaşsız ayrıntı pencere nedeniyle çıkarılmaz.
  Son iki grup depolandığından mevcut veri kümesinde ek pencere çıkarımı sıfırdır;
  önceki gruplar zaten bu sınır dışındadır. Bütçe kademeleri farklı bölgelerin
  veya daha önceki ayrıntıların gösterimini ayrıca azaltabilir ve bunu belirtir.
- Fiyatlar, seviyeler, tüm grafikte seçilmiş aktif/geçmiş bölgeler, formasyon,
  Stabil mevcut durumu ve hata/eksiklikler sırf yaşlı diye atılmaz. Stabil'in
  günlük temas sırası kendi sınırlı geçmişi ve araştırma zamanlamasıyla kalır.
  Araştırma rapor tarihiyle piyasa bar yaşı karıştırılmaz.

Ölçüm: `ai_prompt_history_audit.py --as-of 2026-09-25T18:30:00+03:00`
28 yerel sembol/112 TF için olay, rozet ve replay yaşını gerçek frame endeksiyle
bağımsız eşleştirdi: sıfır hata. Önceki kompaktın seçilmiş olaylarında
1h medyan/maks 72/177, 2h 61/172, 4h 40/95, 1d 7/22 bardır. Hacim rozetlerinde
sırasıyla 56,5/178, 15/50, 37/107 ve 10/32 bardır. Günlük frame sadece 40
mumdur: bu sonuç daha uzun günlük geçmiş için genellenemez.

Aynı kesitte 60 barlı yeni kompakt denetimi: 28/28 sembol, 112 TF, 0 hata;
3.188–4.478 Unicode karakter, 8'i ≤4.000, 20'si 4.001–4.500. 227 grafik
olayından 25'i açıkça özet dışı, 69 eski seçili olay korunur; 383 rozetten
86'sı açıkça özet dışı (pencere **ve** bütçe seçimleri birlikte), 241 grafik
bölgesi ve 70 ana TF replay bölgesi korunur. Bu sayıları yalnız pencerenin
nedensel etkisi olarak yorumlamayın. 1h/2h/1d ana TF için BIMAS, ALARK, TAVHL,
THYAO strict denetimleri sırasıyla 3.453–3.829, 3.572–3.837 ve 3.679–4.059
karakter, her birinde 0 hata. Test edilen kesitler dışındaki promptlar üst
sınıra sığmayabilir; o durumda hata verilir. İlgili testlerde 177 geçti; ek
sınır/yön/4 TF testleri de `test_ai_prompt_compact.py` içindedir.

Güncel, geçmişe dönük test örnekleri (araştırmalar kesit sonrası olarak
etiketlidir; gerçek alarm veya AI değerlendirmesi değildir):
`ai_prompt_ornekleri/BIMAS_2026-09-25_kompakt_v3.txt` (4.402),
`ALARK_2026-09-25_kompakt_v3.txt` (4.241),
`TAVHL_2026-09-25_kompakt_v3.txt` (4.478). Canlıya bağlanmadı veya deploy edilmedi.

## Okunabilir cevap ve 8 turluk güncel denetim

Kompakt talimat geleneksel formasyon eğilimini diğer kanıtlarla yorumlamaya
izin verir; henüz gerçekleşmemiş kırılımı kesin saymaz. Üç sade başlık istenir:
`🧭 Mevcut durum`, `🔎 Bağlam`, `🕯️ Replay notu`. Bu yalnızca modele verilen
istektir; modelin talimata uyduğu veya yorumunun doğru olduğu garanti edilmez.

`format_ai_commentary(text)` isteğe bağlı yerel yardımcıdır. Ayrı satırlarda
üç tanınan başlığı sırasıyla ve bölümleri dolu olup olmadığını doğrular, yalnız
başlıklarını sabit emojili düz biçime getirir; bölüm metnini yeniden yazmaz.
Eksik/tekrarlı/sırası bozuk başlık veya başlık öncesi metinde hata verir. Bölüm
içindeki Markdown korunur ve içerik/fiyat/iddiaların doğruluğu denetlenmez.
Henüz AI çağrısına, Telegram'a ya da alarmlara bağlanmamıştır; gerçek mesajların
sabit biçimde teslim edildiği iddia edilemez. Full/ayrıntılı biçimdeki eski
talimat ve eski el örnekleri tarihsel sözleşme olarak korunur.

Son talimat ve UTF-16 sınırıyla BIMAS, ALARK, TAVHL, THYAO üzerinden sekiz
ayrı tur; her biri 4 sembol/16 TF, strict veya retrospective:

| Tarih | Ana TF | Araştırma | Python karakter aralığı | Hata |
|---|---|---|---:|---:|
| 04.09.2026 | 1h | strict | 3.157–3.729 | 0 |
| 08.09.2026 | 2h | retrospective | 3.263–3.696 | 0 |
| 11.09.2026 | 4h | strict | 3.224–3.884 | 0 |
| 15.09.2026 | 1d | retrospective | 3.063–3.807 | 0 |
| 18.09.2026 | 1h | retrospective | 3.426–3.914 | 0 |
| 21.09.2026 | 2h | strict | 3.606–3.928 | 0 |
| 23.09.2026 | 4h | retrospective | 4.108–4.497 | 0 |
| 25.09.2026 | 1d | strict | 3.689–4.069 | 0 |

23 Eylül TAVHL örneği 4.497 Unicode kod noktası ama **4.500 UTF-16 kod
birimidir**; denetim hem kod noktası hem UTF-16 sınırını kontrol eder. Ayrıca
28 sembollük 25 Eylül 4h retrospective (3.198–4.488) ve 23 Eylül 4h
retrospective (3.010–4.497) kontrolleri son korumayla 0 hata verdi. 18 Eylül
2h strict ve 25 Eylül 1d strict için 28'er sembollük ek kontroller de 0 hatalıydı
(sınır mekanizması son UTF-16 eklemesinden önce; en uzunları 4.196 ve 4.128,
üç astral sembolle bile sınırın altında). Bu 8 turda 32 ve geniş taramalarda
112 üretim vardır; bazı aynı sembol/kesitler tekrarlanır, bağımsız 144 vaka
değildir. Bunlar **prompt üretimi ve sözleşme testleri**, farklı AI modelleriyle
8 canlı yanıt testi değildir. Veriler sadece yerel tarihsel arşivle sınırlıdır.

Sentetik testlerde tam 4.500 UTF-16 sınırı kabul, 4.501 birim reddedilir;
emojili 4.500 kod noktasının 4.501 birim olabileceği ayrıca test edilir. Her
olası gelecek veri kesiti 4.500'e sığacak diye garanti edilmez: güvenli şekilde
sığmıyorsa sessiz kesme yerine `ValueError` döner.

Güncel otomatik örnekler: `BIMAS_2026-09-25_kompakt_v4.txt` 4.412 Unicode /
4.415 UTF-16; `ALARK_2026-09-25_kompakt_v4.txt` 4.251 / 4.254;
`TAVHL_2026-09-25_kompakt_v4.txt` 4.488 / 4.491. Bunlar retrospective'dir.
Canlı geçmiş simülasyonu için kesit sonrası araştırma bulgularını içermeyen
`BIMAS_2026-09-25_kompakt_v4_strict.txt` ve
`ALARK_2026-09-25_kompakt_v4_strict.txt` örnekleri de üretilmiştir.

Tüm depo test koşusu: **4.980 passed, 43 skipped** (14 dk 37 sn). Bu koşu
UTF-16 sınırının eklenmesiyle paralel yürüdüğünden, son kod özelinde ayrıca
`test_ai_prompt_compact.py test_ai_prompt_commentary.py` çalıştırıldı: **34
passed**; son kodla sekiz tur ve iki geniş tarama tekrarlandı. Compileall ve
`git diff --check` temizdir. Bu testler gerçek model yanıtı/Telegram teslimi
veya finansal sonuç garantisi değildir.
