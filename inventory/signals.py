"""
Signal handlers for inventory management system.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta
from .models import (
    ReservationRequest, ReturnRequest, UnitTransfer, Notification,
    InventoryUnit, Admin, User, Order, AuditLog
)


@receiver(post_save, sender=ReservationRequest)
def handle_reservation_approval(sender, instance, created, **kwargs):
    """
    Handle notifications when reservation request is approved.
    Note: Status transitions are handled in the ViewSet perform_update method.
    """
    if not created and instance.status == ReservationRequest.StatusChoices.APPROVED:
        # Notifications are created in ViewSet, but we can add additional logic here if needed
        pass


@receiver(post_save, sender=Order)
def handle_order_creation(sender, instance, created, **kwargs):
    """Create notification when order is created."""
    if created:
        # Convert order_id (UUID) to string for object_id field (PositiveIntegerField)
        # Since Order uses UUID as primary key, we can't store it in PositiveIntegerField
        # Store None for object_id and include order_id in the message instead
        order_id_str = str(instance.order_id)
        item_count = instance.order_items.count()
        
        # Notify inventory manager and superuser
        inventory_managers = Admin.objects.filter(
            roles__name='IM'
        ).select_related('user')
        
        for manager in inventory_managers:
            Notification.objects.create(
                recipient=manager.user,
                notification_type=Notification.NotificationType.ORDER_CREATED,
                title="New Order Created",
                message=f"Order #{order_id_str} has been created with {item_count} item(s).",
                content_type=ContentType.objects.get_for_model(Order),
                object_id=None  # Can't store UUID in PositiveIntegerField
            )
        
        # Notify superusers
        superusers = User.objects.filter(is_superuser=True)
        for superuser in superusers:
            Notification.objects.create(
                recipient=superuser,
                notification_type=Notification.NotificationType.ORDER_CREATED,
                title="New Order Created",
                message=f"Order #{order_id_str} has been created with {item_count} item(s).",
                content_type=ContentType.objects.get_for_model(Order),
                object_id=None  # Can't store UUID in PositiveIntegerField
            )


# ============================================
# AUDIT LOGGING SIGNALS
# ============================================

@receiver(post_save, sender=InventoryUnit)
def audit_log_inventory_unit(sender, instance, created, **kwargs):
    """Log inventory unit changes (create, price/status changes)."""
    if created:
        # Log creation
        AuditLog.objects.create(
            user=instance.created_by if hasattr(instance, 'created_by') else None,
            action=AuditLog.ActionType.CREATE,
            model_name='InventoryUnit',
            object_id=instance.pk,
            object_repr=str(instance),
            new_value={
                'serial_number': instance.serial_number,
                'selling_price': str(instance.selling_price) if instance.selling_price else None,
                'sale_status': instance.sale_status,
                'condition': instance.condition,
            },
            content_type=ContentType.objects.get_for_model(InventoryUnit),
        )
    else:
        # Log updates (price or status changes)
        old_instance = InventoryUnit.objects.filter(pk=instance.pk).first()
        if old_instance:
            changes = {}
            old_data = {}
            new_data = {}
            
            if old_instance.selling_price != instance.selling_price:
                changes['selling_price'] = True
                old_data['selling_price'] = str(old_instance.selling_price) if old_instance.selling_price else None
                new_data['selling_price'] = str(instance.selling_price) if instance.selling_price else None
            
            if old_instance.sale_status != instance.sale_status:
                changes['sale_status'] = True
                old_data['sale_status'] = old_instance.sale_status
                new_data['sale_status'] = instance.sale_status
            
            if changes:
                action = AuditLog.ActionType.PRICE_CHANGE if 'selling_price' in changes else AuditLog.ActionType.STATUS_CHANGE
                if len(changes) > 1:
                    action = AuditLog.ActionType.UPDATE
                
                AuditLog.objects.create(
                    user=instance.updated_by if hasattr(instance, 'updated_by') else None,
                    action=action,
                    model_name='InventoryUnit',
                    object_id=instance.pk,
                    object_repr=str(instance),
                    old_value=old_data,
                    new_value=new_data,
                    content_type=ContentType.objects.get_for_model(InventoryUnit),
                )


@receiver(post_save, sender=ReservationRequest)
def audit_log_reservation_request(sender, instance, created, **kwargs):
    """Log reservation request approvals/rejections."""
    if not created and instance.status in [ReservationRequest.StatusChoices.APPROVED, ReservationRequest.StatusChoices.REJECTED]:
        action = AuditLog.ActionType.APPROVE if instance.status == ReservationRequest.StatusChoices.APPROVED else AuditLog.ActionType.REJECT
        
        approved_by_user = None
        if instance.approved_by:
            approved_by_user = instance.approved_by.user if hasattr(instance.approved_by, "user") else instance.approved_by

        AuditLog.objects.create(
            user=approved_by_user,
            action=action,
            model_name='ReservationRequest',
            object_id=instance.pk,
            object_repr=str(instance),
            new_value={
                'status': instance.status,
                'notes': instance.notes,
            },
            content_type=ContentType.objects.get_for_model(ReservationRequest),
        )


@receiver(post_save, sender=ReturnRequest)
def audit_log_return_request(sender, instance, created, **kwargs):
    """Log return request approvals/rejections."""
    if not created and instance.status in [ReturnRequest.StatusChoices.APPROVED, ReturnRequest.StatusChoices.REJECTED]:
        action = AuditLog.ActionType.APPROVE if instance.status == ReturnRequest.StatusChoices.APPROVED else AuditLog.ActionType.REJECT
        
        approved_by_user = None
        if instance.approved_by:
            approved_by_user = instance.approved_by.user if hasattr(instance.approved_by, "user") else instance.approved_by

        AuditLog.objects.create(
            user=approved_by_user,
            action=action,
            model_name='ReturnRequest',
            object_id=instance.pk,
            object_repr=str(instance),
            new_value={
                'status': instance.status,
                'notes': instance.notes,
            },
            content_type=ContentType.objects.get_for_model(ReturnRequest),
        )


@receiver(post_save, sender=UnitTransfer)
def audit_log_unit_transfer(sender, instance, created, **kwargs):
    """Log unit transfer approvals/rejections."""
    if not created and instance.status in [UnitTransfer.StatusChoices.APPROVED, UnitTransfer.StatusChoices.REJECTED]:
        action = AuditLog.ActionType.APPROVE if instance.status == UnitTransfer.StatusChoices.APPROVED else AuditLog.ActionType.REJECT
        
        AuditLog.objects.create(
            user=instance.approved_by,
            action=action,
            model_name='UnitTransfer',
            object_id=instance.pk,
            object_repr=str(instance),
            new_value={
                'status': instance.status,
                'from_salesperson': instance.from_salesperson.user.username if instance.from_salesperson else None,
                'to_salesperson': instance.to_salesperson.user.username if instance.to_salesperson else None,
            },
            content_type=ContentType.objects.get_for_model(UnitTransfer),
        )

