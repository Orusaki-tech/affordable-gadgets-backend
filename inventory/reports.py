"""
Report generation functions for inventory management.
"""
from django.db.models import Sum, Count, Avg, F, Q, DecimalField, ExpressionWrapper, Case, When
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import InventoryUnit, Product, ReservationRequest, ReturnRequest, UnitTransfer


def get_inventory_value_report():
    """
    Calculate total inventory value by product and overall.
    Returns: {
        'total_value': Decimal,
        'available_value': Decimal,
        'by_product': [{...}, ...],
        'by_status': [{...}, ...]
    }
    """
    # Total value of all units
    total_value = InventoryUnit.objects.aggregate(
        total=Sum('selling_price')
    )['total'] or Decimal('0')
    
    # Value of available units only
    available_value = InventoryUnit.objects.filter(
        sale_status='AV'
    ).aggregate(
        total=Sum('selling_price')
    )['total'] or Decimal('0')
    
    # Value by product
    by_product = InventoryUnit.objects.values(
        'product_template__id',
        'product_template__product_name'
    ).annotate(
        unit_count=Count('id'),
        available_count=Count('id', filter=Q(sale_status='AV')),
        total_value=Sum('selling_price'),
        avg_price=Avg('selling_price')
    ).order_by('-total_value')
    
    # Value by status
    by_status = InventoryUnit.objects.values('sale_status').annotate(
        unit_count=Count('id'),
        total_value=Sum('selling_price')
    ).order_by('-total_value')
    
    return {
        'total_value': total_value,
        'available_value': available_value,
        'by_product': list(by_product),
        'by_status': list(by_status),
    }


def get_stock_movement_report(days=30):
    """
    Track stock movements over time (units added/sold).
    
    Args:
        days: Number of days to look back
    
    Returns: {
        'summary': {...},
        'daily_movement': [{...}, ...]
    }
    """
    start_date = timezone.now() - timedelta(days=days)
    
    # Units sourced in period
    units_sourced = InventoryUnit.objects.filter(
        date_sourced__gte=start_date
    ).count()
    
    # Units sold in period (approximated by status change)
    units_sold = InventoryUnit.objects.filter(
        sale_status='SD',
        updated_at__gte=start_date
    ).count()
    
    # Daily breakdown
    daily_sourced = InventoryUnit.objects.filter(
        date_sourced__gte=start_date
    ).annotate(
        date=TruncDate('date_sourced')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # This is simplified - in production, you'd track actual sale dates
    daily_sold = InventoryUnit.objects.filter(
        sale_status='SD',
        updated_at__gte=start_date
    ).annotate(
        date=TruncDate('updated_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    return {
        'summary': {
            'units_sourced': units_sourced,
            'units_sold': units_sold,
            'net_change': units_sourced - units_sold,
        },
        'daily_sourced': list(daily_sourced),
        'daily_sold': list(daily_sold),
    }


def get_product_performance():
    """
    Analyze product performance (sales velocity, profitability).
    
    Returns: [{
        'product_id': int,
        'product_name': str,
        'total_units': int,
        'available_units': int,
        'sold_units': int,
        'sell_through_rate': float,
        'avg_selling_price': Decimal,
        'total_revenue': Decimal,
    }, ...]
    """
    performance = Product.objects.annotate(
        total_units=Count('inventoryunit'),
        available_units=Count('inventoryunit', filter=Q(inventoryunit__sale_status='AV')),
        sold_units=Count('inventoryunit', filter=Q(inventoryunit__sale_status='SD')),
        reserved_units=Count('inventoryunit', filter=Q(inventoryunit__sale_status='RS')),
        avg_selling_price=Avg('inventoryunit__selling_price'),
        total_revenue=Sum(
            'inventoryunit__selling_price',
            filter=Q(inventoryunit__sale_status='SD')
        )
    ).annotate(
        sell_through_rate=Case(
            When(total_units=0, then=Decimal('0.00')),
            default=ExpressionWrapper(
                F('sold_units') * 100.0 / F('total_units'),
                output_field=DecimalField(max_digits=5, decimal_places=2)
            ),
            output_field=DecimalField(max_digits=5, decimal_places=2)
        )
    ).values(
        'id',
        'product_name',
        'total_units',
        'available_units',
        'sold_units',
        'reserved_units',
        'sell_through_rate',
        'avg_selling_price',
        'total_revenue'
    ).order_by('-sold_units')
    
    return list(performance)


def get_aging_inventory(days_threshold=30):
    """
    Find units that haven't sold after X days.
    
    Args:
        days_threshold: Number of days to consider "aging"
    
    Returns: [{
        'unit_id': int,
        'product_name': str,
        'serial_number': str,
        'days_in_stock': int,
        'selling_price': Decimal,
        'condition': str,
    }, ...]
    """
    threshold_date = timezone.now() - timedelta(days=days_threshold)
    
    aging_units = InventoryUnit.objects.filter(
        date_sourced__lte=threshold_date,
        sale_status='AV'  # Still available
    ).annotate(
        days_in_stock=ExpressionWrapper(
            (timezone.now() - F('date_sourced')).total_seconds() / 86400,
            output_field=DecimalField(max_digits=10, decimal_places=0)
        )
    ).values(
        'id',
        'product_template__product_name',
        'serial_number',
        'selling_price',
        'condition',
        'days_in_stock'
    ).order_by('-days_in_stock')
    
    return list(aging_units)


def get_salesperson_performance(days=30):
    """
    Track salesperson performance (reservations, approvals, etc.).
    
    Args:
        days: Number of days to look back
    
    Returns: [{
        'salesperson_id': int,
        'salesperson_name': str,
        'reservations_requested': int,
        'reservations_approved': int,
        'approval_rate': float,
        'returns_requested': int,
        'transfers_requested': int,
    }, ...]
    """
    start_date = timezone.now() - timedelta(days=days)
    
    # Get all salesperson admins (role code = 'SP')
    from .models import Admin, AdminRole
    
    salesperson_role = AdminRole.objects.filter(role_code='SP').first()
    if not salesperson_role:
        return []
    
    salesperson_admins = Admin.objects.filter(roles=salesperson_role)
    
    performance = []
    for admin in salesperson_admins:
        # Count reservations
        reservations_requested = ReservationRequest.objects.filter(
            requesting_salesperson=admin,
            requested_at__gte=start_date
        ).count()
        
        reservations_approved = ReservationRequest.objects.filter(
            requesting_salesperson=admin,
            requested_at__gte=start_date,
            status='AP'
        ).count()
        
        approval_rate = (reservations_approved / reservations_requested * 100) if reservations_requested > 0 else 0
        
        # Count returns
        returns_requested = ReturnRequest.objects.filter(
            requested_by=admin,
            requested_at__gte=start_date
        ).count()
        
        # Count transfers
        transfers_requested = UnitTransfer.objects.filter(
            Q(from_salesperson=admin) | Q(to_salesperson=admin),
            requested_at__gte=start_date
        ).count()
        
        performance.append({
            'salesperson_id': admin.id,
            'salesperson_name': admin.user.get_full_name() or admin.user.username,
            'salesperson_email': admin.user.email,
            'reservations_requested': reservations_requested,
            'reservations_approved': reservations_approved,
            'approval_rate': round(approval_rate, 2),
            'returns_requested': returns_requested,
            'transfers_requested': transfers_requested,
        })
    
    return sorted(performance, key=lambda x: x['reservations_approved'], reverse=True)


def get_request_management_stats(days=30):
    """
    Get statistics for request management (pending, approved, rejected).
    
    Args:
        days: Number of days to look back
    
    Returns: {
        'reservations': {...},
        'returns': {...},
        'transfers': {...}
    }
    """
    start_date = timezone.now() - timedelta(days=days)
    
    # Reservation stats
    reservation_stats = ReservationRequest.objects.filter(
        requested_at__gte=start_date
    ).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PE')),
        approved=Count('id', filter=Q(status='AP')),
        rejected=Count('id', filter=Q(status='RE')),
        expired=Count('id', filter=Q(status='EX'))
    )
    
    # Return stats
    return_stats = ReturnRequest.objects.filter(
        requested_at__gte=start_date
    ).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PE')),
        approved=Count('id', filter=Q(status='AP')),
        rejected=Count('id', filter=Q(status='RE'))
    )
    
    # Transfer stats
    transfer_stats = UnitTransfer.objects.filter(
        requested_at__gte=start_date
    ).aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='PE')),
        approved=Count('id', filter=Q(status='AP')),
        rejected=Count('id', filter=Q(status='RE'))
    )
    
    return {
        'reservations': reservation_stats,
        'returns': return_stats,
        'transfers': transfer_stats,
    }

