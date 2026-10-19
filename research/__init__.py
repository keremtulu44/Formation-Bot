"""Arşiv tabanlı ölçüm hattı (araştırma tarafı).

Canlı tarayıcıdan bağımsızdır: ``backfill_data/`` arşivini okur, repo'nun
değiştirilmemiş domain motorlarını çalıştırır ve ölçüm satırları üretir.
Canlı yolda (``domain_engines.runner`` içi in-memory state) hiçbir yan
etkisi yoktur; yalnız ``run_domain_engines`` çağrısı üzerinden okur.
"""
