"""Cart service for managing shopping carts."""
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q
from inventory.models import Cart, CartItem, InventoryUnit, Brand
from inventory.services.customer_service import CustomerService
from inventory.services.lead_service import LeadService


class CartService:
    @staticmethod
    def get_or_create_cart(session_key=None, customer_phone=None, brand=None):
        """Get existing cart or create new one."""
        if not brand:
            raise ValueError("Brand is required")
        
        cart = None
        
        # Try to find by customer phone first
        if customer_phone:
            cart = Cart.objects.filter(
                customer_phone=customer_phone,
                brand=brand,
                is_submitted=False
            ).first()
        
        # Try to find by session key
        if not cart and session_key:
            cart = Cart.objects.filter(
                session_key=session_key,
                brand=brand,
                is_submitted=False
            ).first()
        
        # Create new cart if not found
        if not cart:
            cart = Cart.objects.create(
                session_key=session_key or '',
                customer_phone=customer_phone or '',
                brand=brand
            )
        
        # Clean up expired cart
        if cart.is_expired():
            cart.delete()
            return CartService.get_or_create_cart(session_key, customer_phone, brand)
        
        return cart
    
    @staticmethod
    def add_item_to_cart(cart, inventory_unit, quantity=1, promotion_id=None, unit_price=None):
        """Add item to cart (no reservation, just tracking)."""
        # Validate unit is available
        if inventory_unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
            raise ValueError(f"Unit {inventory_unit.id} is not available")
        
        if not inventory_unit.available_online:
            raise ValueError(f"Unit {inventory_unit.id} is not available for online purchase")
        
        # Check company brand availability
        product = inventory_unit.product_template
        unit_has_company_brands = inventory_unit.brands.exists()
        product_has_company_brands = product.brands.exists()
        
        # If unit has explicit company brand assignments, they take precedence
        if unit_has_company_brands:
            # Unit has company brands - cart's company brand must be in them
            if cart.brand not in inventory_unit.brands.all():
                # Unit has company brands but cart's company brand not in them
                # Check if product is global or assigned to cart's company brand
                if not product.is_global and cart.brand not in product.brands.all():
                    raise ValueError("Unit not available for this company brand")
        else:
            # Unit has no company brand assignment - check product level
            if product_has_company_brands:
                # Product has company brands - cart's company brand must be in them
                if cart.brand not in product.brands.all():
                    raise ValueError("Unit not available for this company brand")
            # If product has no company brands and is not global, allow it
            # (default behavior - available to all company brands)
        
        # Calculate promotion price if promotion is provided
        promotion = None
        final_price = inventory_unit.selling_price
        
        if promotion_id:
            try:
                from inventory.models import Promotion
                promotion = Promotion.objects.get(id=promotion_id, brand=cart.brand, is_active=True)
                now = timezone.now()
                
                # Check if promotion is currently active
                if promotion.start_date <= now <= promotion.end_date:
                    # Check if product is eligible
                    is_eligible = False
                    
                    if promotion.products.exists() and product in promotion.products.all():
                        is_eligible = True
                    elif promotion.product_types and product.product_type == promotion.product_types:
                        is_eligible = True
                    
                    if is_eligible:
                        # Calculate discounted price
                        if promotion.discount_percentage:
                            discount = (inventory_unit.selling_price * promotion.discount_percentage) / 100
                            final_price = max(Decimal('0.00'), inventory_unit.selling_price - discount)
                        elif promotion.discount_amount:
                            final_price = max(Decimal('0.00'), inventory_unit.selling_price - promotion.discount_amount)
            except Promotion.DoesNotExist:
                pass
        
        # Use provided unit_price if given (from frontend calculation)
        if unit_price is not None:
            final_price = Decimal(str(unit_price))
        
        # Create or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            inventory_unit=inventory_unit,
            defaults={
                'quantity': quantity,
                'unit_price': final_price,
                'promotion': promotion
            }
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.unit_price = final_price  # Update price in case promotion changed
            cart_item.promotion = promotion
            cart_item.save()
        
        return cart_item
    
    @staticmethod
    def checkout_cart(cart, customer_name, customer_phone, customer_email=None, delivery_address=None):
        """Convert cart to Lead."""
        from inventory.models import Lead, LeadItem
        from django.db import transaction
        
        if cart.is_submitted:
            raise ValueError("Cart already submitted")
        
        with transaction.atomic():
            # Get or create customer
            customer, _ = CustomerService.get_or_create_customer(
                customer_name,
                customer_phone,
                customer_email,
                delivery_address
            )
            
            # Update cart with contact info
            cart.customer_name = customer_name
            cart.customer_phone = customer_phone
            # Explicitly convert empty strings to None for nullable fields
            cart.customer_email = customer_email if customer_email and customer_email.strip() else None
            cart.delivery_address = delivery_address if delivery_address and delivery_address.strip() else None
            cart.customer = customer
            cart.is_submitted = True
            
            # Calculate total value using stored promotion prices
            total_value = Decimal('0.00')
            for item in cart.items.all():
                unit_price = item.get_unit_price()  # Use stored promotion price
                total_value += unit_price * item.quantity
            
            # Create Lead
            lead = Lead.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
                delivery_address=delivery_address,
                customer=customer,
                brand=cart.brand,
                total_value=total_value,
                status=Lead.StatusChoices.NEW
            )
            
            # Create LeadItems with stored promotion prices
            for cart_item in cart.items.all():
                unit_price = cart_item.get_unit_price()  # Use stored promotion price
                LeadItem.objects.create(
                    lead=lead,
                    inventory_unit=cart_item.inventory_unit,
                    quantity=cart_item.quantity,
                    unit_price=unit_price  # Store promotion price
                )
            
            # Link cart to lead
            cart.lead = lead
            cart.save()
            
            # Notify all salespersons associated with this brand
            from inventory.models import Notification, Admin, AdminRole
            from django.contrib.contenttypes.models import ContentType
            from django.utils import timezone
            
            salespersons = Admin.objects.filter(
                roles__name=AdminRole.RoleChoices.SALESPERSON,
                brands=cart.brand  # Only salespersons for this company brand
            ).distinct().select_related('user')
            
            # Format currency for notification message
            total_value_str = f"KES {total_value:,.2f}"
            
            for salesperson in salespersons:
                Notification.objects.create(
                    recipient=salesperson.user,
                    notification_type=Notification.NotificationType.NEW_LEAD,
                    title="New Lead Available",
                    message=f"New lead {lead.lead_reference} from {customer_name} - Total: {total_value_str}",
                    content_type=ContentType.objects.get_for_model(Lead),
                    object_id=lead.id
                )
            
            # Don't auto-assign - let salespersons claim leads
            # LeadService.auto_assign_lead(lead)  # Removed auto-assignment
            
            return lead

