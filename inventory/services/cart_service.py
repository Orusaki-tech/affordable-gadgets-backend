"""Cart service for managing shopping carts."""

import uuid
from decimal import Decimal

from django.utils import timezone

from inventory.models import Bundle, Cart, CartItem, InventoryUnit, ObservabilityEvent
from inventory.services.customer_service import CustomerService


class CartService:
    @staticmethod
    def clear_open_carts_for_order(order) -> int:
        """
        Delete open (unsubmitted) carts for a fully paid order's customer/brand.

        Prefer the authenticated customer cart; phone match only clears carts that
        belong to the same customer or have no customer yet (guest carts). Never
        clears carts from another brand.
        """
        from django.db.models import Q

        brand = getattr(order, "brand", None)
        customer = getattr(order, "customer", None)
        phone = ""
        if customer is not None:
            phone = (getattr(customer, "phone", None) or "").strip()
        if not phone:
            phone = (getattr(order, "customer_phone", None) or "").strip()

        qs = Cart.objects.filter(is_submitted=False)
        if brand is not None:
            qs = qs.filter(brand=brand)

        cart_ids: set[int] = set()
        if customer is not None:
            cart_ids.update(qs.filter(customer=customer).values_list("id", flat=True))
        if phone:
            phone_q = Q(customer_phone=phone) & (
                Q(customer__isnull=True) | Q(customer=customer)
            )
            cart_ids.update(qs.filter(phone_q).values_list("id", flat=True))

        if not cart_ids:
            return 0
        Cart.objects.filter(id__in=cart_ids).delete()
        return len(cart_ids)

    @staticmethod
    def _validate_unit_for_cart(cart, inventory_unit):
        """Ensure inventory unit is available and allowed for cart's brand."""
        if inventory_unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
            raise ValueError(f"Unit {inventory_unit.id} is not available")
        if not inventory_unit.available_online:
            raise ValueError(f"Unit {inventory_unit.id} is not available for online purchase")

        product = inventory_unit.product_template
        unit_has_company_brands = inventory_unit.brands.exists()
        product_has_company_brands = product.brands.exists()

        if unit_has_company_brands:
            if cart.brand not in inventory_unit.brands.all():
                if not product.is_global and cart.brand not in product.brands.all():
                    raise ValueError("Unit not available for this company brand")
        else:
            if product_has_company_brands:
                if cart.brand not in product.brands.all():
                    raise ValueError("Unit not available for this company brand")

    @staticmethod
    def get_or_create_cart_for_customer(customer, brand):
        """Get or create the active cart for a logged-in customer."""
        if not brand:
            raise ValueError("Brand is required")
        if not customer:
            raise ValueError("Customer is required")

        active_carts = Cart.objects.filter(
            customer=customer, brand=brand, is_submitted=False
        ).order_by("-updated_at")
        cart = active_carts.first()

        if active_carts.count() > 1:
            active_carts.exclude(pk=cart.pk).delete()

        if not cart:
            cart = Cart.objects.create(
                customer=customer,
                brand=brand,
                customer_email=customer.email or "",
                customer_phone=customer.phone or "",
            )
            from inventory.observability import CARTS_TOTAL

            try:
                CARTS_TOTAL.labels(brand=brand.code if brand else "unknown", status="total").inc()
            except Exception:
                pass

        if cart.is_expired():
            cart.delete()
            return CartService.get_or_create_cart_for_customer(customer, brand)

        return cart

    @staticmethod
    def get_or_create_cart(session_key=None, customer_phone=None, brand=None):
        """Get existing cart or create new one."""
        if not brand:
            raise ValueError("Brand is required")

        cart = None

        # Try to find by customer phone first
        if customer_phone:
            cart = Cart.objects.filter(
                customer_phone=customer_phone, brand=brand, is_submitted=False
            ).first()

        # Try to find by session key
        if not cart and session_key:
            cart = Cart.objects.filter(
                session_key=session_key, brand=brand, is_submitted=False
            ).first()

        # Create new cart if not found
        if not cart:
            cart = Cart.objects.create(
                session_key=session_key or "", customer_phone=customer_phone or "", brand=brand
            )
            from inventory.observability import CARTS_TOTAL

            try:
                CARTS_TOTAL.labels(brand=brand.code if brand else "unknown", status="total").inc()
            except Exception:
                pass

        # Clean up expired cart
        if cart.is_expired():
            cart.delete()
            return CartService.get_or_create_cart(session_key, customer_phone, brand)

        return cart

    @staticmethod
    def resolve_unit_price(inventory_unit, brand=None, promotion_id=None, promotion=None):
        """Server-authoritative unit price (list or active promotion). Never trusts the client."""
        list_price = Decimal(str(inventory_unit.selling_price))
        product = inventory_unit.product_template
        promo = promotion

        if promo is None and promotion_id is not None:
            from inventory.models import Promotion

            promo_qs = Promotion.objects.filter(id=promotion_id, is_active=True)
            if brand is not None:
                promo_qs = promo_qs.filter(brand=brand)
            promo = promo_qs.first()

        if promo is None:
            return list_price, None

        now = timezone.now()
        if not (promo.start_date <= now <= promo.end_date):
            return list_price, None

        is_eligible = False
        if promo.products.exists() and product in promo.products.all():
            is_eligible = True
        elif promo.product_types and product.product_type == promo.product_types:
            is_eligible = True
        elif promo.featured_product_id == product.id:
            is_eligible = True

        if not is_eligible:
            return list_price, None

        final_price = list_price
        if (
            promo.featured_product_id == product.id
            and promo.featured_sale_price is not None
        ):
            final_price = Decimal(str(promo.featured_sale_price))
        elif promo.discount_percentage:
            discount = (list_price * Decimal(str(promo.discount_percentage))) / Decimal("100")
            final_price = max(Decimal("0.00"), list_price - discount)
        elif promo.discount_amount:
            final_price = max(
                Decimal("0.00"),
                list_price - Decimal(str(promo.discount_amount)),
            )

        return final_price, promo

    @staticmethod
    def trusted_cart_item_unit_price(cart_item):
        """Price for checkout from a cart line — recompute promos; trust server-set bundle prices."""
        inventory_unit = cart_item.inventory_unit
        list_price = Decimal(str(inventory_unit.selling_price))

        if cart_item.bundle_id:
            price = Decimal(str(cart_item.get_unit_price()))
            # Bundle lines are written by CartService.add_bundle_to_cart; reject negatives only.
            return price if price >= 0 else list_price

        if cart_item.promotion_id:
            brand = getattr(cart_item.cart, "brand", None)
            price, _ = CartService.resolve_unit_price(
                inventory_unit,
                brand=brand,
                promotion_id=cart_item.promotion_id,
            )
            return price

        # No promo/bundle: ignore any stored unit_price (may have been client-tampered).
        return list_price

    @staticmethod
    def add_item_to_cart(
        cart, inventory_unit, quantity=1, promotion_id=None, unit_price=None, ip_address=None
    ):
        """Add item to cart (no reservation, just tracking)."""
        CartService._validate_unit_for_cart(cart, inventory_unit)
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

        # Pricing is server-authoritative. `unit_price` from the client is ignored so
        # checkout cannot be undercut via crafted cart/order payloads.
        final_price, promotion = CartService.resolve_unit_price(
            inventory_unit,
            brand=cart.brand,
            promotion_id=promotion_id,
        )
        _ = unit_price  # kept for API compatibility; intentionally unused

        # Create or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            inventory_unit=inventory_unit,
            defaults={"quantity": quantity, "unit_price": final_price, "promotion": promotion},
        )

        if not created:
            cart_item.quantity += quantity
            cart_item.unit_price = final_price  # Update price in case promotion changed
            cart_item.promotion = promotion
            cart_item.save()

        CartService._record_cart_add_event(
            cart,
            product,
            inventory_unit,
            quantity,
            ip_address=ip_address,
            send_notification=created,
        )

        return cart_item

    @staticmethod
    def _resolve_cart_user_id(cart):
        if not cart.customer_id:
            return None
        from inventory.models import Customer

        return (
            Customer.objects.filter(pk=cart.customer_id)
            .values_list("user_id", flat=True)
            .first()
        )

    @staticmethod
    def _record_cart_add_event(
        cart, product, inventory_unit, quantity, ip_address=None, *, send_notification=True
    ):
        """Record cart_add observability event and backfill orphaned session events."""
        cart_user_id = CartService._resolve_cart_user_id(cart)
        session_key = cart.session_key or ""
        ObservabilityEvent.objects.create(
            user_id=cart_user_id,
            session_key=session_key,
            event_type=ObservabilityEvent.EventType.CART_ADD,
            product_id=product.id,
            brand_code=getattr(cart.brand, "code", "AFFORDABLE_GADGETS"),
            metadata={"quantity": quantity, "inventory_unit_id": inventory_unit.id},
            ip_address=ip_address or None,
        )
        if cart_user_id and session_key:
            ObservabilityEvent.objects.filter(
                session_key=session_key,
                event_type=ObservabilityEvent.EventType.CART_ADD,
                user__isnull=True,
            ).update(user_id=cart_user_id)

        if not send_notification:
            return

        from inventory.services.whatsapp_lead_service import notify_cart_add

        notify_cart_add(
            cart=cart,
            product=product,
            quantity=quantity,
            inventory_unit_id=inventory_unit.id,
        )

    @staticmethod
    def add_bundle_to_cart(cart, bundle, main_inventory_unit_id=None, bundle_item_ids=None):
        """Add a bundle to cart by creating grouped CartItems."""
        if bundle.brand_id != cart.brand_id:
            raise ValueError("Bundle not available for this brand")
        if not bundle.is_currently_active:
            raise ValueError("Bundle is not active")

        group_id = uuid.uuid4()
        items_queryset = bundle.items.all().select_related("product")
        if bundle_item_ids:
            items_queryset = items_queryset.filter(id__in=bundle_item_ids)
        items = list(items_queryset)
        if not items:
            raise ValueError("Bundle has no items")

        # Build base item prices
        item_prices = []
        selected_units = []
        for item in items:
            unit = None
            if item.product_id == bundle.main_product_id and main_inventory_unit_id:
                unit = InventoryUnit.objects.filter(
                    id=main_inventory_unit_id,
                    product_template=item.product,
                    sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                    available_online=True,
                ).first()
            if unit is None:
                unit = (
                    InventoryUnit.objects.filter(
                        product_template=item.product,
                        sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                        available_online=True,
                    )
                    .order_by("id")
                    .first()
                )
            if unit is None:
                raise ValueError(f"No available unit for {item.product.product_name}")
            CartService._validate_unit_for_cart(cart, unit)
            selected_units.append((item, unit))
            base_price = (
                Decimal(str(item.override_price))
                if item.override_price is not None
                else unit.selling_price
            )
            item_prices.append(base_price * item.quantity)

        items_total = sum(item_prices, Decimal("0.00"))
        if items_total <= 0:
            raise ValueError("Bundle total cannot be zero")

        # Determine target total based on pricing mode
        if bundle.pricing_mode == Bundle.PricingMode.FIXED and bundle.bundle_price is not None:
            target_total = Decimal(str(bundle.bundle_price))
        elif (
            bundle.pricing_mode == Bundle.PricingMode.PERCENT
            and bundle.discount_percentage is not None
        ):
            discount = (items_total * Decimal(str(bundle.discount_percentage))) / Decimal("100")
            target_total = max(Decimal("0.00"), items_total - discount)
        elif (
            bundle.pricing_mode == Bundle.PricingMode.AMOUNT and bundle.discount_amount is not None
        ):
            target_total = max(Decimal("0.00"), items_total - Decimal(str(bundle.discount_amount)))
        else:
            target_total = items_total

        # Distribute bundle total proportionally to items
        factor = (target_total / items_total) if items_total > 0 else Decimal("1")
        remaining = target_total
        created_items = []
        for index, (item, unit) in enumerate(selected_units):
            base_price = (
                Decimal(str(item.override_price))
                if item.override_price is not None
                else unit.selling_price
            )
            if index == len(selected_units) - 1:
                unit_price = remaining / Decimal(item.quantity)
            else:
                unit_price = (base_price * factor).quantize(Decimal("0.01"))
                remaining -= unit_price * item.quantity
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                inventory_unit=unit,
                defaults={
                    "quantity": item.quantity,
                    "unit_price": unit_price,
                    "bundle": bundle,
                    "bundle_group_id": group_id,
                },
            )
            if not created:
                cart_item.quantity += item.quantity
                cart_item.unit_price = unit_price
                cart_item.bundle = bundle
                cart_item.bundle_group_id = group_id
                cart_item.save()
            CartService._record_cart_add_event(
                cart,
                item.product,
                unit,
                item.quantity,
                ip_address=None,
                send_notification=False,
            )
            created_items.append(cart_item)

        if created_items:
            first_item, first_unit = selected_units[0]
            from inventory.services.whatsapp_lead_service import notify_cart_add

            notify_cart_add(
                cart=cart,
                product=first_item.product,
                quantity=sum(ci.quantity for ci in created_items),
                inventory_unit_id=first_unit.id,
            )

        return created_items, group_id

    @staticmethod
    def checkout_cart(
        cart,
        customer_name,
        customer_phone,
        customer_email=None,
        delivery_address=None,
        delivery_county=None,
        delivery_ward=None,
        delivery_fee=None,
        delivery_window_start=None,
        delivery_window_end=None,
        delivery_notes=None,
    ):
        """Convert cart to Lead."""
        from django.db import transaction

        from inventory.models import Lead, LeadItem

        if cart.is_submitted:
            raise ValueError("Cart already submitted")

        with transaction.atomic():
            # Get or create customer
            customer, _ = CustomerService.get_or_create_customer(
                customer_name, customer_phone, customer_email, delivery_address
            )

            # Update cart with contact info
            cart.customer_name = customer_name
            cart.customer_phone = customer_phone
            # Explicitly convert empty strings to None for nullable fields
            cart.customer_email = (
                customer_email if customer_email and customer_email.strip() else None
            )
            cart.delivery_address = (
                delivery_address if delivery_address and delivery_address.strip() else None
            )
            cart.customer = customer
            cart.delivery_county = delivery_county or ""
            cart.delivery_ward = delivery_ward or ""
            cart.delivery_fee = delivery_fee or Decimal("0.00")
            cart.delivery_window_start = delivery_window_start
            cart.delivery_window_end = delivery_window_end
            cart.delivery_notes = delivery_notes or ""
            cart.is_submitted = True

            # Calculate total value using trusted (server-derived) prices
            total_value = Decimal("0.00")
            for item in cart.items.all():
                unit_price = CartService.trusted_cart_item_unit_price(item)
                total_value += unit_price * item.quantity

            # Create Lead
            lead = Lead.objects.create(
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
                delivery_address=delivery_address,
                delivery_county=delivery_county or "",
                delivery_ward=delivery_ward or "",
                delivery_fee=cart.delivery_fee,
                delivery_window_start=delivery_window_start,
                delivery_window_end=delivery_window_end,
                delivery_notes=delivery_notes or "",
                customer=customer,
                brand=cart.brand,
                total_value=total_value + (cart.delivery_fee or Decimal("0.00")),
                status=Lead.StatusChoices.NEW,
            )

            # Track lead creation
            try:
                from inventory.observability import LEADS_CREATED

                LEADS_CREATED.labels(brand=cart.brand.code if cart.brand else "unknown").inc()
            except Exception:
                pass

            # Create LeadItems with trusted prices
            for cart_item in cart.items.all():
                unit_price = CartService.trusted_cart_item_unit_price(cart_item)
                LeadItem.objects.create(
                    lead=lead,
                    inventory_unit=cart_item.inventory_unit,
                    quantity=cart_item.quantity,
                    unit_price=unit_price,
                    bundle=cart_item.bundle,
                    bundle_group_id=cart_item.bundle_group_id,
                )

            # Link cart to lead
            cart.lead = lead
            cart.save()

            # Track cart→lead conversion
            from inventory.observability import CARTS_TOTAL

            try:
                CARTS_TOTAL.labels(
                    brand=cart.brand.code if cart.brand else "unknown", status="submitted"
                ).inc()
            except Exception:
                pass

            # Notify all salespersons associated with this brand
            from django.contrib.contenttypes.models import ContentType

            from inventory.models import Admin, AdminRole, Notification

            salespersons = (
                Admin.objects.filter(
                    roles__name=AdminRole.RoleChoices.SALESPERSON,
                    brands=cart.brand,  # Only salespersons for this company brand
                )
                .distinct()
                .select_related("user")
            )

            # Format currency for notification message
            total_value_str = f"KES {total_value:,.2f}"

            for salesperson in salespersons:
                Notification.objects.create(
                    recipient=salesperson.user,
                    notification_type=Notification.NotificationType.NEW_LEAD,
                    title="New Lead Available",
                    message=f"New lead {lead.lead_reference} from {customer_name} - Total: {total_value_str}",
                    content_type=ContentType.objects.get_for_model(Lead),
                    object_id=lead.id,
                )

            # Don't auto-assign - let salespersons claim leads
            # LeadService.auto_assign_lead(lead)  # Removed auto-assignment

            return lead
