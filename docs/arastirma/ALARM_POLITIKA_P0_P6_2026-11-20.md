# Alarm politikası: aynı örneklemde eski ve düzeltilmiş ölçüm

2026-10-19 – 2026-11-18 · 22 ortak İstanbul seansı · 50/57 aktif sembol × 4 native zaman dilimi.
Arşiv dışında: BRENT, USDTRY, XAGUSD, XAUUSD, XBANK, XU50, XUSIN.

| Politika | Kart | Eski kart/seri-günü | Kart/seans ort. (medyan) | En yoğun seans | Ölçülen / henüz ölçülemeyen | Yönlü ≥1 ATR eski → yeni | Herhangi yöne ≥1 ATR eski → yeni | Güçlü tetik yakalama |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| P0 | 2136 | 0,47 | 97,09 (99,5) | 119 (2026-11-17) | 1913 / 223 | 60,1% → 67,1% | 98,8% → 99,2% | 33,3% |
| P6 | 785 | 0,17 | 35,68 (31,0) | 89 (2026-11-04) | 729 / 56 | 62,2% → 66,9% | 99,5% → 99,7% | 12,0% |

P0: her tetik; P6: mevcut bağlam filtresi. İki hesapta aynı kartlar; filtre eşikleri değişmedi. Eski yönlü hesap boş sonucu başarısız, eski yönsüz hesap 40 bara kadar uzanımı kullanır. Yeni ikisi de 12 mum kullanır. Ufku dolmayan kart sıklığa dahil, isabete dahil değil.

Güçlü yakalama = gönderilen ≥1,5 ATR yönlü tetik / tüm ölçülen ≥1,5 ATR yönlü tetikler (12 bar). Cooldown sembol ve periyot başına 6 bar; pencere öncesi geçmiş korunur. Replay'in yönsüz tetikten ürettiği iki yön satırı bağımsız işlem değildir.

Seanslar tetiklerden değil, tüm kapsanan serilerde bar gözlenen İstanbul tarihlerinden gelir; sıfır kartlı günler dahildir. Eski seri-günü ile yeni kanal toplamının birimleri farklıdır. Sayılar potansiyel karttır; canlı teslimat, getiri veya canlıdaki türetilmiş mumların doğrulaması değildir.
