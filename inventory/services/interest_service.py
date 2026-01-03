"""Interest service for tracking lead interest in inventory units."""
from inventory.models import Lead, InventoryUnit, Product


class InterestService:
    @staticmethod
    def get_interest_count(inventory_unit):
        """Get number of active leads containing this unit."""
        active_statuses = [Lead.StatusChoices.NEW, Lead.StatusChoices.CONTACTED]
        from django.utils import timezone
        
        return Lead.objects.filter(
            items__inventory_unit=inventory_unit,
            status__in=active_statuses,
            expires_at__gt=timezone.now()  # Not expired
        ).distinct().count()
    
    @staticmethod
    def get_product_interest_count(product):
        """Get total interest count for all units of a product."""
        units = product.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        total_interest = 0
        for unit in units:
            total_interest += InterestService.get_interest_count(unit)
        return total_interest







