"""Başlık biçimleme içerik veya finansal doğruluk denetimi değildir."""
import pytest

from ai_prompt import format_ai_commentary


def test_plain_and_markdown_headings_are_normalized_without_rewriting_body():
    source = ('**Mevcut durum**\r\n106,80; +OB 101,50–106,00.\r\n\r\n'
              '## Bağlam:\r\nCHoCH ↓109,90 ve karşı kanıt.\r\n\r\n'
              '**Replay notu:**\r\nTemas 106,60; sonraki 106,80.')
    assert format_ai_commentary(source) == (
        '🧭 Mevcut durum\n106,80; +OB 101,50–106,00.\n\n'
        '🔎 Bağlam\nCHoCH ↓109,90 ve karşı kanıt.\n\n'
        '🕯️ Replay notu\nTemas 106,60; sonraki 106,80.')


def test_formatted_text_is_idempotent():
    text = ('🧭 Mevcut durum\nGörüş.\n\n🔎 Bağlam\nKarşı kanıt.\n\n'
            '🕯️ Replay notu\nSonraki kapanış bilinmiyor.')
    assert format_ai_commentary(format_ai_commentary(text)) == text


@pytest.mark.parametrize('bad', [
    '',
    'başlangıç\nMevcut durum\na\nBağlam\nb\nReplay notu\nc',
    'Mevcut durum\na\nReplay notu\nb\nBağlam\nc',
    'Mevcut durum\na\nBağlam\nb',
    'Mevcut durum\na\nBağlam\n\nReplay notu\nc',
    'Mevcut durum\na\nBağlam\nb\nBağlam\nb\nReplay notu\nc',
    'Mevcut durum: görüş\nBağlam\nb\nReplay notu\nc',
])
def test_malformed_output_is_not_silently_rewritten(bad):
    with pytest.raises(ValueError):
        format_ai_commentary(bad)


def test_body_is_not_markdown_stripped_or_financially_reinterpreted():
    text = 'Mevcut durum\n**Dikkat:** 100,00\nBağlam\nİçerik\nReplay notu\nBilinmiyor'
    assert '**Dikkat:** 100,00' in format_ai_commentary(text)
