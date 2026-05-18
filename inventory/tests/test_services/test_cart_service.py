from decimal import Decimal

import pytest
from django.utils import timezone

from inventory.models import AdminRole, Cart, CartItem, InventoryUnit, Notification
from inventory.services.cart_service import CartService

pytestmark = pytest.mark.django_db


@pytest.fixture
def cart(brand):
    return Cart.objects.create(session_key="test-session", brand=brand)


class TestValidateUnitForCart:
    def test_available_unit_passes(self, cart, available_unit):
        CartService._validate_unit_for_cart(cart, available_unit)

    def test_sold_unit_raises(self, cart, sold_unit):
        with pytest.raises(ValueError, match="not available"):
            CartService._validate_unit_for_cart(cart, sold_unit)

    def test_not_available_online_raises(self, cart, product):
        unit = InventoryUnit.objects.create(
            product_template=product,
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=False,
            selling_price=Decimal("1000"),
            cost_of_unit=Decimal("500"),
        )
        with pytest.raises(ValueError, match="not available for online"):
            CartService._validate_unit_for_cart(cart, unit)


class TestGetOrCreateCart:
    def test_creates_new_cart(self, brand):
        cart = CartService.get_or_create_cart(session_key="session123", brand=brand)
        assert cart is not None
        assert cart.session_key == "session123"
        assert cart.is_submitted is False

    def test_finds_existing_by_session(self, brand):
        existing = Cart.objects.create(session_key="existing-session", brand=brand)
        cart = CartService.get_or_create_cart(session_key="existing-session", brand=brand)
        assert cart.id == existing.id

    def test_finds_existing_by_phone(self, brand):
        existing = Cart.objects.create(customer_phone="+254700000001", brand=brand)
        cart = CartService.get_or_create_cart(customer_phone="+254700000001", brand=brand)
        assert cart.id == existing.id

    def test_phone_takes_precedence_over_session(self, brand):
        Cart.objects.create(session_key="session-phone-test", brand=brand)
        phone_cart = Cart.objects.create(customer_phone="+254700000002", brand=brand)
        cart = CartService.get_or_create_cart(
            session_key="session-phone-test", customer_phone="+254700000002", brand=brand
        )
        assert cart.id == phone_cart.id

    def test_raises_without_brand(self):
        with pytest.raises(ValueError, match="Brand"):
            CartService.get_or_create_cart(session_key="test")

    def test_recreates_expired_cart(self, brand):
        old = Cart.objects.create(session_key="expired", brand=brand)
        old.expires_at = timezone.now() - timezone.timedelta(hours=1)
        old.save()
        cart = CartService.get_or_create_cart(session_key="expired", brand=brand)
        assert cart.id != old.id


class TestAddItemToCart:
    def test_adds_item(self, cart, available_unit):
        item = CartService.add_item_to_cart(cart, available_unit)
        assert item is not None
        assert CartItem.objects.filter(cart=cart, inventory_unit=available_unit).exists()

    def test_custom_quantity(self, cart, available_unit):
        item = CartService.add_item_to_cart(cart, available_unit, quantity=3)
        assert item.quantity == 3

    def test_increments_existing_item(self, cart, available_unit):
        CartService.add_item_to_cart(cart, available_unit, quantity=1)
        item = CartService.add_item_to_cart(cart, available_unit, quantity=2)
        assert item.quantity == 3

    def test_custom_unit_price(self, cart, available_unit):
        item = CartService.add_item_to_cart(cart, available_unit, unit_price=Decimal("500"))
        assert item.unit_price == Decimal("500")


class TestCheckoutCart:
    def _checkout(self, cart, **kw):
        defaults = dict(
            customer_name="John", customer_phone="+254700000001", delivery_address="123 Main St"
        )
        defaults.update(kw)
        return CartService.checkout_cart(cart, **defaults)

    def test_converts_cart_to_lead(self, cart, available_unit):
        CartService.add_item_to_cart(cart, available_unit, unit_price=Decimal("1000"))
        lead = self._checkout(cart)
        assert lead is not None
        assert lead.customer_name == "John"
        assert lead.total_value >= Decimal("1000")

    def test_marks_cart_as_submitted(self, cart, available_unit):
        CartService.add_item_to_cart(cart, available_unit)
        self._checkout(cart)
        cart.refresh_from_db()
        assert cart.is_submitted is True

    def test_raises_on_submitted_cart(self, cart, available_unit):
        CartService.add_item_to_cart(cart, available_unit)
        self._checkout(cart)
        with pytest.raises(ValueError, match="submitted"):
            self._checkout(cart, customer_name="Jane", customer_phone="+254700000002")

    def test_creates_lead_items(self, cart, available_unit):
        CartService.add_item_to_cart(cart, available_unit)
        lead = self._checkout(cart)
        assert lead.items.count() == 1
        assert lead.items.first().inventory_unit == available_unit

    def test_creates_notifications(self, cart, available_unit, brand, sales_admin):
        role = AdminRole.objects.get(name=AdminRole.RoleChoices.SALESPERSON)
        sales_admin.roles.add(role)
        sales_admin.brands.add(brand)
        CartService.add_item_to_cart(cart, available_unit)
        self._checkout(cart)
        notifications = Notification.objects.filter(
            notification_type=Notification.NotificationType.NEW_LEAD
        )
        assert notifications.count() >= 1

    def test_includes_delivery_fee_in_total(self, cart, available_unit):
        CartService.add_item_to_cart(cart, available_unit, unit_price=Decimal("1000"))
        lead = self._checkout(cart, delivery_fee=Decimal("500"))
        assert lead.total_value == Decimal("1500")
