# OB olay seçimi — taşınabilir kanıt paketi

27 Kasım 2026. [Karar ve sınırlar](../../../denetim/ALARM_OLAY_SECIMI_OB_2026-11-27.md).

- `summary.json`: 200 seri için arşiv/kod hash'leri, eski v2 eşitliği, önek kontrolleri, kanal ve politika/cooldown karşılaştırması. Araştırma koşusu anındaki hash'lerdir; daha sonra test/doküman eklenmesi bunların üzerine yazılmaz.
- `examples.csv`: sınıf × taraf başına kronolojik ilk üç örnek; gerçekleşmiş getiriye göre seçilmez. Kaynak UTC mum açılış zamanını, önceden bilinen bölgeyi, OHLC ve diğer sebepleri içerir.
- `evidence.json`: tam ham çıktının SHA256/boyut kaydı, eski OB tetiklerinin mum ucunda kapanış kontrolü ve son test kaydı. Büyük ham `rows.jsonl` Git'e eklenmez; yerel kaynak aşağıda.

## Yeniden üretim

Repo kökünde, yerel arşivler ve nedensel v2 tabanı mevcutken (boş/yeni çıktı dizini kullanın):

```sh
env TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID= TELEGRAM_GROUP_ID= \
    TELEGRAM_CHANNEL_ID= SUPABASE_URL= SUPABASE_SERVICE_ROLE_KEY= \
    .venv/bin/python -m research.ob_alarm_event_study \
    --output var/ob_alarm_events_reproduce
```

Kaydedilen tam koşu: `var/ob_alarm_event_final_20261127/{summary.json,rows.jsonl}`.
Tarihî taban: `var/alarm_recall_v2_20261127/{events.jsonl,decisions.jsonl,summary.json}`.
Seriler `backfill_data/` içindeki native 1h/2h/4h/1d arşivlerinden gelir. Bu çalışma, tarihî v2'nin OB fiyat-içi koşulunu bilerek dondurur; yeni kuralın kendisine kıyaslanmasını engeller.

Sayaç yorumlama:

- `groups`: OB olay sebepleri; aynı mumda başka sebep olabilir, bağımsız mesaj değildir.
- `capacity_counterfactual`: politika ve altı bar cooldown uygulanan kanal adayları; **Stabil/scheduler/gerçek teslim öncesi**.
- `prefix_probes`: seçilen her serinin tek geçmiş önek eşitliği; her olası uzunluk için matematiksel kanıt değildir. Üretim OB yardımcısı ile bağımsız ön-bölge tanımı ayrıca her uygun mumda kıyaslanır.

## Regresyon komutu

```sh
.venv/bin/python -m pytest -q \
 test_ob_alarm_events.py test_domain_alarm_service.py test_domain_alarm_politika.py \
 test_alarm_audit_fixes.py test_domain_incremental_parity.py test_domain_engines.py \
 test_domain_integration_regressions.py test_stabil_resistance_delivery_e2e.py \
 test_alarm_classic_default.py test_tekrar_alarm_korumasi.py \
 test_formation_trigger_geometry.py test_causal_alarm_replay.py test_alarm_recall_breakdown.py
```

E2E taşıyıcı gerçek Telegram yerine offline fixture kullanır. Testler Python3.11 ortamında çalıştırıldı; dağıtım ortamının Python3.12 olduğu notu korunur. Tam repo suite'i yeniden çalıştırılmış sayılmaz.
