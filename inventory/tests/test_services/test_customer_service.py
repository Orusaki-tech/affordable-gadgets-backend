import pytest
from inventory.models import Customer
from inventory.services.customer_service import CustomerService


pytestmark = pytest.mark.django_db


class TestRecognizeCustomer:
    def test_recognizes_existing_customer(self):
        customer = Customer.objects.create(
            name="John Doe", phone="+254700000001", email="john@example.com"
        )
        result = CustomerService.recognize_customer("+254700000001")
        assert result["is_returning_customer"] is True
        assert result["customer"]["name"] == "John Doe"
        assert result["customer"]["id"] == customer.id

    def test_unknown_phone_returns_none(self):
        result = CustomerService.recognize_customer("+254700009999")
        assert result["is_returning_customer"] is False
        assert result["customer"] is None

    def test_updates_last_lead_at(self):
        customer = Customer.objects.create(name="Jane", phone="+254700000002")
        result = CustomerService.recognize_customer("+254700000002")
        assert result["is_returning_customer"] is True

    def test_empty_phone_handled_gracefully(self):
        result = CustomerService.recognize_customer("")
        assert result["is_returning_customer"] is False

    def test_none_phone_handled_gracefully(self):
        result = CustomerService.recognize_customer(None)
        assert result["is_returning_customer"] is False

    def test_welcome_message_includes_name(self):
        Customer.objects.create(name="Alice", phone="+254700000003")
        result = CustomerService.recognize_customer("+254700000003")
        assert "Alice" in result["message"]


class TestGetOrCreateCustomer:
    def test_creates_new_customer(self):
        customer, created = CustomerService.get_or_create_customer(
            "Bob", "+254700000010", "bob@example.com", "123 Main St"
        )
        assert created is True
        assert customer.name == "Bob"
        assert customer.phone == "+254700000010"

    def test_returns_existing_customer(self):
        Customer.objects.create(name="Old Name", phone="+254700000020")
        customer, created = CustomerService.get_or_create_customer(
            "New Name", "+254700000020"
        )
        assert created is False
        assert customer.name == "New Name"

    def test_merges_email_on_existing(self):
        Customer.objects.create(name="Charlie", phone="+254700000030")
        customer, _ = CustomerService.get_or_create_customer(
            "Charlie", "+254700000030", email="charlie@new.com"
        )
        assert customer.email == "charlie@new.com"

    def test_does_not_clear_email_when_not_provided(self):
        Customer.objects.create(name="Diana", phone="+254700000040", email="diana@test.com")
        customer, _ = CustomerService.get_or_create_customer("Diana", "+254700000040")
        assert customer.email == "diana@test.com"
