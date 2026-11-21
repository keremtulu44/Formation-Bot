# P0 / P6 ölçüm pilotu — yöntem ve tekrar koşusu

**[Aynı örneklemde eski → yeni sonuç tablosu](ALARM_POLITIKA_P0_P6_2026-11-20.md)** · [önceki 88 sembollük araştırma](ALARM_POLITIKA_SONUCLARI.md). Eski çalışmayla bu pilot farklı evren ve dönemlerdir; ölçüm düzeltmesinin etkisi iki ayrı belgedeki yüzdeler çıkarılarak değil, yeni tablonun *aynı satırındaki* eski ve yeni değerler karşılaştırılarak okunmalıdır.

## Nasıl tekrar edilir?

Repo kökünde, araştırma bağımlılıklarının kurulu olduğu ortamda, **yeni ve boş** bir çıktı dizini kullanın. Canlı bot, ağ, token veya Telegram gerekmez. Bu pilot `STOCK_UNIVERSE` için repo varsayılanını kullanır, üretimdeki gizli ayarı bildiğini varsaymaz.

```bash
export STOCK_UNIVERSE=''
OUT=var/p0_p6_native_pilot
python -m research.domain_alarm_replay --aktif-evren --son-bar 480 --rapor-atla --cikti "$OUT"
python -m research.alarm_politika --cikti "$OUT" --ilk 2026-10-19 --son 2026-11-18 \
  --rapor var/p0_p6_sonuc.md
```

- Her serinin **son en fazla 480 arşiv mumu** motora girer. Ölçüm penceresinden önceki mumlar formasyon, bağlam ve cooldown için kullanılır; sonraki mevcut mumlar yalnız sonuç ölçümü için kullanılır. Bu kısa pilot, motorları tüm arşivden başlatan bir koşuya eşdeğer değildir. Tam geçmiş istenirse ayrı dizinde `--son-bar` verilmeden çalıştırılabilir.
- Gün = İstanbul yerel tarihi. Dört periyodun ve bütün kapsanan sembollerin bar envanterinde ortak olan tarihler kullanılır. Bir barda hiç tetik olmaması günü paydadan düşürmez. Replay'in sıfır ileri barlı son çapa için satır üretmemesi ve son günün kısmi olabilmesi nedeniyle serilerin son tarihi yük ölçümüne alınmaz. Günlük mum UTC'de önceki güne denk gelse bile doğru seansa yazılır.
- P0 ve P6 **aynı adaylar** üzerinde ayrı ayrı 6 bar cooldown uygular. Sıklık kart sayar; yönlü isabet yalnız `yon_asim_100` ölçülebilen kartları sayar. Herhangi yöne isabet 12 barlık lehte **veya** aleyhte aşımı kullanır; iki tarafta birden hareket şart değildir. Güçlü tetik yakalama bir getiri oranı değil, ≥1,5 ATR yapan ham yön satırlarının ne kadarının kart olarak kaldığıdır. Ufku dolmayanlar zaten bilinen güçlü tetik değildir; bu yüzden bu sütunun eski/yeni payı aynıdır.
- Önceki hesabı yeniden üretirken *aynı günler ve adaylar* için eski seri-günü paydası, eksik yönlü sonucu başarısız sayma ve `yon_tepe_atr`/`yon_dip_atr` (en çok 40 bar) kullanılır. Eski çalışmanın ham JSONL'i değil, güncel üreticinin çıktısı kullanılmıştır. Bilinmeyen bağlamdaki P6 varsayılanı dahil filtre değiştirilmemiştir: burada ölçüm değişikliğini kural değişikliğiyle karıştırmıyoruz.
- Bunlar native mumlardan hesaplanan potansiyel kartlar. Gerçek kanal yönlendirmesi, kullanıcıya teslim, günlük Telegram limitleri ve maliyetlerden sonra işlem getirisi modellenmedi. Bu pencere ileriye dönük doğrulama veya P6'yı yayına alma gerekçesi değildir.

`--tum-politikalar` diğer araştırma politikalarını da gösterir. Ham JSONL dosyaları yerelde kalır; yayımlanan çıktı küçük Markdown tablosudur.
