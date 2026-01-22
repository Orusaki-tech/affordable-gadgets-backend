"""Lead service for managing leads and converting to orders."""
from django.utils import timezone
from django.db import transaction
from inventory.models import Lead, Admin, AdminRole, Order, OrderItem, InventoryUnit


class LeadService:
    @staticmethod
    def auto_assign_lead(lead):
        """Auto-assign lead to salesperson with least active leads."""
        # Get salespersons for this brand
        salespersons = Admin.objects.filter(
            roles__name=AdminRole.RoleChoices.SALESPERSON,
            brands=lead.brand
        ).distinct()
        
        if not salespersons.exists():
            # No salespersons assigned to brand, leave unassigned
            return
        
        # Find salesperson with least active leads
        min_leads = float('inf')
        assigned_salesperson = None
        
        for salesperson in salespersons:
            active_lead_count = Lead.objects.filter(
                assigned_salesperson=salesperson,
                status__in=[Lead.StatusChoices.NEW, Lead.StatusChoices.CONTACTED]
            ).count()
            
            if active_lead_count < min_leads:
                min_leads = active_lead_count
                assigned_salesperson = salesperson
        
        if assigned_salesperson:
            lead.assigned_salesperson = assigned_salesperson
            lead.save(update_fields=['assigned_salesperson'])
    
    @staticmethod
    def convert_lead_to_order(lead, salesperson):
        """Convert lead to order (one-click order creation)."""
        if lead.status != Lead.StatusChoices.CONTACTED:
            raise ValueError("Lead must be in CONTACTED status to convert")
        
        with transaction.atomic():
            # Create order (source_lead is set on Lead model, not Order)
            order = Order.objects.create(
                customer=lead.customer,
                user=lead.customer.user if lead.customer and lead.customer.user else None,
                brand=lead.brand,
                order_source=Order.OrderSourceChoices.ONLINE,
                status=Order.StatusChoices.PENDING,
                total_amount=lead.total_value
            )
            
            # Create order items and transition units to PENDING_PAYMENT
            for lead_item in lead.items.all():
                unit = lead_item.inventory_unit
                
                # Transition to PENDING_PAYMENT (will be SOLD when payment is confirmed)
                unit.sale_status = InventoryUnit.SaleStatusChoices.PENDING_PAYMENT
                unit.save()
                
                # Create order item
                OrderItem.objects.create(
                    order=order,
                    inventory_unit=unit,
                    quantity=lead_item.quantity,
                    unit_price_at_purchase=lead_item.unit_price,
                    bundle=lead_item.bundle,
                    bundle_group_id=lead_item.bundle_group_id
                )
            
            # Update lead - link to order (this creates the source_lead relationship)
            lead.status = Lead.StatusChoices.CONVERTED
            lead.converted_at = timezone.now()
            lead.order = order
            lead.save()
            
            # Clear the associated cart now that lead is converted to order
            # The cart has served its purpose - items are now in the order
            from inventory.models import Cart
            try:
                cart = Cart.objects.filter(lead=lead).first()
                if cart:
                    cart.delete()
                    print(f"Cart {cart.id} deleted after lead {lead.lead_reference} converted to order")
            except Exception as e:
                # Log but don't fail the conversion if cart deletion fails
                print(f"Warning: Could not delete cart for lead {lead.lead_reference}: {str(e)}")
            
            return order

