from rest_framework import permissions
from .models import Customer, Admin, AdminRole
import logging

logger = logging.getLogger(__name__)

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow Admins (staff users) to perform write operations,
    but allow read operations for everyone (including unauthenticated users).
    
    Applies well to: Product, Color, UnitAcquisitionSource, ProductAccessory.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to Admin users
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)

class IsContentCreatorOrInventoryManagerOrReadOnly(permissions.BasePermission):
    """
    Allow public read access, but restrict write access to Content Creators,
    Inventory Managers, or Superusers.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_content_creator or admin.is_inventory_manager

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow Admins (staff users) to perform any action.
    
    Applies well to: InventoryUnit, OrderItem.
    """
    def has_permission(self, request, view):
        # Only allow access if the user is authenticated and is a staff user
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )

class IsSuperuser(permissions.BasePermission):
    """
    Custom permission to only allow superusers to perform any action.
    
    Applies well to: AdminViewSet (admin management).
    """
    def has_permission(self, request, view):
        # Only allow access if the user is authenticated and is a superuser
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)

class IsCustomerOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow:
    1. Admins full access.
    2. Object owners (Customers) read/write access to their own profile.
    
    Applies well to: CustomerProfileView.
    """
    def has_permission(self, request, view):
        # Admins have full access
        if request.user.is_authenticated and request.user.is_staff:
            return True
        
        # Only allow authenticated users access beyond this point
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Admins have full access to any object
        if request.user.is_authenticated and request.user.is_staff:
            return True
        
        # Object must be a Customer instance, and the user must be linked to it
        if isinstance(obj, Customer):
            return obj.user == request.user
            
        return False # Deny all others

class IsReviewOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow:
    1. Admins full access (CRUD).
    2. Review owners (the user who created it) read/update/delete access.
    3. All authenticated users can create (POST).
    4. All users (even anonymous) can list/retrieve (GET).
    
    Applies well to: ReviewViewSet.
    """
    
    def has_permission(self, request, view):
        # Allow read methods (list, retrieve) for everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Allow creation (POST) only for authenticated users (Customers)
        if view.action == 'create':
            return request.user.is_authenticated
            
        # All other methods (PUT, PATCH, DELETE) require object-level check
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Admins have full control over all objects
        if request.user.is_authenticated and request.user.is_staff:
            return True
            
        # If the user is authenticated and not an admin, check if they own the object.
        # The Review model now links to 'customer', which links to 'user'.
        if obj.customer and obj.customer.user == request.user:
            return True
            
        # Deny all others
        return False


# -------------------------------------------------------------------------
# ROLE-BASED PERMISSIONS
# -------------------------------------------------------------------------

def get_admin_from_user(user):
    """Helper function to get Admin instance from User."""
    if not user or not user.is_authenticated or not user.is_staff:
        return None
    try:
        return Admin.objects.get(user=user)
    except Admin.DoesNotExist:
        return None


class HasRole(permissions.BasePermission):
    """Generic permission to check if user has a specific role."""
    
    def __init__(self, role_code):
        self.role_code = role_code
        super().__init__()
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superusers have all permissions
        if request.user.is_superuser:
            return True
        
        # Check if user is staff
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.has_role(self.role_code)


class IsSalesperson(permissions.BasePermission):
    """Permission to check if user has Salesperson role."""
    
    def has_permission(self, request, view):
        import json
        import os
        
        # Use PESAPAL_LOG_PATH from environment variable, fallback to /tmp/pesapal_debug.log
        from django.conf import settings
        log_path = getattr(settings, 'PESAPAL_LOG_PATH', '/tmp/pesapal_debug.log')
        
        #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'permissions.py:149',
                    'message': 'IsSalesperson.has_permission() ENTRY',
                    'data': {
                        'user_id': request.user.id if request.user and request.user.is_authenticated else None,
                        'username': request.user.username if request.user and request.user.is_authenticated else None,
                        'is_authenticated': request.user.is_authenticated if request.user else False,
                        'is_staff': request.user.is_staff if request.user and request.user.is_authenticated else False,
                        'is_superuser': request.user.is_superuser if request.user and request.user.is_authenticated else False,
                        'view_action': view.action if hasattr(view, 'action') else None
                    },
                    'timestamp': int(__import__('time').time() * 1000)
                }) + '\n')
        except: pass
        #endregion
        
        if not request.user or not request.user.is_authenticated:
            #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'permissions.py:151',
                        'message': 'IsSalesperson: User not authenticated',
                        'data': {},
                        'timestamp': int(__import__('time').time() * 1000)
                    }) + '\n')
            except: pass
            #endregion
            return False
        
        if request.user.is_superuser:
            #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'permissions.py:154',
                        'message': 'IsSalesperson: Superuser granted access',
                        'data': {'username': request.user.username},
                        'timestamp': int(__import__('time').time() * 1000)
                    }) + '\n')
            except: pass
            #endregion
            return True
        
        if not request.user.is_staff:
            #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'permissions.py:157',
                        'message': 'IsSalesperson: User is not staff',
                        'data': {'username': request.user.username},
                        'timestamp': int(__import__('time').time() * 1000)
                    }) + '\n')
            except: pass
            #endregion
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'permissions.py:160',
                        'message': 'IsSalesperson: No admin profile found',
                        'data': {'username': request.user.username},
                        'timestamp': int(__import__('time').time() * 1000)
                    }) + '\n')
            except: pass
            #endregion
            return False
        
        is_salesperson = admin.is_salesperson
        
        #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'permissions.py:163',
                    'message': 'IsSalesperson: Final check result',
                    'data': {
                        'admin_id': admin.id,
                        'admin_code': admin.admin_code,
                        'is_salesperson': is_salesperson,
                        'roles': list(admin.roles.values_list('name', flat=True)),
                        'permission_granted': is_salesperson
                    },
                    'timestamp': int(__import__('time').time() * 1000)
                }) + '\n')
        except: pass
        #endregion
        
        return is_salesperson


class IsInventoryManager(permissions.BasePermission):
    """Permission to check if user has Inventory Manager role."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_inventory_manager


class IsContentCreator(permissions.BasePermission):
    """Permission to check if user has Content Creator role."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_content_creator


class IsSalespersonOrInventoryManager(permissions.BasePermission):
    """Permission to check if user has Salesperson OR Inventory Manager role."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_salesperson or admin.is_inventory_manager


class CanReserveUnits(permissions.BasePermission):
    """Permission to check if user can reserve units (Salesperson or Inventory Manager)."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_salesperson or admin.is_inventory_manager


class CanApproveRequests(permissions.BasePermission):
    """Permission to check if user can approve requests (Inventory Manager or Superuser)."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"CanApproveRequests: User not authenticated")
            return False
        
        if request.user.is_superuser:
            logger.info(f"CanApproveRequests: Superuser {request.user.username} granted permission")
            return True
        
        if not request.user.is_staff:
            logger.warning(f"CanApproveRequests: User {request.user.username} is not staff")
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            logger.warning(f"CanApproveRequests: No Admin profile found for user {request.user.username}")
            return False
        
        is_im = admin.is_inventory_manager
        logger.info(f"CanApproveRequests.has_permission: User {request.user.username}, Admin {admin.admin_code}, is_inventory_manager={is_im}, roles={list(admin.roles.values_list('name', flat=True))}")
        return is_im
    
    def has_object_permission(self, request, view, obj):
        """Check object-level permission (same as has_permission for this use case)."""
        return self.has_permission(request, view)


class CanCreateReviews(permissions.BasePermission):
    """Permission to check if user can create reviews (Content Creator or Superuser)."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_content_creator


class IsMarketingManager(permissions.BasePermission):
    """Permission to check if user has Marketing Manager role."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_marketing_manager


class IsOrderManager(permissions.BasePermission):
    """Permission to check if user has Order Manager role."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_order_manager


class IsInventoryManagerOrMarketingManagerReadOnly(permissions.BasePermission):
    """
    Permission for Inventory Units:
    - Inventory Manager: Full access (read/write)
    - Marketing Manager: Read-only access
    - Salesperson: Read-only access
    - Superuser: Full access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        # Read access for marketing manager or salesperson, write access for inventory manager
        if request.method in permissions.SAFE_METHODS:
            return admin.is_marketing_manager or admin.is_salesperson or admin.is_inventory_manager
        
        # Write access only for inventory manager or superuser
        return admin.is_inventory_manager


class IsBundleManagerOrReadOnly(permissions.BasePermission):
    """
    Bundles:
    - Marketing Manager / Global Admin / Superuser: full access
    - Inventory Manager / Content Creator / Order Manager / Salesperson: read-only
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not request.user.is_staff:
            return False

        admin = get_admin_from_user(request.user)
        if not admin:
            return False

        if request.method in permissions.SAFE_METHODS:
            return (
                admin.is_marketing_manager
                or admin.is_inventory_manager
                or admin.is_content_creator
                or admin.is_order_manager
                or admin.is_salesperson
                or admin.is_global_admin
            )

        return admin.is_marketing_manager or admin.is_global_admin


class IsSalespersonOrInventoryManagerOrMarketingManagerReadOnly(permissions.BasePermission):
    """
    Permission for Product read access:
    - Salesperson: Read-only access (to view product details for reservations)
    - Inventory Manager: Full access (read/write)
    - Marketing Manager: Read-only access
    - Content Creator: Read-only access (to select products for reviews)
    - Superuser: Full access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        # Allow read access for Salespersons, Inventory Managers, Marketing Managers, and Content Creators
        if request.method in permissions.SAFE_METHODS:
            return admin.is_salesperson or admin.is_inventory_manager or admin.is_marketing_manager or admin.is_content_creator
        
        # Write access only for Inventory Managers (not Salespersons, Marketing Managers, or Content Creators)
        return admin.is_inventory_manager


class IsContentCreatorOrInventoryManager(permissions.BasePermission):
    """Permission for write operations: Content Creators OR Inventory Managers (but NOT Marketing Managers)."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        # Allow write access for Content Creators and Inventory Managers, but NOT Marketing Managers
        return admin.is_content_creator or admin.is_inventory_manager


class IsInventoryManagerOrSuperuser(permissions.BasePermission):
    """Permission for create/delete: Inventory Managers or Superusers only."""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_inventory_manager


class IsInventoryManagerOrSalespersonReadOnly(permissions.BasePermission):
    """
    Permission for Inventory Units:
    - Inventory Manager: Full access (read/write)
    - Salesperson: Read-only access
    - Superuser: Full access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        # Read access for salesperson, write access for inventory manager
        if request.method in permissions.SAFE_METHODS:
            return admin.is_salesperson or admin.is_inventory_manager
        
        # Write access only for inventory manager or superuser
        return admin.is_inventory_manager


class IsInventoryManagerOrReadOnly(permissions.BasePermission):
    """
    Permission for Inventory Management operations:
    - Inventory Manager: Full access
    - Others: Read-only (for viewing)
    - Superuser: Full access
    """
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        if request.user.is_superuser:
            return True
        
        if not request.user.is_staff:
            return False
        
        # Read access for all staff users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write access only for inventory manager
        admin = get_admin_from_user(request.user)
        if not admin:
            return False
        
        return admin.is_inventory_manager
