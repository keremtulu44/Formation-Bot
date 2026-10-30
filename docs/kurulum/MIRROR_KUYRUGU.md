# Formasyon mirror kuyruğu

**Güncel mod:** Bot Supabase'den eski kayıtları okuyabilir, fakat hiçbir tabloya yazmaz. Mirror kuyruğuna yeni satır eklenmez veya gönderilmez; eski kuyruk dosyası silinmez. Aşağıdaki açıklama önceki yazma modunun davranışıdır. Uzak heartbeat artık güncellenmez; canlılık için Render `/health` kullanılmalıdır.

Render'ın geçici diskinde yazılan yeni karne, bildirim mühürleri, önbellek ve formasyon geçmişi redeploy veya instance değişiminde kaybolabilir. Supabase'deki eski kopya yeni gelişmeleri kapsamaz; bu, tekrar bildirim veya eksik geçmiş riskidir. Supabase ile çoklu örnek bildirimi de kapalıdır.

## Önceki yazma modu

Formasyon geçmişi önce `DATA_DIR/formation_history` altında saklanır; f2 tabloları uzak yedektir. Tarama boyunca üretilen satırlar aynı mantıksal anahtar için birleştirilerek `DATA_DIR/f2_kuyruk.sqlite3` içinde tutulur ve her hisse sonrasında sınırlı sayıda batch gönderilir. Önceki `f2_kuyruk.json` varsa yeni kuyruk oluşturulurken bir kez içe alınır; eski dosya silinmez.

- 5.000 satır uyarı eşiğidir; aşılınca kuyruktan satır **silinmez**. Uzun Supabase kesintilerinde disk kullanımı artabilir; izleyin.
- Bir 400/422 veya geçici hata batch'i silmez. Hata logunu inceleyin; hatalı satır batch'in ilerlemesini engelleyebilir, bu henüz otomatik satır izolasyonu değildir. Tekrar denemeler artan aralıklarla yapılır.
- Yerel SQLite, Supabase'e yazılıncaya kadar tek başına uzak yedek değildir. Render `DATA_DIR=/tmp/...` kullanıyorsa redeploy/instance değişikliği bekleyen kuyruk ve yerel geçmişi kaybettirebilir. Kalıcı disk yoksa deploy öncesinde kuyruk ve uzak f2 verileri doğrulanmalıdır. Daha önce atılan veya kaybolan kayıtların bu değişiklikle geri geldiği varsayılamaz.
- `Supabase f2_* flush reddedildi`, `Tarama sırasında mirror flush atlandı` ve kuyruk büyüklüğü takip edilmelidir. `state:heartbeat` içindeki `formation_mirror` alanı bekleyen satırları, tablolara dağılımı, süreçte gönderilen sayıyı ve son HTTP hatasını gösterir. `/health` uygulamanın yaşadığını gösterir; f2 yedeğinin eksiksiz olduğunu kanıtlamaz.
