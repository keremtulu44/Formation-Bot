"""İsteğe bağlı, yalnız başlıkları düzenleyen AI yanıtı biçimleyicisi.

Bu fonksiyon model çağırmaz, metnin doğruluğunu veya finansal güvenliğini
onaylamaz ve alarm/Telegram akışına kendiliğinden bağlanmaz.
"""
from __future__ import annotations

import re

_HEADINGS = ("Mevcut durum", "Bağlam", "Replay notu")
_DECORATED = ("🧭 Mevcut durum", "🔎 Bağlam", "🕯️ Replay notu")
_EMOJIS = ("🧭", "🔎", "🕯️", "🕯")


def _heading(line: str) -> str | None:
    candidate = line.strip()
    candidate = re.sub(r"^#{1,3}\s+", "", candidate)
    # Support the common **Heading:** and **Heading**: forms, not arbitrary
    # inline markup or a body line that happens to mention a heading.
    candidate = candidate.strip("* ").removesuffix(":").strip("* ")
    for emoji in _EMOJIS:
        if candidate.startswith(emoji):
            candidate = candidate[len(emoji):].strip()
            break
    return candidate if candidate in _HEADINGS else None


def format_ai_commentary(text: str) -> str:
    """Üç bilinen başlığı sırayla doğrula; içeriği yeniden yorumlama.

    Başlıklar ayrı satırda olmalı; eksik, boş, yinelenmiş veya sırası bozuk
    bölümler ve giriş metni hata verir. Başlık dışı metin aynen korunur;
    sembol/emoji veya finansal iddialar doğrulanmaz.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("AI yanıtı boş veya metin değil")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sections: list[list[str]] = []
    found: list[str] = []
    for line in lines:
        heading = _heading(line)
        if heading is not None:
            found.append(heading)
            sections.append([])
        elif not sections:
            if line.strip():
                raise ValueError("İlk başlık öncesinde metin var")
        else:
            sections[-1].append(line)
    if tuple(found) != _HEADINGS:
        raise ValueError("AI yanıtında üç başlık doğru sırayla ve birer kez bulunmalı")
    if any(not any(line.strip() for line in section) for section in sections):
        raise ValueError("AI yanıtında boş bölüm var")
    output = []
    for heading, body in zip(_DECORATED, sections):
        # Trim only leading/trailing blank separator lines, not section content.
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        output.append(heading + "\n" + "\n".join(body))
    return "\n\n".join(output)
