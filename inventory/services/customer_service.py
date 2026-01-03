"""Customer service for customer recognition and management."""
from django.utils import timezone
from inventory.models import Customer


class CustomerService:
    @staticmethod
    def recognize_customer(phone, brand=None):
        """Find existing customer by phone, return customer and welcome message."""
        try:
            # Use filter().first() instead of get() to handle potential duplicates gracefully
            customer = Customer.objects.filter(phone=phone).first()
            
            if not customer:
                return {
                    'customer': None,
                    'is_returning_customer': False,
                    'is_returning': False,
                    'message': None
                }
            
            # Update last_lead_at if the field exists
            try:
                customer.last_lead_at = timezone.now()
                customer.save(update_fields=['last_lead_at'])
            except Exception:
                # If last_lead_at field doesn't exist or can't be updated, continue anyway
                pass
            
            # Return serialized customer data (not the model instance)
            return {
                'customer': {
                    'id': customer.id,
                    'name': customer.name or '',
                    'phone': customer.phone or '',
                    'email': customer.email or '',
                    'delivery_address': customer.delivery_address or '',
                },
                'is_returning_customer': True,  # Fixed: match frontend expectation
                'is_returning': True,  # Keep for backward compatibility
                'message': f"Welcome back, {customer.name or 'Customer'}!"
            }
        except Exception as e:
            # Log the error but return a safe response
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error in recognize_customer: {str(e)}', exc_info=True)
            
            # Return safe default response
            return {
                'customer': None,
                'is_returning_customer': False,
                'is_returning': False,
                'message': None
            }
    
    @staticmethod
    def get_or_create_customer(name, phone, email=None, delivery_address=None):
        """Get existing customer or create new one."""
        customer, created = Customer.objects.get_or_create(
            phone=phone,
            defaults={
                'name': name,
                'email': email,
                'delivery_address': delivery_address
            }
        )
        
        # Update fields if customer exists
        if not created:
            customer.name = name
            if email:
                customer.email = email
            if delivery_address:
                customer.delivery_address = delivery_address
            customer.save()
        
        return customer, created

