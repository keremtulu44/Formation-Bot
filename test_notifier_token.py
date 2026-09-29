from notifier import _env_temizle, token_bicimi_uygun_mu, telegram_hata_ipucu


def test_env_temizle_bosluk_ve_tirnak():
    assert _env_temizle("  123456:ABC  ") == "123456:ABC"
    assert _env_temizle('"123456:ABC"') == "123456:ABC"
    assert _env_temizle("'123456:ABC'") == "123456:ABC"
    assert _env_temizle('  " 123456:ABC "  ') == "123456:ABC"
    assert _env_temizle(None) == ""
    assert _env_temizle("") == ""


def test_token_bicimi_uygun_mu_dogru():
    assert token_bicimi_uygun_mu("123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw")
    assert token_bicimi_uygun_mu("987654321:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890")
    assert token_bicimi_uygun_mu('  "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  ')


def test_token_bicimi_uygun_mu_yanlis():
    assert not token_bicimi_uygun_mu("")
    assert not token_bicimi_uygun_mu("12345")
    assert not token_bicimi_uygun_mu("abc:def")
    assert not token_bicimi_uygun_mu("123456789")
    assert not token_bicimi_uygun_mu("123:short")
    assert not token_bicimi_uygun_mu(None)
    assert not token_bicimi_uygun_mu("123456789:")  # ikinci kısım boş


def test_telegram_hata_ipucu_401():
    ipucu = telegram_hata_ipucu(401, "Unauthorized")
    assert "401" in ipucu or "geçersiz" in ipucu.lower() or "token" in ipucu.lower()
    assert "BotFather" in ipucu or "token" in ipucu.lower()


def test_telegram_hata_ipucu_403():
    ipucu = telegram_hata_ipucu(403, "Forbidden: bot was blocked")
    assert "403" in ipucu or "engellen" in ipucu.lower() or "sohbet" in ipucu.lower()


def test_telegram_hata_ipucu_404():
    ipucu = telegram_hata_ipucu(404, "Not Found")
    assert "404" in ipucu


def test_telegram_hata_ipucu_400():
    ipucu = telegram_hata_ipucu(400, "Bad Request: chat not found")
    assert "400" in ipucu or "chat_id" in ipucu.lower()


def test_telegram_hata_ipucu_409():
    ipucu = telegram_hata_ipucu(409, "Conflict: terminated by other getUpdates")
    assert "409" in ipucu or "aynı" in ipucu.lower() or "Conflict" in ipucu


def test_telegram_hata_ipucu_chat_not_found():
    ipucu = telegram_hata_ipucu(400, "Bad Request: chat not found")
    low = ipucu.lower()
    # chat not found için Türkçe ipucu ve /start içermeli
    assert "chat not found" in low or "sohbet" in low
    assert "start" in low or "sohbet" in low


def test_telegram_hata_ipucu_blocked():
    ipucu = telegram_hata_ipucu(403, "Forbidden: bot was blocked by the user")
    low = ipucu.lower()
    # engellenmiş / blocked / Unblock içermeli
    assert "engellen" in low or "blocked" in low or "unblock" in low or "engel" in low


def test_env_temizle_sayisal():
    assert _env_temizle(12345) == "12345"
    assert _env_temizle(True) == "True"


def test_token_bicimi_uzunluk():
    # Çok kısa token geçersiz
    assert not token_bicimi_uygun_mu("123456789:short")
    # Çok uzun ve doğru format geçerli
    assert token_bicimi_uygun_mu("1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef123456")


def test_telegram_hata_ipucu_bilinmeyen_kod():
    ipucu = telegram_hata_ipucu(500, "Internal Server Error")
    assert "500" in ipucu or "Telegram hatası" in ipucu


def test_token_temizle_ve_dogrula():
    token = '  "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"  '
    temiz = _env_temizle(token)
    assert token_bicimi_uygun_mu(temiz)
    assert temiz == "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
