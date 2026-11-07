# DOCO üzerinde destek ve direnç yolu — iki açıklayıcı örnek

Bu iki örnek **gösterim için seçildi**, rastgele veya temsilî bir örneklem değil; oranların yerine geçmez. Fiyatlar arşivden, saatler İstanbul yerel saatidir. Her çizgi, ilgili 4s mumun başında bilinen günlük Stabil çizgisidir. Aday `HORIZONTAL_AFTER_DROP` kullanıcının görsel yatay tanımıyla doğrulanmış sayılmaz.

## Destek: kırılma → çizgi aşağı → aday yatay → yeniden kırılma

| 4s kapanış zamanı | Adım | Destek çizgisi | Fiyat kapanışı | Anlamı |
|---|---|---:|---:|---|
| 11.03.2026 13:30 | Aşağı kırılma | 9.602,50 | 9.422,50 | Fiyat eski desteğin altında kapandı. |
| 16.03.2026 13:30 | Çizgi ilk aşağı güncelleme | 8.860,00 | 8.665,00 | Fiyat yeni çizginin de altında; eski çizgi hâlâ geri alınmamış. |
| 16.03.2026 17:30 | Yeni çizginin üstüne kapanış | 8.860,00 | 8.892,50 | Aday rejim hâlâ aşağı basamak; eski 9.602,50 çizgisi geri alınmış değil. |
| 18.03.2026 13:30 | Aday düz proxy | 8.860,00 | 9.355,00 | Aynı yeni çizgi, fiyat üstünde; bu yalnız proxy sınıfı. |
| 19.03.2026 13:00 | Yeni çizginin yeniden altı | 8.860,00 | 8.702,50 | Düz proxy ardından da aşağı kapanış mümkün. |

## Direnç: kırılma → çizgi yukarı → aday yatay → yeniden kırılma

| 4s kapanış zamanı | Adım | Direnç çizgisi | Fiyat kapanışı | Anlamı |
|---|---|---:|---:|---|
| 18.02.2026 13:30 | Yukarı kırılma | 10.692,50 | 10.977,50 | Fiyat eski direncin üstünde kapandı. |
| 23.02.2026 13:30 | Çizgi ilk yukarı güncelleme | 11.307,50 | 11.247,50 | Fiyat yeni çizginin altında; eski çizginin üstünde. |
| 25.02.2026 13:30 | Aday düz proxy | 11.307,50 | 11.285,00 | Aynı yeni çizginin altında kapanış. |
| 25.02.2026 17:30 | Yeni çizginin yeniden üstü | 11.307,50 | 11.390,00 | Düz proxy ardından da yukarı kapanış mümkün. |

Bunlar mekanik ve nedensel birer sonuç değil; iki seçilmiş epizodun kapanış bazlı kaydıdır. Eski/yeni çizginin ve fiyatın ayrı takip edilmesi önemlidir. [Toplu yol sonuçları](yol_bulgulari.md) ve [doğrulama](DOGRULAMA.md).
