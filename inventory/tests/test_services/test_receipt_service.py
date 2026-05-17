import pytest
from decimal import Decimal
from inventory.services.receipt_service import ReceiptService


pytestmark = pytest.mark.django_db


class TestNumberToWords:
    def test_zero(self):
        assert "Zero" in ReceiptService.number_to_words(Decimal("0"))

    def test_whole_number(self):
        result = ReceiptService.number_to_words(Decimal("1500"))
        assert "One" in result

    def test_with_cents(self):
        result = ReceiptService.number_to_words(Decimal("1250.50"))
        assert "Shilling" in result

    def test_one_shilling(self):
        result = ReceiptService.number_to_words(Decimal("1"))
        assert "One" in result or "Shilling" in result


class TestGenerateReceiptNumber:
    def test_returns_string(self, order):
        number = ReceiptService.generate_receipt_number(order)
        assert isinstance(number, str)
        assert len(number) > 0

    def test_unique_per_order(self, order):
        from inventory.models import Order as OrderModel, Customer
        n1 = ReceiptService.generate_receipt_number(order)
        c2 = Customer.objects.create(name="Test2", phone="+254700000002")
        o2 = OrderModel.objects.create(customer=c2, brand=order.brand)
        n2 = ReceiptService.generate_receipt_number(o2)
        assert n1 != n2


class TestGetReceiptUrl:
    def test_returns_url_string(self, order):
        url = ReceiptService.get_receipt_url(order, "html")
        assert str(order.order_id) in url
        assert "format=html" in url or "format=pdf" in url

    def test_pdf_format(self, order):
        url = ReceiptService.get_receipt_url(order, "pdf")
        assert "pdf" in url


class TestGetReceiptContext:
    def test_returns_dict_with_order_data(self, order):
        ctx = ReceiptService.get_receipt_context(order)
        assert isinstance(ctx, dict)
        assert ctx["order"] == order
        assert "customer_name" in ctx
        assert "receipt_number" in ctx
