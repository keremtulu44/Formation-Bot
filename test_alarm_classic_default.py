"""Classic formation + Stabil default; explicit env may opt in to domain."""
import os
import subprocess
import sys


def _config(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in {"YENI_DOMAIN_ALARM", "STABIL_GERI_ALIM_ALARM"}}
    env.update(extra)
    output = subprocess.check_output([sys.executable, "-c", (
        "import config; print(config.YENI_DOMAIN_ALARM, config.STABIL_GERI_ALIM_ALARM, "
        "','.join(config.ALERT_STATES), ','.join(sorted(config.WATCH_STATES)))")],
        env=env, text=True)
    return output.strip()


def test_default_classic_stabil_and_explicit_override():
    default = _config()
    assert default.startswith("False True ")
    assert "KIRILIM_TEYITLI,RETEST_BASARILI,KIRILIM_GECERSIZLESTI" in default
    assert "SIKISMA_GUCLENIYOR" in default
    assert _config(YENI_DOMAIN_ALARM="1").startswith("True True ")
    assert _config(STABIL_GERI_ALIM_ALARM="0").startswith("False False ")
