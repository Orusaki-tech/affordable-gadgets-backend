import pytest
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from inventory.models import Admin, AdminRole, InventoryUnit, Lead, Order
from inventory.services.lead_service import LeadService


pytestmark = pytest.mark.django_db


@pytest.fixture
def lead_with_items(brand, customer, product, available_unit):
    lead = Lead.objects.create(
        customer=customer,
        brand=brand,
        status=Lead.StatusChoices.NEW,
        total_value=Decimal("15000.00"),
        expires_at=timezone.now() + timedelta(days=7),
    )
    lead.items.create(inventory_unit=available_unit, quantity=1, unit_price=Decimal("15000.00"))
    return lead


class TestAutoAssignLead:
    def test_assigns_to_salesperson_with_fewest_leads(
        self, lead_with_items, brand, sales_admin
    ):
        role = AdminRole.objects.get(name=AdminRole.RoleChoices.SALESPERSON)
        sales_admin.roles.add(role)
        sales_admin.brands.add(brand)
        LeadService.auto_assign_lead(lead_with_items)
        lead_with_items.refresh_from_db()
        assert lead_with_items.assigned_salesperson == sales_admin

    def test_no_salespersons_leaves_unassigned(self, lead_with_items):
        LeadService.auto_assign_lead(lead_with_items)
        lead_with_items.refresh_from_db()
        assert lead_with_items.assigned_salesperson is None

    def test_assigns_to_least_loaded(self, lead_with_items, brand, customer):
        role = AdminRole.objects.get(name=AdminRole.RoleChoices.SALESPERSON)
        free_sp = Admin.objects.create(admin_code="ADM-FREE")
        free_sp.roles.add(role)
        free_sp.brands.add(brand)
        busy_sp = Admin.objects.create(admin_code="ADM-BUSY")
        busy_sp.roles.add(role)
        busy_sp.brands.add(brand)
        Lead.objects.create(
            customer=customer,
            brand=brand,
            assigned_salesperson=busy_sp,
            status=Lead.StatusChoices.NEW,
            expires_at=timezone.now() + timedelta(days=7),
        )
        LeadService.auto_assign_lead(lead_with_items)
        lead_with_items.refresh_from_db()
        assert lead_with_items.assigned_salesperson == free_sp


class TestConvertLeadToOrder:
    def test_converts_contacted_lead_to_order(self, lead_with_items, sales_admin):
        lead_with_items.status = Lead.StatusChoices.CONTACTED
        lead_with_items.save()
        order = LeadService.convert_lead_to_order(lead_with_items, sales_admin)
        assert order is not None
        assert Order.objects.filter(order_id=order.order_id).exists()
        lead_with_items.refresh_from_db()
        assert lead_with_items.status == Lead.StatusChoices.CONVERTED
        assert lead_with_items.order == order

    def test_raises_on_non_contacted_lead(self, lead_with_items, sales_admin):
        with pytest.raises(ValueError, match="CONTACTED"):
            LeadService.convert_lead_to_order(lead_with_items, sales_admin)

    def test_creates_order_items(self, lead_with_items, sales_admin, available_unit):
        lead_with_items.status = Lead.StatusChoices.CONTACTED
        lead_with_items.save()
        order = LeadService.convert_lead_to_order(lead_with_items, sales_admin)
        assert order.order_items.count() == 1
        assert order.order_items.first().inventory_unit == available_unit

    def test_transitions_units_to_pending_payment(self, lead_with_items, sales_admin, available_unit):
        lead_with_items.status = Lead.StatusChoices.CONTACTED
        lead_with_items.save()
        LeadService.convert_lead_to_order(lead_with_items, sales_admin)
        available_unit.refresh_from_db()
        assert available_unit.sale_status == InventoryUnit.SaleStatusChoices.PENDING_PAYMENT

    def test_creates_order_with_correct_values(self, lead_with_items, sales_admin):
        lead_with_items.status = Lead.StatusChoices.CONTACTED
        lead_with_items.save()
        order = LeadService.convert_lead_to_order(lead_with_items, sales_admin)
        assert order.total_amount == Decimal("15000.00")
        assert order.customer == lead_with_items.customer
