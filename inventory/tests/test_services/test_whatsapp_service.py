from inventory.services.whatsapp_service import WhatsAppService


class TestFormatPhoneNumber:
    def test_keeps_e164_format(self):
        assert WhatsAppService.format_phone_number("+254712345678") == "+254712345678"

    def test_strips_leading_zero(self):
        assert WhatsAppService.format_phone_number("0712345678") == "+254712345678"

    def test_strips_local_prefix(self):
        assert WhatsAppService.format_phone_number("254712345678") == "+254712345678"

    def test_handles_whitespace(self):
        assert WhatsAppService.format_phone_number(" 0712 345 678 ") == "+254712345678"

    def test_handles_safaricom_format(self):
        result = WhatsAppService.format_phone_number("+254 (0) 712-345-678")
        assert result == "+2540712345678"

    def test_returns_none_for_empty(self):
        assert WhatsAppService.format_phone_number("") is None

    def test_returns_none_for_none(self):
        assert WhatsAppService.format_phone_number(None) is None

    def test_short_number_returns_none(self):
        assert WhatsAppService.format_phone_number("123") is None
