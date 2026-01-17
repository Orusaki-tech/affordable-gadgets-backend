from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password # NEW: For password strength
from rest_framework.authtoken.models import Token # NEW: For generating auth tokens
from django.contrib.auth import authenticate
from .models import (
    Product, Order, OrderItem, Customer, ProductImage, Review, ProductAccessory,
    Admin, Color, User, InventoryUnit, UnitAcquisitionSource, InventoryUnitImage,
    AdminRole, ReservationRequest, ReturnRequest, UnitTransfer, Notification, AuditLog, Tag,
    Brand, Lead, LeadItem, Cart, CartItem, Promotion
)
from decimal import Decimal
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
import logging

logger = logging.getLogger(__name__)

# --- AUTH/PROFILE SERIALIZERS ---

User = get_user_model() 

class UserSerializer(serializers.ModelSerializer):
    """Basic User serialization for nested views."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'last_login', 'date_joined', 'is_staff', 'is_superuser')
        read_only_fields = ('id', 'last_login', 'date_joined', 'is_staff', 'is_superuser')

class AdminRoleSerializer(serializers.ModelSerializer):
    """Serializer for AdminRole model."""
    role_code = serializers.CharField(source='name', read_only=True)
    role_name = serializers.CharField(source='display_name', read_only=True)
    
    class Meta:
        model = AdminRole
        fields = ('id', 'name', 'display_name', 'role_code', 'role_name', 'description', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

class AdminSerializer(serializers.ModelSerializer):
    """
    Serializer for the Admin profile, extending the base User details.
    Used for nested viewing and AdminProfileView retrieval.
    """
    user = UserSerializer(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    last_login = serializers.DateTimeField(source='user.last_login', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    roles = AdminRoleSerializer(many=True, read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(
        queryset=AdminRole.objects.all(),
        source='roles',
        many=True,
        write_only=True,
        required=False
    )
    brands = serializers.SerializerMethodField()
    brand_ids = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.all(),  # Use .all() to avoid evaluation issues
        source='brands',
        many=True,
        write_only=True,
        required=False
    )
    is_global_admin = serializers.BooleanField(read_only=True)
    reserved_units_count = serializers.SerializerMethodField()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter to only active brands
        if 'brand_ids' in self.fields:
            self.fields['brand_ids'].queryset = Brand.objects.filter(is_active=True)
    
    def get_brands(self, obj):
        """Return list of brands associated with this admin"""
        brands = obj.brands.all()
        return [
            {
                'id': brand.id,
                'code': brand.code,
                'name': brand.name,
                'is_active': brand.is_active,
            }
            for brand in brands
        ]
    
    class Meta:
        model = Admin
        fields = ('id', 'user', 'username', 'email', 'admin_code', 'last_login', 'date_joined', 'roles', 'role_ids', 'brands', 'brand_ids', 'is_global_admin', 'reserved_units_count')
        read_only_fields = ('id', 'user', 'username', 'email', 'last_login', 'date_joined', 'roles', 'brands', 'is_global_admin', 'reserved_units_count')
    
    def get_reserved_units_count(self, obj):
        """Count of units currently reserved by this admin."""
        return InventoryUnit.objects.filter(reserved_by=obj, sale_status=InventoryUnit.SaleStatusChoices.RESERVED).count()

class AdminCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new Admin accounts.
    Creates both User and Admin objects.
    """
    username = serializers.CharField(required=True, write_only=True)
    email = serializers.EmailField(required=True, write_only=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    admin_code = serializers.CharField(required=True, max_length=20)
    
    # Read-only fields for response
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Admin
        fields = ('id', 'username', 'email', 'password', 'admin_code', 'user')
        read_only_fields = ('id', 'user')
    
    def to_representation(self, instance):
        """Override to include username and email from related User object."""
        representation = super().to_representation(instance)
        # Add username and email from the related user
        if instance.user:
            representation['username'] = instance.user.username
            representation['email'] = instance.user.email
        return representation
    
    def validate_username(self, value):
        """
        Check that the username is not already in use by an active admin.
        If a User exists with this username but has no Admin profile, we can reuse it.
        """
        existing_user = User.objects.filter(username=value).first()
        if existing_user:
            # Check if this user already has an Admin profile
            if Admin.objects.filter(user=existing_user).exists():
                raise serializers.ValidationError("This username is already taken by an admin.")
        return value
    
    def validate_email(self, value):
        """
        Check that the email is not already in use by an active admin.
        If a User exists with this email but has no Admin profile, we can reuse it.
        """
        existing_user = User.objects.filter(email=value).first()
        if existing_user:
            # Check if this user already has an Admin profile
            if Admin.objects.filter(user=existing_user).exists():
                raise serializers.ValidationError("This email address is already in use by an admin.")
        return value
    
    def validate_admin_code(self, value):
        """Check that the admin code is not already in use."""
        if Admin.objects.filter(admin_code=value).exists():
            raise serializers.ValidationError("This admin code is already in use.")
        return value
    
    @transaction.atomic
    def create(self, validated_data):
        """
        Creates Admin account atomically.
        - If User exists with email/username but no Admin profile, reuses that User
        - If User doesn't exist, creates new User
        - Always creates Admin profile
        - All operations are atomic - either all succeed or all fail
        """
        import logging

        logger = logging.getLogger(__name__)

        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        admin_code = validated_data.pop('admin_code')

        logger.info(
            f"Creating admin with username: {username}, email: {email}, admin_code: {admin_code}"
        )

        # Check if User already exists (by email or username)
        existing_user = None
        if User.objects.filter(email=email).exists():
            existing_user = User.objects.get(email=email)
            logger.info(f"Found existing user with email {email}: {existing_user.username}")
        elif User.objects.filter(username=username).exists():
            existing_user = User.objects.get(username=username)
            logger.info(f"Found existing user with username {username}: {existing_user.email}")

        # If user exists, verify they don't already have an Admin profile
        if existing_user:
            if Admin.objects.filter(user=existing_user).exists():
                raise serializers.ValidationError(
                    {
                        "email": "A user with this email already has an admin profile.",
                        "username": "A user with this username already has an admin profile.",
                    }
                )

            # Reuse existing user - update if needed
            user = existing_user
            user.is_staff = True  # Ensure staff status
            if password:  # Update password if provided
                user.set_password(password)
            # Update email/username if they differ
            if user.email != email:
                user.email = email
            if user.username != username:
                user.username = username
            user.save()
            logger.info(f"Reusing existing user {user.id} for admin creation")
        else:
            # Create new User with staff privileges
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    is_staff=True,
                    is_superuser=False,  # Can be changed if needed
                )
                logger.info(f"User created successfully: {user.id}")
            except Exception as e:
                logger.error(f"Error creating user: {str(e)}")
                raise serializers.ValidationError(
                    {"user": f"Failed to create user account: {str(e)}"}
                )

        # Create Admin profile (this must succeed or transaction rolls back)
        try:
            admin = Admin.objects.create(user=user, admin_code=admin_code)
            logger.info(f"Admin profile created successfully: {admin.id}")
            return admin
        except Exception as e:
            logger.error(f"Error creating admin profile: {str(e)}")
            # Transaction will roll back automatically, but surface a clear error
            raise serializers.ValidationError(
                {"admin": f"Failed to create admin profile: {str(e)}"}
            )

class CustomerSerializer(serializers.ModelSerializer):
    """Customer serialization for nested views (e.g., in Order or Review)."""
    user = UserSerializer(read_only=True)
    class Meta:
        model = Customer
        # Including all fields for comprehensive display when nested
        fields = ('id', 'user', 'phone_number', 'address', )
        read_only_fields = ('id', 'user') 

class CustomerProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Dedicated Serializer for RetrieveUpdateAPIView (CustomerProfileView).
    Allows authenticated users to update their personal details AND returns 
    the full name from the linked User model.
    """
    # READ-ONLY FIELDS: Directly fetch fields from the related User instance
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.ReadOnlyField(source='user.email')
    
    # NEW: Include First Name and Last Name from the User model
    first_name = serializers.ReadOnlyField(source='user.first_name')
    last_name = serializers.ReadOnlyField(source='user.last_name')
    
    class Meta:
        model = Customer
        # Include the new fields in the list
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 
            'phone_number', 'address', 'user'
        )
        read_only_fields = ('id', 'user', 'username', 'email', 'first_name', 'last_name')


class CustomerRegistrationSerializer(serializers.Serializer):
    """
    NEW: Serializer to handle the creation of both a User account and its linked 
    Customer profile in one atomic transaction.
    """
    # User Model Fields
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        style={'input_type': 'password'},
        validators=[validate_password] # Django's built-in password validation
    )
    
    # Customer Model Fields
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    

    def validate_email(self, value):
        """Check that the email is not already in use."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email address is already in use.")
        return value

    def validate_username(self, value):
        """Check that the username is not already in use."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        """
        Creates the User and Customer instances atomically.
        """
        # 1. Pop fields intended for the User model
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        password = validated_data.pop('password')

        # 2. Create the User instance with password hashing
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
            # Note: is_staff defaults to False, which is correct for a Customer
        )

        # 3. Create the Customer instance, linking it to the new User
        customer = Customer.objects.create(
            user=user,
            **validated_data # This includes phone_number, address
        )

        # 4. Create an authentication token for immediate login
        token = Token.objects.create(user=user)

        # Return the Customer instance
        return customer

    def to_representation(self, instance):
        """
        Custom representation to include the authentication token upon successful registration.
        """
        # Get the token created in the .create() method
        token = Token.objects.get(user=instance.user).key
        
        # Return the Customer data plus the token
        return {
            'username': instance.user.username,
            'email': instance.user.email,
            'phone_number': instance.phone_number,
            'token': token,
            'message': 'Registration successful. Token generated for immediate use.'
        }
class CustomerLoginSerializer(serializers.Serializer):
    """
    Serializer to handle username/email and password authentication.
    """
    username_or_email = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    # Read-only fields returned on successful login
    token = serializers.CharField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    
    # Instance attribute to hold the authenticated user
    user = None

    def validate(self, data):
        """
        Custom validation to perform the authentication using Django's built-in system.
        """
        username_or_email = data.get('username_or_email')
        password = data.get('password')

        if not username_or_email or not password:
            raise serializers.ValidationError("Must include 'username_or_email' and 'password'.")

        # Try to find the user by username or email
        try:
            # Use filter/get logic to allow login with either username or email
            if '@' in username_or_email:
                user = User.objects.get(email__iexact=username_or_email)
                username = user.username # Use the found username for auth
            else:
                username = username_or_email
            
            # Use Django's authenticate function
            user = authenticate(username=username, password=password)

        except User.DoesNotExist:
            # If the user is not found by email, it will be handled by authenticate returning None
            user = authenticate(username=username_or_email, password=password)


        if user and user.is_active:
            # Update last_login timestamp
            from django.utils import timezone
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
            
            # Check if a token already exists, otherwise create a new one
            token, created = Token.objects.get_or_create(user=user)
            self.user = user
            
            # Pass the token key and user ID back in the validated data
            data['token'] = token.key
            data['user_id'] = user.id
            data['email'] = user.email
            data['is_staff'] = user.is_staff  # Indicate if user has admin privileges

            return data
        
        raise serializers.ValidationError("Invalid credentials or user is inactive.")

# --- UTILITY SERIALIZERS ---

class ColorSerializer(serializers.ModelSerializer):
    """Serializes the Color model."""
    class Meta:
        model = Color
        fields = ('id', 'name', 'hex_code')
        read_only_fields = ('id',)

class UnitAcquisitionSourceSerializer(serializers.ModelSerializer):
    """
    Serializer for managing Supplier and Import Partner contact details (CRUD endpoint).
    """
    class Meta:
        model = UnitAcquisitionSource
        fields = ('id', 'source_type', 'name', 'phone_number')
        read_only_fields = ('id',)
        
class DiscountCalculatorSerializer(serializers.Serializer):
    """
    Utility serializer to calculate the discount percentage based on price difference.
    """
    original_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01'),
        help_text="The original selling price of the item."
    )
    sale_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.00'),
        help_text="The amount the item is being sold for."
    )
    discount_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True,
        help_text="The calculated discount percentage."
    )

    def validate(self, data):
        original_price = data['original_price']
        sale_price = data['sale_price']

        if sale_price > original_price:
            raise serializers.ValidationError({"sale_price": "Sale price cannot be higher than the original price."})
        return data

    def to_representation(self, instance):
        """Perform calculation and return the result."""
        original_price = instance['original_price']
        sale_price = instance['sale_price']
        
        discount_amount = original_price - sale_price
        if original_price > 0:
            discount_percentage = (discount_amount / original_price) * Decimal('100.00')
        else:
            discount_percentage = Decimal('0.00')
            
        return {
            'original_price': original_price,
            'sale_price': sale_price,
            'discount_percentage': round(discount_percentage, 2)
        }


# --- PRODUCT TEMPLATE SERIALIZER ---
class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for Product images.
    - Read: returns computed image_url for display and product ID
    - Write (admin-only): accepts product and image to create a new image
    """
    image_url = serializers.SerializerMethodField(read_only=True)

    # Product field: readable for filtering, writable for creation
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), read_only=False
    )
    image = serializers.ImageField(write_only=True)

    class Meta:
        model = ProductImage
        fields = ('id', 'product', 'image', 'is_primary', 'image_url', 'alt_text', 'image_caption', 'display_order')
        read_only_fields = ('id',)
    
    def get_image_url(self, obj):
        """Return optimized image URL with Cloudinary transformations"""
        if obj.image:
            from .cloudinary_utils import get_optimized_image_url
            # Return optimized URL (auto-optimized by Cloudinary)
            return get_optimized_image_url(obj.image)
        return None

    def create(self, validated_data):
        image = validated_data.pop('image', None)
        instance = super().create(validated_data)

        if image:
            from .cloudinary_utils import upload_image_to_cloudinary
            saved_name, _ = upload_image_to_cloudinary(image, 'product_photos')
            if saved_name:
                instance.image.name = saved_name
                instance.save()

        return instance

    def update(self, instance, validated_data):
        image = validated_data.pop('image', None)
        instance = super().update(instance, validated_data)

        if image is not None:
            if image:
                from .cloudinary_utils import upload_image_to_cloudinary
                saved_name, _ = upload_image_to_cloudinary(image, 'product_photos')
                if saved_name:
                    instance.image.name = saved_name
            else:
                instance.image = None
            instance.save()

        return instance
    
    def validate_alt_text(self, value):
        """Warn if alt_text is missing (but don't block - can be added later)"""
        if not value or not value.strip():
            # This is a warning, not an error - alt text should be added but isn't required immediately
            pass
        return value

class InventoryUnitImageSerializer(serializers.ModelSerializer):
    """
    Serializer for Inventory Unit images.
    - Read: returns computed image_url for display
    - Write (admin-only): accepts inventory_unit and image to create a new image
    """
    image_url = serializers.SerializerMethodField(read_only=True)

    # Writable fields for creation
    inventory_unit = serializers.PrimaryKeyRelatedField(
        queryset=InventoryUnit.objects.all(), write_only=True
    )
    image = serializers.ImageField(write_only=True)

    # Color field for color selection from images
    color = ColorSerializer(read_only=True)
    color_id = serializers.PrimaryKeyRelatedField(
        queryset=Color.objects.all(),
        source='color',
        allow_null=True,
        required=False,
        write_only=True
    )
    color_name = serializers.CharField(source='color.name', read_only=True)

    class Meta:
        model = InventoryUnitImage
        fields = ('id', 'inventory_unit', 'image', 'is_primary', 'image_url', 'color', 'color_id', 'color_name', 'created_at')
        read_only_fields = ('id', 'created_at', 'color', 'color_name')
    
    def get_image_url(self, obj):
        """Return optimized image URL with Cloudinary transformations"""
        if obj.image:
            from .cloudinary_utils import get_optimized_image_url
            # Return optimized URL (auto-optimized by Cloudinary)
            return get_optimized_image_url(obj.image)
        return None

    def create(self, validated_data):
        image = validated_data.pop('image', None)
        instance = super().create(validated_data)

        if image:
            from .cloudinary_utils import upload_image_to_cloudinary
            saved_name, _ = upload_image_to_cloudinary(image, 'unit_photos')
            if saved_name:
                instance.image.name = saved_name
                instance.save()

        return instance

    def update(self, instance, validated_data):
        image = validated_data.pop('image', None)
        instance = super().update(instance, validated_data)

        if image is not None:
            if image:
                from .cloudinary_utils import upload_image_to_cloudinary
                saved_name, _ = upload_image_to_cloudinary(image, 'unit_photos')
                if saved_name:
                    instance.image.name = saved_name
            else:
                instance.image = None
            instance.save()

        return instance

class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializes the generic Product template.
    """
    product_type_display = serializers.CharField(source='get_product_type_display', read_only=True)
    # images is a reverse relation (one-to-many from ProductImage), so it's read-only
    images = serializers.SerializerMethodField(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        source='tags',
        many=True,
        write_only=True,
        required=False
    )
    # Brand association fields
    brands = serializers.SerializerMethodField(read_only=True)
    brand_ids = serializers.PrimaryKeyRelatedField(
        queryset=Brand.objects.filter(is_active=True),
        source='brands',
        many=True,
        write_only=True,
        required=False,
        help_text="List of Brand IDs this product is available for. Empty = available to all brands."
    )
    is_global = serializers.BooleanField(
        required=False,
        help_text="If True, product is available to all brands regardless of brand assignment"
    )
    seo_score = serializers.SerializerMethodField(read_only=True)
    og_image_url = serializers.SerializerMethodField(read_only=True)
    product_video_file_url = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Product
        fields = (
            'id', 'product_type', 'product_type_display', 'product_name', 
            'product_description', 'brand', 'model_series',
            'min_stock_threshold', 'reorder_point', 'is_discontinued',
            'created_at', 'updated_at',
            'created_by', 'updated_by', 'images',
            # SEO Fields
            'meta_title', 'meta_description', 'slug', 'keywords', 'og_image', 'og_image_url',
            # Content Fields
            'product_highlights', 'long_description', 'is_published',
            # Video Fields
            'product_video_url', 'product_video_file', 'product_video_file_url',
            # Tags
            'tags', 'tag_ids',
            # Brand Assignment
            'brands', 'brand_ids', 'is_global',
            # Computed Fields
            'seo_score'
        )
        read_only_fields = ('id', 'created_at', 'updated_at', 'images', 'created_by', 'updated_by', 'seo_score', 'og_image_url', 'product_video_file_url', 'brands')
    
    def get_brands(self, obj):
        """Return list of brands associated with this product"""
        # Import here to avoid circular import
        brands = obj.brands.all()
        return [
            {
                'id': brand.id,
                'code': brand.code,
                'name': brand.name,
                'is_active': brand.is_active,
            }
            for brand in brands
        ]
    
    def get_images(self, obj):
        """Return list of image URLs for this product with alt text and ordering"""
        if hasattr(obj, 'images'):
            from .cloudinary_utils import get_optimized_image_url
            return [
                {
                    'id': img.id,
                    'image_url': get_optimized_image_url(img.image),
                    'thumbnail_url': get_optimized_image_url(img.image, width=200, height=200),
                    'is_primary': img.is_primary,
                    'alt_text': img.alt_text,
                    'image_caption': img.image_caption,
                    'display_order': img.display_order
                }
                for img in obj.images.all()
            ]
        return []
    
    def get_og_image_url(self, obj):
        """Return OG image URL if available with optimization"""
        if obj.og_image:
            from .cloudinary_utils import get_optimized_image_url
            # OG images should be 1200x630 for optimal social sharing
            return get_optimized_image_url(obj.og_image, width=1200, height=630, crop='fill')
        return None
    
    def get_product_video_file_url(self, obj):
        """Return product video file URL if available with optimization"""
        if obj.product_video_file:
            from .cloudinary_utils import get_video_url
            # Return optimized video URL
            return get_video_url(obj.product_video_file)
        return None
    
    def get_seo_score(self, obj):
        """Calculate SEO completion score (0-100)"""
        score = 0
        total_checks = 8
        
        # Check each SEO element
        if obj.meta_title:
            score += 1
        if obj.meta_description:
            score += 1
        if obj.slug:
            score += 1
        if obj.og_image:
            score += 1
        if obj.product_description:
            score += 1
        if obj.images.exists():
            # Check if at least one image has alt text
            if obj.images.filter(alt_text__isnull=False).exclude(alt_text='').exists():
                score += 1
        if obj.product_highlights and len(obj.product_highlights) > 0:
            score += 1
        if obj.keywords:
            score += 1
        
        return round((score / total_checks) * 100)
    
    def validate_meta_title(self, value):
        """Validate meta title length"""
        if value and len(value) > 60:
            raise serializers.ValidationError("Meta title should be 60 characters or less for optimal SEO.")
        return value
    
    def validate_meta_description(self, value):
        """Validate meta description length"""
        if value and len(value) > 160:
            raise serializers.ValidationError("Meta description should be 160 characters or less for optimal SEO.")
        return value

    def create(self, validated_data):
        og_image = validated_data.pop('og_image', None)
        product_video_file = validated_data.pop('product_video_file', None)

        instance = super().create(validated_data)

        if og_image:
            from .cloudinary_utils import upload_image_to_cloudinary
            saved_name, _ = upload_image_to_cloudinary(og_image, 'og_images')
            if saved_name:
                instance.og_image.name = saved_name

        if product_video_file:
            from .cloudinary_utils import upload_video_to_cloudinary
            saved_name, _ = upload_video_to_cloudinary(product_video_file, 'product_videos')
            if saved_name:
                instance.product_video_file.name = saved_name

        if og_image or product_video_file:
            instance.save()

        return instance

    def update(self, instance, validated_data):
        og_image = validated_data.pop('og_image', None)
        product_video_file = validated_data.pop('product_video_file', None)

        instance = super().update(instance, validated_data)

        if og_image is not None:
            if og_image:
                from .cloudinary_utils import upload_image_to_cloudinary
                saved_name, _ = upload_image_to_cloudinary(og_image, 'og_images')
                if saved_name:
                    instance.og_image.name = saved_name
            else:
                instance.og_image = None

        if product_video_file is not None:
            if product_video_file:
                from .cloudinary_utils import upload_video_to_cloudinary
                saved_name, _ = upload_video_to_cloudinary(product_video_file, 'product_videos')
                if saved_name:
                    instance.product_video_file.name = saved_name
            else:
                instance.product_video_file = None

        if og_image is not None or product_video_file is not None:
            instance.save()

        return instance

# --- PRODUCT ACCESSORY LINK SERIALIZER ---

class ProductAccessorySerializer(serializers.ModelSerializer):
    """
    Serializer for the intermediary ProductAccessory model. 
    """
    # Read-only fields for clarity
    main_product_name = serializers.CharField(source='main_product.product_name', read_only=True)
    accessory_name = serializers.CharField(source='accessory.product_name', read_only=True)
    accessory_slug = serializers.CharField(source='accessory.slug', read_only=True)
    
    # Include accessory product details
    accessory_primary_image = serializers.SerializerMethodField()
    accessory_video_url = serializers.CharField(source='accessory.product_video_url', read_only=True)
    accessory_price_range = serializers.SerializerMethodField()
    
    def get_accessory_primary_image(self, obj):
        """Get the primary image URL for the accessory product."""
        from inventory.models import ProductImage
        from inventory.cloudinary_utils import get_optimized_image_url
        
        primary_image = ProductImage.objects.filter(
            product=obj.accessory,
            is_primary=True
        ).first()
        
        if primary_image and primary_image.image:
            request = self.context.get('request')
            original_url = primary_image.image.url
            cloudinary_url = get_optimized_image_url(primary_image.image)
            
            # Build absolute URLs for local files
            if original_url.startswith('/media/') or original_url.startswith('/static/'):
                if request:
                    try:
                        absolute_url = request.build_absolute_uri(original_url)
                    except Exception:
                        # Fallback if request doesn't have proper host
                        from django.conf import settings
                        host = getattr(request, 'get_host', lambda: 'localhost:8000')()
                        scheme = getattr(request, 'scheme', 'http')
                        absolute_url = f"{scheme}://{host}{original_url}"
                else:
                    # Fallback if no request context
                    from django.conf import settings
                    import os
                    host = os.environ.get('DJANGO_HOST', 'localhost:8000')
                    protocol = 'https' if os.environ.get('DJANGO_USE_HTTPS', '').lower() == 'true' else 'http'
                    absolute_url = f"{protocol}://{host}{original_url}"
                
                # Use Cloudinary if available, otherwise absolute local URL
                return cloudinary_url if (cloudinary_url and cloudinary_url != original_url and 'cloudinary.com' in cloudinary_url) else absolute_url
            else:
                return cloudinary_url
        return None
    
    def get_accessory_price_range(self, obj):
        """Get price range for available accessory units."""
        from inventory.models import InventoryUnit
        from django.db.models import Min, Max
        
        # For accessories, calculate available quantity accounting for pending orders
        from django.db.models import Sum, Min, Max
        from inventory.models import Order
        
        # Get all units for this accessory
        all_units = obj.accessory.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        
        # Filter to only units with available quantity > 0 (accounting for pending orders)
        available_units = []
        for unit in all_units:
            pending_orders_qty = OrderItem.objects.filter(
                inventory_unit=unit,
                order__status__in=[Order.StatusChoices.PENDING, Order.StatusChoices.PAID]
            ).aggregate(total=Sum('quantity'))['total'] or 0
            available_qty = unit.quantity - pending_orders_qty
            if available_qty > 0:
                available_units.append(unit)
        
        if available_units:
            prices = InventoryUnit.objects.filter(
                id__in=[u.id for u in available_units]
            ).aggregate(
                min_price=Min('selling_price'),
                max_price=Max('selling_price')
            )
            return {
                'min': float(prices['min_price']) if prices['min_price'] else None,
                'max': float(prices['max_price']) if prices['max_price'] else None,
            }
        return {'min': None, 'max': None}
    
    accessory_color_variants = serializers.SerializerMethodField()
    
    def get_accessory_color_variants(self, obj):
        """
        Get all available color variants for this accessory.
        Groups units by color and shows all available options.
        """
        from inventory.models import InventoryUnit
        from inventory.cloudinary_utils import get_optimized_image_url
        import logging
        
        logger = logging.getLogger(__name__)
        
        # #region agent log
        # Debug: Check all units for this accessory (before filtering)
        all_units = InventoryUnit.objects.filter(product_template=obj.accessory)
        logger.info(f"DEBUG[ACCESSORY] Accessory ID={obj.accessory.id} name={obj.accessory.product_name} - Total units: {all_units.count()}")
        for unit in all_units:
            logger.info(f"DEBUG[ACCESSORY] Unit ID={unit.id} quantity={unit.quantity} sale_status={unit.sale_status} available_online={unit.available_online}")
        # #endregion
        
        # For accessories, calculate available quantity accounting for pending orders
        from django.db.models import Sum
        from inventory.models import Order
        
        # Get all units for this accessory
        all_units = InventoryUnit.objects.filter(
            product_template=obj.accessory,
            available_online=True
        ).select_related('product_color').prefetch_related(
            'images'  # Prefetch all unit images
        )
        
        # Filter to only units with available quantity > 0 (accounting for pending orders)
        available_units = []
        for unit in all_units:
            # Calculate pending order quantities for this unit
            pending_orders_qty = OrderItem.objects.filter(
                inventory_unit=unit,
                order__status__in=[Order.StatusChoices.PENDING, Order.StatusChoices.PAID]
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            available_qty = unit.quantity - pending_orders_qty
            
            # Only include units with available quantity > 0 and status AVAILABLE
            if available_qty > 0 and unit.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE:
                available_units.append(unit)
                # #region agent log
                logger.info(f"DEBUG[ACCESSORY] Unit ID={unit.id} total_qty={unit.quantity} pending={pending_orders_qty} available={available_qty}")
                # #endregion
        
        # #region agent log
        logger.info(f"DEBUG[ACCESSORY] After filtering - Available units count: {len(available_units)}")
        total_qty = sum(unit.quantity - (OrderItem.objects.filter(
            inventory_unit=unit,
            order__status__in=[Order.StatusChoices.PENDING, Order.StatusChoices.PAID]
        ).aggregate(total=Sum('quantity'))['total'] or 0) for unit in available_units)
        logger.info(f"DEBUG[ACCESSORY] Total available quantity: {total_qty}")
        # #endregion
        
        # Group by color
        color_variants = {}
        for unit in available_units:
            color_id = unit.product_color.id if unit.product_color else None
            color_name = unit.product_color.name if unit.product_color else 'Universal'
            
            if color_id not in color_variants:
                color_variants[color_id] = {
                    'color_id': color_id,
                    'color_name': color_name,
                    'hex_code': unit.product_color.hex_code if unit.product_color else None,
                    'units': [],
                    'min_price': float('inf'),
                    'max_price': 0,
                    'total_quantity': 0,
                }
            
            # Get image for this color variant (primary first, then any image, then product image)
            # Use the same pattern as PublicInventoryUnitSerializer
            # Access prefetched images
            unit_images_list = list(unit.images.all()) if hasattr(unit, 'images') else []
            unit_image_obj = None
            
            # Try primary image first
            for img in unit_images_list:
                if img.is_primary and img.image:
                    unit_image_obj = img
                    break
            
            # If no primary, use any image
            if not unit_image_obj:
                for img in unit_images_list:
                    if img.image:
                        unit_image_obj = img
                        break
            
            # If no unit image, try product primary image
            if not unit_image_obj or not unit_image_obj.image:
                from inventory.models import ProductImage
                product_image = ProductImage.objects.filter(
                    product=unit.product_template,
                    is_primary=True
                ).first()
                if product_image and product_image.image:
                    # Create a mock object with the image field
                    class MockImage:
                        def __init__(self, img):
                            self.image = img.image
                    unit_image_obj = MockImage(product_image)
            
            image_url = None
            if unit_image_obj and hasattr(unit_image_obj, 'image') and unit_image_obj.image:
                request = self.context.get('request')
                original_url = unit_image_obj.image.url
                cloudinary_url = get_optimized_image_url(unit_image_obj.image)
                
                # Build absolute URLs for local files (same pattern as PublicInventoryUnitSerializer)
                if (original_url.startswith('/media/') or original_url.startswith('/static/')) and request:
                    absolute_url = request.build_absolute_uri(original_url)
                    # Use Cloudinary if available, otherwise absolute local URL
                    image_url = cloudinary_url if (cloudinary_url and cloudinary_url != original_url and 'cloudinary.com' in cloudinary_url) else absolute_url
                elif original_url.startswith('/media/') or original_url.startswith('/static/'):
                    # Fallback if no request context
                    import os
                    host = os.environ.get('DJANGO_HOST', 'localhost:8000')
                    protocol = 'https' if os.environ.get('DJANGO_USE_HTTPS', '').lower() == 'true' else 'http'
                    image_url = f"{protocol}://{host}{original_url}"
                else:
                    image_url = cloudinary_url
            
            # Calculate available quantity for this unit (accounting for pending orders)
            from django.db.models import Sum
            from inventory.models import Order
            pending_orders_qty = OrderItem.objects.filter(
                inventory_unit=unit,
                order__status__in=[Order.StatusChoices.PENDING, Order.StatusChoices.PAID]
            ).aggregate(total=Sum('quantity'))['total'] or 0
            available_qty = unit.quantity - pending_orders_qty
            
            color_variants[color_id]['units'].append({
                'unit_id': unit.id,
                'price': float(unit.selling_price),
                'quantity': available_qty,  # Show available quantity, not total
                'condition': unit.condition,
                'image_url': image_url,
            })
            
            # Update price range
            price = float(unit.selling_price)
            color_variants[color_id]['min_price'] = min(color_variants[color_id]['min_price'], price)
            color_variants[color_id]['max_price'] = max(color_variants[color_id]['max_price'], price)
            color_variants[color_id]['total_quantity'] += available_qty
        
        # Convert to list and format
        result = []
        for color_id, variant_data in color_variants.items():
            result.append({
                'color_id': color_id,
                'color_name': variant_data['color_name'],
                'hex_code': variant_data['hex_code'],
                'min_price': variant_data['min_price'] if variant_data['min_price'] != float('inf') else None,
                'max_price': variant_data['max_price'] if variant_data['max_price'] > 0 else None,
                'total_quantity': variant_data['total_quantity'],
                'available_units': len(variant_data['units']),
                'units': variant_data['units'],
            })
        
        # Sort by color name for consistent display
        result.sort(key=lambda x: x['color_name'])
        
        return result

    class Meta:
        model = ProductAccessory
        fields = (
            'id', 'main_product', 'accessory', 'required_quantity',
            'main_product_name', 'accessory_name', 'accessory_slug',
            'accessory_primary_image', 'accessory_video_url', 'accessory_price_range',
            'accessory_color_variants'
        )
        read_only_fields = ('id',)

# --- INVENTORY UNIT SERIALIZER (The core logic for validation) ---

class InventoryUnitSerializer(serializers.ModelSerializer):
    """
    Serializes physical Inventory Units.
    - Phones/Laptops/Tablets: Unique units (serial_number/IMEI), quantity=1.
    - Accessories: Bulk items (no unique identifier), quantity required and can be > 1.
    """
    # Read-only fields for context and display
    product_template = serializers.PrimaryKeyRelatedField(read_only=True)  # Read-only ID for filtering/matching
    product_template_name = serializers.CharField(source='product_template.product_name', read_only=True)
    product_brand = serializers.CharField(source='product_template.brand', read_only=True)
    product_type = serializers.CharField(source='product_template.product_type', read_only=True)
    
    # Nested fields for related objects (read-only views)
    product_color = ColorSerializer(read_only=True)
    color_name = serializers.CharField(source='product_color.name', read_only=True)
    acquisition_source_details = UnitAcquisitionSourceSerializer(read_only=True)
    # Images as read-only nested field
    images = serializers.SerializerMethodField(read_only=True)
    
    # Writable fields for Foreign Keys (used during creation/update)
    product_template_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product_template', write_only=True
    )
    product_color_id = serializers.PrimaryKeyRelatedField(
        queryset=Color.objects.all(), source='product_color', allow_null=True, required=False, write_only=True
    )
    acquisition_source_details_id = serializers.PrimaryKeyRelatedField(
        queryset=UnitAcquisitionSource.objects.all(), source='acquisition_source_details', 
        allow_null=True, required=False, write_only=True
    )
    
    # sale_status is read-only - system-managed only (order lifecycle, buyback approval, etc.)
    sale_status = serializers.CharField(read_only=True)
    # available_online - whether unit can be purchased online (editable by admins)
    available_online = serializers.BooleanField(default=True, required=False)
    
    # Reservation fields
    reserved_by_username = serializers.CharField(source='reserved_by.user.username', read_only=True)
    reserved_by_id = serializers.IntegerField(source='reserved_by.id', read_only=True)
    reserved_until = serializers.DateTimeField(read_only=True)
    can_reserve = serializers.SerializerMethodField()
    can_transfer = serializers.SerializerMethodField()
    is_reservation_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryUnit
        fields = (
            # IDs & Template context
            'id', 'product_template', 'product_template_id', 'product_template_name', 'product_brand', 'product_type',
            'product_color_id', 'product_color', 'color_name', 'acquisition_source_details_id', 'acquisition_source_details',
            # Core attributes
            'condition', 'source', 'sale_status', 'available_online', 'grade', 'date_sourced',
            'cost_of_unit', 'selling_price', 'quantity', 'serial_number', 'imei', 
            # Specs
            'storage_gb', 'ram_gb', 'battery_mah', 'is_sim_enabled', 'processor_details',
            # Images
            'images',
            # Reservation fields
            'reserved_by_id', 'reserved_by_username', 'reserved_until', 'can_reserve', 'can_transfer', 'is_reservation_expired'
        )
        read_only_fields = ('id', 'sale_status', 'images', 'reserved_by_id', 'reserved_by_username', 'reserved_until', 'can_reserve', 'can_transfer', 'is_reservation_expired')
    
    def get_can_reserve(self, obj):
        """Check if current user can reserve this unit."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if not request.user.is_staff:
            return False
        try:
            admin = Admin.objects.get(user=request.user)
            return admin.is_salesperson and obj.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE
        except Admin.DoesNotExist:
            return False
    
    def get_can_transfer(self, obj):
        """Check if current user can request transfer of this unit."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        if not request.user.is_staff:
            return False
        if obj.sale_status != InventoryUnit.SaleStatusChoices.RESERVED or not obj.reserved_by:
            return False
        try:
            admin = Admin.objects.get(user=request.user)
            # Can transfer if unit is reserved by someone else
            return admin.is_salesperson and obj.reserved_by.id != admin.id
        except Admin.DoesNotExist:
            return False
    
    def get_images(self, obj):
        """Return list of image URLs for this inventory unit"""
        if hasattr(obj, 'images'):
            from .cloudinary_utils import get_optimized_image_url
            images = obj.images.all().order_by('-is_primary', 'id')
            return [
                {
                    'id': img.id,
                    'image_url': get_optimized_image_url(img.image) if img.image else None,
                    'thumbnail_url': get_optimized_image_url(img.image, width=200, height=200) if img.image else None,
                    'is_primary': img.is_primary,
                    'color_id': img.color.id if img.color else None,
                    'color_name': img.color.name if img.color else None,
                    'created_at': img.created_at
                }
                for img in images
            ]
        return []

    def validate(self, data):
        """
        Custom validation to enforce business rules based on Product Type and Brand.
        This logic is critical for data integrity.
        """
        # --- Context Setup (Using provided logic to handle instance/data lookup) ---
        if 'product_template' in data:
            template = data['product_template']
        elif self.instance:
            template = self.instance.product_template
        else:
            raise serializers.ValidationError({"product_template_id": "Product template must be specified."})

        product_type = template.product_type
        brand = template.brand.lower()
        
        # Pull data, falling back to existing instance if updating
        current_imei = data.get('imei', getattr(self.instance, 'imei', None))
        current_sn = data.get('serial_number', getattr(self.instance, 'serial_number', None))
        current_storage = data.get('storage_gb', getattr(self.instance, 'storage_gb', None))
        current_ram = data.get('ram_gb', getattr(self.instance, 'ram_gb', None))
        current_grade = data.get('grade', getattr(self.instance, 'grade', None))
        current_is_sim = data.get('is_sim_enabled', getattr(self.instance, 'is_sim_enabled', False))
        current_source = data.get('source', getattr(self.instance, 'source', None))
        current_source_details = data.get('acquisition_source_details', getattr(self.instance, 'acquisition_source_details', None))

        
        is_accessory = product_type == Product.ProductType.ACCESSORY
        is_phone_or_tablet = product_type in [Product.ProductType.PHONE, Product.ProductType.TABLET]
        is_laptop = product_type == Product.ProductType.LAPTOP
        
        # --- 1. QUANTITY LOGIC ---
        current_quantity = data.get('quantity', getattr(self.instance, 'quantity', 1))
        
        if not is_accessory:
            # Phones/Laptops/Tablets: quantity must be 1
            if current_quantity != 1:
                raise serializers.ValidationError({
                    "quantity": "Quantity must be 1 for Phones, Laptops, and Tablets (unique units)."
                })
        else:
            # Accessories: quantity required and must be >= 1
            if not current_quantity or current_quantity < 1:
                raise serializers.ValidationError({
                    "quantity": "Quantity is required and must be at least 1 for accessories."
                })
        
        # --- 2. UNIQUE UNIT REQUIREMENTS (SN, IMEI, Grade, Processor) ---
        if not is_accessory:
            if not current_sn:
                raise serializers.ValidationError({"serial_number": "Serial number is required for all unique products."})
            
            if is_phone_or_tablet:
                if (product_type == Product.ProductType.PHONE or (product_type == Product.ProductType.TABLET and current_is_sim)):
                    if not current_imei:
                        raise serializers.ValidationError({"imei": "IMEI is required for Phones and SIM-enabled Tablets."})
                
                if not current_grade:
                     raise serializers.ValidationError({"grade": "Grade (A or B) is required for Phones and Tablets."})

            if is_laptop:
                if current_imei:
                    raise serializers.ValidationError({"imei": "Laptops should not have an IMEI."})
                if not data.get('processor_details', getattr(self.instance, 'processor_details', None)):
                    raise serializers.ValidationError({"processor_details": "Processor details are required for Laptops."})
        else:
            # Accessories don't need serial_number or IMEI
            if current_sn:
                raise serializers.ValidationError({
                    "serial_number": "Accessories should not have serial numbers."
                })
            if current_imei:
                raise serializers.ValidationError({
                    "imei": "Accessories should not have IMEI numbers."
                })
        
        # --- 3. RAM/STORAGE CONDITIONAL LOGIC ---
        if not is_accessory:
            if brand == 'apple':
                if not current_storage:
                    raise serializers.ValidationError({"storage_gb": "Storage is required for all Apple products."})
                if current_ram and current_ram != 0:
                    raise serializers.ValidationError({"ram_gb": "RAM should be blank for Apple products (storage-only input)."})
            else: # All other brands require both RAM and Storage
                if not current_storage or not current_ram:
                    raise serializers.ValidationError({"storage_gb": "Storage and RAM are required for non-Apple unique products."})
        
        # --- 4. CONDITIONAL ACQUISITION SOURCE DETAILS ---
        if current_source in [InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER, InventoryUnit.SourceChoices.EXTERNAL_IMPORT]:
            if not current_source_details:
                raise serializers.ValidationError({"acquisition_source_details_id": "Acquisition source details are required for External Supplier or Import sources."})
        
        if current_source == InventoryUnit.SourceChoices.BUYBACK_CUSTOMER:
            if current_source_details:
                raise serializers.ValidationError({"acquisition_source_details_id": "Acquisition source details must be blank for Buyback sources."})
        
        return data
    
    def create(self, validated_data):
        """
        Auto-set sale_status based on source:
        - Buyback (BB) → RETURNED (needs admin approval via ReturnRequest)
        - Supplier/Import (SU/IM) → AVAILABLE
        """
        source = validated_data.get('source', InventoryUnit.SourceChoices.EXTERNAL_SUPPLIER)
        
        if source == InventoryUnit.SourceChoices.BUYBACK_CUSTOMER:
            validated_data['sale_status'] = InventoryUnit.SaleStatusChoices.RETURNED
        else:
            validated_data['sale_status'] = InventoryUnit.SaleStatusChoices.AVAILABLE
        
        # Default available_online to True if not provided
        if 'available_online' not in validated_data:
            validated_data['available_online'] = True
        
        # Create the unit
        unit = super().create(validated_data)
        
        # Auto-create ReturnRequest for buyback units
        if source == InventoryUnit.SourceChoices.BUYBACK_CUSTOMER:
            from inventory.models import ReturnRequest
            return_request = ReturnRequest.objects.create(
                requesting_salesperson=None,  # Buyback units don't have a salesperson
                status=ReturnRequest.StatusChoices.PENDING,
                notes="Auto-created for buyback unit"
            )
            return_request.inventory_units.add(unit)
        
        return unit
    
    def update(self, instance, validated_data):
        """
        Prevent manual sale_status changes - it's system-managed.
        Sale status is controlled by order lifecycle, buyback approval, etc.
        """
        # sale_status is read-only, so it shouldn't be in validated_data
        # Remove it if somehow it got through
        validated_data.pop('sale_status', None)
        
        return super().update(instance, validated_data)


# --- PUBLIC-FACING INVENTORY UNIT SERIALIZER (Safe fields only) ---

class PublicInventoryUnitSerializer(serializers.ModelSerializer):
    product_template_name = serializers.CharField(source='product_template.product_name', read_only=True)
    product_brand = serializers.CharField(source='product_template.brand', read_only=True)
    product_type = serializers.CharField(source='product_template.product_type', read_only=True)
    product_color = ColorSerializer(read_only=True)

    class Meta:
        model = InventoryUnit
        fields = (
            'id',
            'product_template_name', 'product_brand', 'product_type',
            'condition', 'grade',
            'selling_price',
            'storage_gb', 'ram_gb', 'is_sim_enabled', 'processor_details',
            'product_color',
        )

# --- SALES AND ORDER SERIALIZERS ---

class ReviewSerializer(serializers.ModelSerializer):
    """
    Serializes the Review model. Handles the read-only customer relationship.
    Supports both video file uploads and video URLs.
    """
    customer_username = serializers.SerializerMethodField(read_only=True)
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    is_admin_review = serializers.BooleanField(read_only=True)  # Computed from customer field
    review_image_url = serializers.SerializerMethodField(read_only=True)
    # review_image is the model field (ImageField) - writable for uploads
    review_image = serializers.ImageField(required=False, allow_null=True)
    
    def get_customer_username(self, obj):
        """Get customer username, handling None customer (admin reviews)."""
        if obj.customer and obj.customer.user:
            return obj.customer.user.username
        return None
    video_file_url = serializers.SerializerMethodField()  # Returns full URL to uploaded video
    
    class Meta:
        model = Review
        fields = (
            'id', 'product', 'video_file', 'video_url', 'video_file_url',
            'review_image', 'review_image_url',
            'product_name', 'product_condition', 'purchase_date',
            'customer', 'customer_username', 'rating',
            'comment', 'date_posted', 'is_admin_review'
        )
        read_only_fields = (
            'id', 'customer', 'date_posted', 'is_admin_review',
            'video_file_url', 'review_image_url'
        )

    def get_video_file_url(self, obj):
        """Returns the full URL to the uploaded video file with optimization."""
        if obj.video_file:
            from .cloudinary_utils import get_video_url
            # Return optimized video URL from Cloudinary
            return get_video_url(obj.video_file)
        return None

    def to_representation(self, instance):
        """Override to return optimized review_image URL in response."""
        representation = super().to_representation(instance)
        if instance.review_image:
            from .cloudinary_utils import get_optimized_image_url
            optimized_url = get_optimized_image_url(
                instance.review_image,
                width=700,
                height=900,
                crop='fill'
            )
            if optimized_url:
                representation['review_image'] = optimized_url
        return representation

    def create(self, validated_data):
        review_image = validated_data.pop('review_image', None)
        video_file = validated_data.pop('video_file', None)

        review = super().create(validated_data)

        if review_image:
            from .cloudinary_utils import upload_image_to_cloudinary
            saved_name, _ = upload_image_to_cloudinary(review_image, 'review_images')
            if saved_name:
                review.review_image.name = saved_name

        if video_file:
            from .cloudinary_utils import upload_video_to_cloudinary
            saved_name, _ = upload_video_to_cloudinary(video_file, 'review_videos')
            if saved_name:
                review.video_file.name = saved_name

        if review_image or video_file:
            review.save()

        return review

    def update(self, instance, validated_data):
        review_image = validated_data.pop('review_image', None)
        video_file = validated_data.pop('video_file', None)

        instance = super().update(instance, validated_data)

        if review_image is not None:
            if review_image:
                from .cloudinary_utils import upload_image_to_cloudinary
                saved_name, _ = upload_image_to_cloudinary(review_image, 'review_images')
                if saved_name:
                    instance.review_image.name = saved_name
            else:
                instance.review_image = None

        if video_file is not None:
            if video_file:
                from .cloudinary_utils import upload_video_to_cloudinary
                saved_name, _ = upload_video_to_cloudinary(video_file, 'review_videos')
                if saved_name:
                    instance.video_file.name = saved_name
            else:
                instance.video_file = None

        if review_image is not None or video_file is not None:
            instance.save()

        return instance

    def get_review_image_url(self, obj):
        """Return optimized review image URL (prefer Cloudinary, fallback to constructed URL)."""
        if obj.review_image:
            from .cloudinary_utils import get_optimized_image_url
            import os
            import cloudinary
            from cloudinary import CloudinaryImage

            original_url = obj.review_image.url

            # If already a Cloudinary URL, optimize it and return
            if 'cloudinary.com' in original_url or 'res.cloudinary.com' in original_url:
                cloudinary_url = get_optimized_image_url(obj.review_image, width=700, height=900, crop='fill')
                return cloudinary_url if cloudinary_url else original_url

            # If URL is local, try to construct Cloudinary URL from image name
            is_local_path = (
                original_url.startswith('/media/') or original_url.startswith('/static/') or
                '/media/' in original_url or '/static/' in original_url
            )
            if is_local_path and hasattr(obj.review_image, 'name') and obj.review_image.name:
                try:
                    cloudinary.config(
                        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
                        api_key=os.environ.get('CLOUDINARY_API_KEY'),
                        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
                        secure=True
                    )
                    public_id = obj.review_image.name
                    if '.' in public_id:
                        public_id = public_id.rsplit('.', 1)[0]
                    cloudinary_img = CloudinaryImage(public_id)
                    return cloudinary_img.build_url(width=700, height=900, crop='fill')
                except Exception:
                    return None
        return None

    def validate_review_image(self, value):
        """Block uploads if Cloudinary storage is not configured."""
        if value is None:
            return value
        from django.conf import settings
        cloudinary_enabled = bool(getattr(settings, 'CLOUDINARY_ENABLED', False))
        if not cloudinary_enabled:
            raise serializers.ValidationError(
                "Cloudinary storage is not configured. Image uploads are disabled."
            )
        return value

    def validate_video_file(self, value):
        """Block uploads if Cloudinary storage is not configured."""
        if value is None:
            return value
        from django.conf import settings
        cloudinary_enabled = bool(getattr(settings, 'CLOUDINARY_ENABLED', False))
        if not cloudinary_enabled:
            raise serializers.ValidationError(
                "Cloudinary storage is not configured. Video uploads are disabled."
            )
        return value

class OrderItemSerializer(serializers.ModelSerializer):
    """
    Nested serializer for displaying OrderItems.
    """
    product_template_name = serializers.CharField(source='inventory_unit.product_template.product_name', read_only=True)
    serial_number = serializers.CharField(source='inventory_unit.serial_number', read_only=True, allow_null=True)
    imei = serializers.CharField(source='inventory_unit.imei', read_only=True, allow_null=True)
    unit_id = serializers.IntegerField(source='inventory_unit.id', read_only=True, allow_null=True)
    sub_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    # This field accepts the ID from the client and resolves it to the InventoryUnit instance.
    # It passes the resolved instance under the key 'inventory_unit' to the parent create() method.
    inventory_unit_id = serializers.PrimaryKeyRelatedField(
        queryset=InventoryUnit.objects.all(), 
        source='inventory_unit', write_only=True, required=True
    )
    
    class Meta:
        model = OrderItem
        fields = (
            'id', 'inventory_unit', 'inventory_unit_id', 'unit_id', 'product_template_name', 
            'serial_number', 'imei', 'quantity', 'unit_price_at_purchase', 'sub_total'
        )
        # FIX: Removed 'inventory_unit' from read_only_fields. 
        # The 'inventory_unit_id' field handles the write, and the 'inventory_unit' 
        # field (the model FK itself) is required internally for saving.
        read_only_fields = ('id', 'unit_id', 'serial_number', 'imei', 'unit_price_at_purchase') 

    # Note: If you want to calculate sub_total on the fly for viewing, you need a get_sub_total method,
    # but since the field is read-only, DRF will use the value stored in the database.


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer for the Order model. Handles nested creation of OrderItems, 
    inventory management, and total calculation.
    """
    # Use 'order_items' for both input and output (related_name='order_items' on OrderItem model)
    order_items = OrderItemSerializer(many=True, required=True)
    
    # Read-only fields for display
    user = UserSerializer(read_only=True)
    customer_username = serializers.SerializerMethodField(read_only=True)
    customer_phone = serializers.SerializerMethodField(read_only=True)
    delivery_address = serializers.SerializerMethodField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    order_source = serializers.CharField(required=False)  # Writable for creation, set by view
    order_source_display = serializers.CharField(source='get_order_source_display', read_only=True)
    brand = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
    brand_name = serializers.SerializerMethodField(read_only=True)
    
    def get_customer_username(self, obj):
        """Get customer username, handling None user."""
        if obj.customer and obj.customer.user:
            return obj.customer.user.username
        return obj.customer.name if obj.customer else None
    
    def get_customer_phone(self, obj):
        """Get customer phone number - prefer from source_lead for online orders, otherwise from customer."""
        # For online orders, get phone from the lead
        if hasattr(obj, 'source_lead') and obj.source_lead:
            return obj.source_lead.customer_phone or ''
        # Otherwise, get from customer
        if obj.customer:
            return obj.customer.phone or obj.customer.phone_number or ''
        return ''
    
    def get_delivery_address(self, obj):
        """Get delivery address - prefer from source_lead for online orders, otherwise from customer."""
        # For online orders, get address from the lead
        if hasattr(obj, 'source_lead') and obj.source_lead:
            return obj.source_lead.delivery_address or ''
        # Otherwise, get from customer
        if obj.customer:
            return obj.customer.delivery_address or obj.customer.address or ''
        return ''
    
    def get_brand_name(self, obj):
        """Get brand name, handling None brand."""
        return obj.brand.name if obj.brand else None
    
    class Meta:
        model = Order
        fields = (
            'order_id', 'user', 'customer', 'customer_username', 'customer_phone', 'delivery_address',
            'created_at', 'status', 'status_display', 'order_source', 'order_source_display',
            'total_amount', 'order_items', 'brand', 'brand_name'
        )
        read_only_fields = ('order_id', 'created_at', 'total_amount', 'customer', 'user')
    
    def __init__(self, *args, **kwargs):
        """Allow status updates for admin users"""
        super().__init__(*args, **kwargs)
        # Make status writable for updates (admin can update order status)
        if self.instance is not None:  # This is an update
            self.fields['status'].read_only = False
            # Make order_items read-only for updates (only status updates allowed)
            # This prevents validation errors when only status is being updated
            if 'order_items' in self.fields:
                self.fields['order_items'].read_only = True
                self.fields['order_items'].required = False

    def create(self, validated_data):
        # 1. Pop nested items and FKs set by the view
        # We pop the field mapped to the source: 'order_items'
        order_items_data = validated_data.pop('order_items')
        customer = validated_data.pop('customer') 
        user = validated_data.pop('user')         

        # 2. Use transaction to ensure atomic operations (inventory + order creation)
        with transaction.atomic():
            # Create the main Order object
            order = Order.objects.create(customer=customer, user=user, status=Order.StatusChoices.PENDING, **validated_data)
            
            final_total = Decimal('0.00')

            for item_data in order_items_data:
                inventory_unit = item_data.get('inventory_unit') 
                quantity = item_data['quantity']

                if not inventory_unit:
                    raise serializers.ValidationError("Inventory Unit must be provided for an order item.")
                
                # For online orders (ONLINE source), allow AVAILABLE units and automatically reserve them
                # For walk-in orders, require RESERVED status (salesperson workflow)
                order_source = validated_data.get('order_source', Order.OrderSourceChoices.ONLINE)
                
                if inventory_unit.sale_status not in [
                    InventoryUnit.SaleStatusChoices.RESERVED,
                    InventoryUnit.SaleStatusChoices.PENDING_PAYMENT,  # Allow if already pending
                    InventoryUnit.SaleStatusChoices.AVAILABLE  # Allow AVAILABLE for online orders
                ]:
                    raise serializers.ValidationError(
                        f"Unit ID {inventory_unit.id} cannot be added to an order. "
                        f"Current status: {inventory_unit.get_sale_status_display()}. "
                        f"Unit must be AVAILABLE or RESERVED."
                    )
                
                # For online orders with AVAILABLE units, automatically reserve them
                if (order_source == Order.OrderSourceChoices.ONLINE and 
                    inventory_unit.sale_status == InventoryUnit.SaleStatusChoices.AVAILABLE):
                    inventory_unit.sale_status = InventoryUnit.SaleStatusChoices.RESERVED
                    inventory_unit.save(update_fields=['sale_status'])
                
                if inventory_unit.product_template.product_type != Product.ProductType.ACCESSORY:
                    # Unique item (Phone/Laptop/Tablet) - must have quantity 1
                    if quantity != 1:
                        raise serializers.ValidationError(
                            f"Unique item {inventory_unit.id} must have quantity 1."
                        )
                    
                    # Transition RESERVED → PENDING_PAYMENT for unique items (will be SOLD when payment confirmed)
                    if inventory_unit.sale_status == InventoryUnit.SaleStatusChoices.RESERVED:
                        inventory_unit.sale_status = InventoryUnit.SaleStatusChoices.PENDING_PAYMENT
                    inventory_unit.reserved_by = None  # Clear reservation
                    inventory_unit.reserved_until = None
                    inventory_unit.save()

                else:
                    # Accessory - check available quantity (don't deduct yet, wait for payment confirmation)
                    # Calculate available quantity: total quantity minus pending order quantities
                    from django.db.models import Sum
                    pending_orders_qty = OrderItem.objects.filter(
                        inventory_unit=inventory_unit,
                        order__status__in=[Order.StatusChoices.PENDING, Order.StatusChoices.PAID]
                    ).aggregate(total=Sum('quantity'))['total'] or 0
                    
                    available_qty = inventory_unit.quantity - pending_orders_qty
                    
                    if quantity > available_qty:
                        raise serializers.ValidationError(
                            f"Accessory unit {inventory_unit.id} only has {available_qty} available in stock "
                            f"(total: {inventory_unit.quantity}, reserved: {pending_orders_qty}), "
                            f"but {quantity} were requested."
                        )
                    
                    # For accessories: Don't decrement quantity when order is created
                    # Keep quantity as is, and keep status as AVAILABLE if quantity > 0
                    # The ordered quantity is "reserved" via the OrderItem record
                    # When payment is confirmed, quantity will be decremented
                    inventory_unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                    
                    # Clear reservation info for accessories
                    inventory_unit.reserved_by = None
                    inventory_unit.reserved_until = None
                    inventory_unit.save()
                
                # Create the OrderItem
                unit_price = inventory_unit.selling_price
                sub_total = unit_price * quantity
                
                OrderItem.objects.create(
                    order=order,
                    inventory_unit=inventory_unit,
                    quantity=quantity,
                    unit_price_at_purchase=unit_price 
                )
                
                final_total += sub_total
                
            # Update the order total and save it
            order.total_amount = final_total
            order.save()
            
            return order
    
    def update(self, instance, validated_data):
        """
        Handle order updates. For status-only updates, order_items is not required.
        The viewset's perform_update will handle the actual save and any special logic.
        """
        # Update status if provided (this will be saved by serializer.save() in perform_update)
        if 'status' in validated_data:
            instance.status = validated_data['status']
        
        # If order_items are provided, we could handle updating them here in the future
        # For now, we just update the status
        
        # Return the instance - serializer.save() will be called by perform_update
        return instance


# -------------------------------------------------------------------------
# REQUEST MANAGEMENT SERIALIZERS
# -------------------------------------------------------------------------

class ReservationRequestSerializer(serializers.ModelSerializer):
    """Serializer for ReservationRequest model."""
    requesting_salesperson_username = serializers.CharField(source='requesting_salesperson.user.username', read_only=True)
    requesting_salesperson_brands = serializers.SerializerMethodField()
    # Legacy single unit fields (for backward compatibility)
    inventory_unit_name = serializers.SerializerMethodField()
    inventory_unit_id = serializers.PrimaryKeyRelatedField(
        queryset=InventoryUnit.objects.all(),
        source='inventory_unit',
        write_only=True,
        required=False,
        allow_null=True
    )
    # New multiple units fields
    inventory_unit_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=InventoryUnit.objects.all(),
        source='inventory_units',
        write_only=True,
        required=False
    )
    inventory_units_details = serializers.SerializerMethodField()
    approved_by_username = serializers.CharField(source='approved_by.user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = ReservationRequest
        fields = (
            'id', 'requesting_salesperson', 'requesting_salesperson_username', 'requesting_salesperson_brands',
            'inventory_unit', 'inventory_unit_id', 'inventory_unit_name',  # Legacy
            'inventory_units', 'inventory_unit_ids', 'inventory_units_details',  # New
            'status', 'status_display', 'requested_at', 'approved_at', 
            'expires_at', 'approved_by', 'approved_by_username', 'notes'
        )
        read_only_fields = ('id', 'requesting_salesperson', 'inventory_unit', 'inventory_units', 'requested_at', 'approved_at', 'expires_at', 'approved_by')
        # Note: 'status' is NOT in read_only_fields so it can be updated for approval/rejection
        extra_kwargs = {
            'status': {'required': False},
            'notes': {'required': False},
        }
    
    def get_requesting_salesperson_brands(self, obj):
        """Get brands associated with the requesting salesperson."""
        if not obj.requesting_salesperson:
            return []
        brands = obj.requesting_salesperson.brands.all()
        return [
            {
                'id': brand.id,
                'code': brand.code,
                'name': brand.name,
                'is_active': brand.is_active,
                'ecommerce_domain': brand.ecommerce_domain or '',
            }
            for brand in brands
        ]
    
    def get_inventory_unit_name(self, obj):
        """Get name of first unit (for backward compatibility)."""
        if obj.inventory_units.exists():
            return obj.inventory_units.first().product_template.product_name
        elif obj.inventory_unit:
            return obj.inventory_unit.product_template.product_name
        return None
    
    def get_inventory_units_details(self, obj):
        """Get detailed information about all units in the request."""
        units = []
        # Use new ManyToMany field
        for unit in obj.inventory_units.all():
            units.append({
                'id': unit.id,
                'product_name': unit.product_template.product_name,
                'serial_number': unit.serial_number,
                'condition': unit.condition,
                'grade': unit.grade,
                'selling_price': str(unit.selling_price),
                'sale_status': unit.sale_status,
                'sale_status_display': unit.get_sale_status_display(),
            })
        # Fallback to old single unit field during migration
        if not units and obj.inventory_unit:
            units.append({
                'id': obj.inventory_unit.id,
                'product_name': obj.inventory_unit.product_template.product_name,
                'serial_number': obj.inventory_unit.serial_number,
                'condition': obj.inventory_unit.condition,
                'grade': obj.inventory_unit.grade,
                'selling_price': str(obj.inventory_unit.selling_price),
                'sale_status': obj.inventory_unit.sale_status,
                'sale_status_display': obj.inventory_unit.get_sale_status_display(),
            })
        return units
    
    def validate_inventory_unit_ids(self, value):
        """Validate all units are available for reservation."""
        if not value:
            raise serializers.ValidationError("At least one inventory unit must be specified.")
        
        # For updates, allow units that are already in this request
        current_request = getattr(self, 'instance', None)
        current_unit_ids = set()
        if current_request:
            current_unit_ids = set(current_request.inventory_units.values_list('id', flat=True))
        
        for unit in value:
            # Allow units that are already in this request
            if current_request and unit.id in current_unit_ids:
                continue
                
            if unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
                raise serializers.ValidationError(f"Unit {unit.id} is not available for reservation. Current status: {unit.get_sale_status_display()}")
            # Only check reserved_by if unit is not already in this request
            if unit.reserved_by and unit.reserved_by != (current_request.requesting_salesperson if current_request else None):
                raise serializers.ValidationError(f"Unit {unit.id} is already reserved by another salesperson.")
        return value
    
    def validate(self, attrs):
        """Validate that either inventory_unit_ids or inventory_unit_id is provided."""
        # Check if this is an update (instance exists)
        if self.instance:
            # For updates, allow partial data (PATCH)
            # If no units are provided, that's okay - we'll keep existing units
            logger.info(f"Update validation for request {self.instance.id}. Attrs keys: {list(attrs.keys())}")
            return attrs
        
        # For creates, require at least one unit
        inventory_unit_ids = attrs.get('inventory_units', [])
        inventory_unit_id = attrs.get('inventory_unit')
        
        if not inventory_unit_ids and not inventory_unit_id:
            raise serializers.ValidationError("At least one inventory unit must be specified.")
        
        return attrs
    
    def create(self, validated_data):
        """Auto-set requesting_salesperson from current user."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        
        # Ignore any status supplied during creation; reservations always start pending.
        validated_data.pop('status', None)
        validated_data['status'] = ReservationRequest.StatusChoices.PENDING
        
        try:
            admin = Admin.objects.get(user=request.user)
            validated_data['requesting_salesperson'] = admin
        except Admin.DoesNotExist:
            raise serializers.ValidationError("Admin profile required.")
        
        # Extract units (handle both old and new format)
        inventory_units = validated_data.pop('inventory_units', [])
        inventory_unit = validated_data.pop('inventory_unit', None)
        
        # Convert old single unit to list if needed
        if inventory_unit and not inventory_units:
            inventory_units = [inventory_unit]
        
        if not inventory_units:
            raise serializers.ValidationError("At least one inventory unit must be specified.")
        
        # Create new reservation request
        reservation_request = super().create(validated_data)
        
        # Add units to ManyToMany relationship
        reservation_request.inventory_units.set(inventory_units)
        
        # Also set old field for migration compatibility
        if inventory_unit:
            reservation_request.inventory_unit = inventory_unit
            reservation_request.save(update_fields=['inventory_unit'])
        
        # Send notifications to inventory managers and superusers
        # Wrap in try-except to prevent notification errors from breaking request creation
        try:
            # Get first unit for notification (or use old field)
            first_unit = reservation_request.inventory_units.first() or reservation_request.inventory_unit
            if not first_unit:
                return reservation_request
                
            salesperson = reservation_request.requesting_salesperson
            unit_count = reservation_request.inventory_units.count() or (1 if reservation_request.inventory_unit else 0)
            product_name = first_unit.product_template.product_name
            serial_number = first_unit.serial_number or f"Unit #{first_unit.id}"
            salesperson_name = salesperson.user.username
            
            # Create notification message
            if unit_count == 1:
                message = f"{product_name} (SN: {serial_number}) requested by {salesperson_name}. Review and approve if needed."
            else:
                message = f"{unit_count} units requested by {salesperson_name}. Review and approve if needed."
            
            # Notify all Inventory Managers
            managers = Admin.objects.filter(
                roles__name=AdminRole.RoleChoices.INVENTORY_MANAGER
            ).select_related('user')
            
            manager_count = managers.count()
            logger.info(f"Creating notifications for reservation request {reservation_request.id}. Found {manager_count} inventory managers.")
            
            if manager_count == 0:
                logger.warning(f"No inventory managers found to notify for reservation request {reservation_request.id}")
            
            for manager in managers:
                try:
                    Notification.objects.create(
                        recipient=manager.user,
                        notification_type=Notification.NotificationType.REQUEST_PENDING_APPROVAL,
                        title="New Reservation Request",
                        message=message,
                        content_type=ContentType.objects.get_for_model(ReservationRequest),
                        object_id=reservation_request.id
                    )
                    logger.info(f"Notification created for inventory manager: {manager.user.username}")
                except Exception as e:
                    # Log error but don't break the request creation
                    logger.error(f"Failed to create notification for manager {manager.user.username}: {e}", exc_info=True)
            
            # Also notify superusers
            superusers = User.objects.filter(is_superuser=True)
            superuser_count = superusers.count()
            logger.info(f"Found {superuser_count} superusers to notify.")
            
            if superuser_count == 0:
                logger.warning(f"No superusers found to notify for reservation request {reservation_request.id}")
            
            for superuser in superusers:
                try:
                    Notification.objects.create(
                        recipient=superuser,
                        notification_type=Notification.NotificationType.REQUEST_PENDING_APPROVAL,
                        title="New Reservation Request",
                        message=message,
                        content_type=ContentType.objects.get_for_model(ReservationRequest),
                        object_id=reservation_request.id
                    )
                    logger.info(f"Notification created for superuser: {superuser.username}")
                except Exception as e:
                    # Log error but don't break the request creation
                    logger.error(f"Failed to create notification for superuser {superuser.username}: {e}", exc_info=True)
        except Exception as e:
            # Log error but don't break the request creation
            logger.error(f"Failed to create notifications for reservation request {reservation_request.id}: {e}", exc_info=True)
        
        return reservation_request
    
    def update(self, instance, validated_data):
        """Update reservation request - allow editing units and notes for PENDING requests."""
        try:
            logger.info(f"Updating reservation request {instance.id}. Status: {instance.status}, Validated data keys: {list(validated_data.keys())}")
            
            # Only allow editing units and notes if status is PENDING
            if instance.status != ReservationRequest.StatusChoices.PENDING:
                # For non-pending requests, only allow notes updates
                if 'notes' in validated_data:
                    instance.notes = validated_data['notes']
                    instance.save(update_fields=['notes'])
                return instance
            
            # Extract units
            inventory_units = validated_data.pop('inventory_units', None)
            inventory_unit = validated_data.pop('inventory_unit', None)
            
            logger.info(f"Extracted units: inventory_units={inventory_units is not None}, inventory_unit={inventory_unit is not None}")
            
            # Update units if provided
            if inventory_units is not None:
                # Get current unit IDs to allow keeping existing units
                current_unit_ids = set(instance.inventory_units.values_list('id', flat=True))
                logger.info(f"Current unit IDs in request: {current_unit_ids}")
                
                # Validate all units (allow units already in this request, even if RESERVED by same salesperson)
                for unit in inventory_units:
                    logger.info(f"Validating unit {unit.id}, status: {unit.sale_status}, reserved_by: {unit.reserved_by}, requesting_salesperson: {instance.requesting_salesperson.id if instance.requesting_salesperson else None}")
                    # Allow units that are already in this request (regardless of status, as long as reserved by same salesperson)
                    if unit.id in current_unit_ids:
                        # If unit is already in request, allow it even if RESERVED (as long as it's reserved by the same salesperson)
                        if unit.reserved_by == instance.requesting_salesperson:
                            logger.info(f"Unit {unit.id} is already in request and reserved by same salesperson, allowing")
                            continue
                        else:
                            # Unit is in request but reserved by someone else - this shouldn't happen, but handle it
                            logger.warning(f"Unit {unit.id} is in request but reserved by different salesperson")
                            continue
                        
                    # For new units, they must be AVAILABLE
                    if unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
                        raise serializers.ValidationError(f"Unit {unit.id} is not available for reservation. Current status: {unit.get_sale_status_display()}")
                    # Check if unit is reserved by another salesperson
                    if unit.reserved_by and unit.reserved_by != instance.requesting_salesperson:
                        raise serializers.ValidationError(f"Unit {unit.id} is already reserved by another salesperson.")
                
                logger.info(f"Setting {len(inventory_units)} units on request {instance.id}")
                instance.inventory_units.set(inventory_units)
            
            # Handle old single unit format
            if inventory_unit:
                if inventory_unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
                    raise serializers.ValidationError(f"Unit {inventory_unit.id} is not available for reservation.")
                instance.inventory_units.set([inventory_unit])
                instance.inventory_unit = inventory_unit
            
            # Update other fields
            if 'notes' in validated_data:
                instance.notes = validated_data['notes']
            
            logger.info(f"Saving reservation request {instance.id}")
            instance.save()
            logger.info(f"Successfully updated reservation request {instance.id}")
            return instance
        except Exception as e:
            import traceback
            logger.error(f"Error updating reservation request {instance.id}: {str(e)}\n{traceback.format_exc()}")
            raise


class ReturnRequestSerializer(serializers.ModelSerializer):
    """Serializer for ReturnRequest model (bulk returns)."""
    transfer_history = serializers.SerializerMethodField(read_only=True)
    net_holdings_info = serializers.SerializerMethodField(read_only=True)
    requesting_salesperson_username = serializers.CharField(source='requesting_salesperson.user.username', read_only=True)
    approved_by_username = serializers.CharField(source='approved_by.user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    inventory_units_count = serializers.SerializerMethodField()
    inventory_units_detail = serializers.SerializerMethodField()
    inventory_units = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    unit_ids = serializers.PrimaryKeyRelatedField(
        queryset=InventoryUnit.objects.all(),
        source='inventory_units',
        many=True,
        write_only=True,
        required=False
    )
    
    class Meta:
        model = ReturnRequest
        fields = (
            'id', 'requesting_salesperson', 'requesting_salesperson_username', 'inventory_units', 'unit_ids',
            'inventory_units_count', 'inventory_units_detail', 'transfer_history', 'net_holdings_info',
            'status', 'status_display',
            'requested_at', 'approved_at', 'approved_by', 'approved_by_username', 'notes'
        )
        read_only_fields = ('id', 'requesting_salesperson', 'requested_at', 'approved_at', 'approved_by')
    
    def get_inventory_units_count(self, obj):
        """Return count of units in this return request."""
        return obj.inventory_units.count()
    
    def get_inventory_units_detail(self, obj):
        """Return basic info about units in this return request."""
        return [
            {
                'id': unit.id,
                'product_name': unit.product_template.product_name,
                'serial_number': unit.serial_number,
            }
            for unit in obj.inventory_units.all()
        ]
    
    def get_transfer_history(self, obj):
        """Get transfer history for units in this return request."""
        from .models import UnitTransfer
        salesperson = obj.requesting_salesperson
        
        # Get all transfers involving this salesperson and the units in this return request
        unit_ids = list(obj.inventory_units.values_list('id', flat=True))
        
        transfers = UnitTransfer.objects.filter(
            inventory_unit__in=unit_ids
        ).select_related(
            'from_salesperson__user', 'to_salesperson__user', 'inventory_unit__product_template'
        ).order_by('-requested_at')
        
        return [
            {
                'id': transfer.id,
                'unit_id': transfer.inventory_unit.id,
                'unit_name': transfer.inventory_unit.product_template.product_name,
                'from_salesperson': transfer.from_salesperson.user.username,
                'to_salesperson': transfer.to_salesperson.user.username,
                'status': transfer.status,
                'status_display': transfer.get_status_display(),
                'requested_at': transfer.requested_at,
                'approved_at': transfer.approved_at,
            }
            for transfer in transfers
        ]
    
    def get_net_holdings_info(self, obj):
        """Calculate net holdings for the requesting salesperson."""
        from .models import UnitTransfer
        salesperson = obj.requesting_salesperson
        
        # Units directly reserved (via reservation requests)
        directly_reserved = InventoryUnit.objects.filter(
            reserved_by=salesperson,
            sale_status=InventoryUnit.SaleStatusChoices.RESERVED
        ).count()
        
        # Units received via approved transfers
        received_via_transfer = UnitTransfer.objects.filter(
            to_salesperson=salesperson,
            status=UnitTransfer.StatusChoices.APPROVED
        ).count()
        
        # Units transferred out (approved transfers)
        transferred_out = UnitTransfer.objects.filter(
            from_salesperson=salesperson,
            status=UnitTransfer.StatusChoices.APPROVED
        ).count()
        
        # Net holdings
        net_holdings = directly_reserved + received_via_transfer - transferred_out
        
        return {
            'directly_reserved': directly_reserved,
            'received_via_transfer': received_via_transfer,
            'transferred_out': transferred_out,
            'net_holdings': net_holdings,
        }
    
    def validate_unit_ids(self, value):
        """Ensure all units are RESERVED and reserved by the requesting admin."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        
        try:
            admin = Admin.objects.get(user=request.user)
        except Admin.DoesNotExist:
            raise serializers.ValidationError("Admin profile required.")
        
        for unit in value:
            # Explicitly check if unit is sold - cannot return sold items
            if unit.sale_status == InventoryUnit.SaleStatusChoices.SOLD:
                raise serializers.ValidationError(
                    f"Unit {unit.id} has been sold and cannot be returned."
                )
            if unit.sale_status != InventoryUnit.SaleStatusChoices.RESERVED:
                raise serializers.ValidationError(
                    f"Unit {unit.id} is not RESERVED. Only reserved units can be returned."
                )
            if unit.reserved_by != admin:
                raise serializers.ValidationError(
                    f"Unit {unit.id} is reserved by another salesperson. You can only return units you have reserved."
                )
        
        return value
    
    def create(self, validated_data):
        """Auto-set requesting_salesperson and handle bulk return creation."""
        request = self.context.get('request')
        try:
            admin = Admin.objects.get(user=request.user)
            validated_data['requesting_salesperson'] = admin
        except Admin.DoesNotExist:
            raise serializers.ValidationError("Admin profile required.")
        
        # If no units specified, get all reserved units for this admin
        units_data = validated_data.pop('inventory_units', [])
        if not units_data:
            # Bulk return all reserved units
            reserved_units = InventoryUnit.objects.filter(
                reserved_by=admin,
                sale_status=InventoryUnit.SaleStatusChoices.RESERVED
            )
            units_data = list(reserved_units)
        
        return_request = super().create(validated_data)
        return_request.inventory_units.set(units_data)
        return return_request


class UnitTransferSerializer(serializers.ModelSerializer):
    """Serializer for UnitTransfer model."""
    from_salesperson_username = serializers.CharField(source='from_salesperson.user.username', read_only=True)
    to_salesperson_username = serializers.CharField(source='to_salesperson.user.username', read_only=True)
    approved_by_username = serializers.CharField(source='approved_by.user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    inventory_unit_name = serializers.CharField(source='inventory_unit.product_template.product_name', read_only=True)
    inventory_unit_id = serializers.PrimaryKeyRelatedField(
        queryset=InventoryUnit.objects.filter(sale_status=InventoryUnit.SaleStatusChoices.RESERVED),
        source='inventory_unit',
        write_only=True
    )
    to_salesperson_id = serializers.PrimaryKeyRelatedField(
        queryset=Admin.objects.filter(roles__name=AdminRole.RoleChoices.SALESPERSON),
        source='to_salesperson',
        write_only=True
    )
    
    class Meta:
        model = UnitTransfer
        fields = (
            'id', 'inventory_unit', 'inventory_unit_id', 'inventory_unit_name',
            'from_salesperson', 'from_salesperson_username',
            'to_salesperson', 'to_salesperson_id', 'to_salesperson_username',
            'status', 'status_display', 'requested_at', 'approved_at',
            'approved_by', 'approved_by_username', 'notes'
        )
        read_only_fields = ('id', 'from_salesperson', 'requested_at', 'approved_at', 'approved_by', 'status')
    
    def validate_inventory_unit_id(self, value):
        """Ensure unit is RESERVED."""
        if value.sale_status != InventoryUnit.SaleStatusChoices.RESERVED:
            raise serializers.ValidationError("Only RESERVED units can be transferred.")
        return value
    
    def validate_to_salesperson_id(self, value):
        """Ensure target is a salesperson."""
        if not value.is_salesperson:
            raise serializers.ValidationError("Target admin must have Salesperson role.")
        return value
    
    def validate(self, data):
        """Ensure from_salesperson is different from to_salesperson."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        
        try:
            from_admin = Admin.objects.get(user=request.user)
        except Admin.DoesNotExist:
            raise serializers.ValidationError("Admin profile required.")
        
        inventory_unit = data.get('inventory_unit') or self.instance.inventory_unit if self.instance else None
        to_salesperson = data.get('to_salesperson')
        
        if inventory_unit:
            if inventory_unit.reserved_by != from_admin:
                raise serializers.ValidationError({
                    'inventory_unit_id': "You can only transfer units that you have reserved."
                })
        
        if to_salesperson and from_admin.id == to_salesperson.id:
            raise serializers.ValidationError({
                'to_salesperson_id': "Cannot transfer unit to yourself."
            })
        
        return data
    
    def create(self, validated_data):
        """Auto-set from_salesperson from current user."""
        request = self.context.get('request')
        try:
            admin = Admin.objects.get(user=request.user)
            validated_data['from_salesperson'] = admin
        except Admin.DoesNotExist:
            raise serializers.ValidationError("Admin profile required.")
        
        return super().create(validated_data)


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    recipient_username = serializers.CharField(source='recipient.username', read_only=True)
    
    class Meta:
        model = Notification
        fields = (
            'id', 'recipient', 'recipient_username', 'notification_type', 'notification_type_display',
            'title', 'message', 'is_read', 'created_at', 'content_type', 'object_id'
        )
        read_only_fields = ('id', 'recipient', 'created_at')


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model (read-only)."""
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True, allow_null=True)
    user_email = serializers.CharField(source='user.email', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = (
            'id', 'user', 'user_username', 'user_email', 'action', 'action_display',
            'model_name', 'object_id', 'object_repr', 'old_value', 'new_value',
            'ip_address', 'user_agent', 'timestamp'
        )
        read_only_fields = fields  # All fields are read-only


# -------------------------------------------------------------------------
# BRAND & LEAD SERIALIZERS
# -------------------------------------------------------------------------

class BrandSerializer(serializers.ModelSerializer):
    """Serializer for Brand model."""
    logo_url = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Brand
        fields = (
            'id', 'code', 'name', 'description', 'is_active', 'logo', 'logo_url', 'primary_color',
            'ecommerce_domain', 'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at', 'logo_url')
    
    def get_logo_url(self, obj):
        """Return optimized logo URL with Cloudinary transformations"""
        if obj.logo:
            from .cloudinary_utils import get_optimized_image_url
            # Logo optimized for display (typically 200x200 or similar)
            return get_optimized_image_url(obj.logo, width=200, height=200, crop='fill')
        return None

    def create(self, validated_data):
        logo = validated_data.pop('logo', None)
        instance = super().create(validated_data)

        if logo:
            from .cloudinary_utils import upload_image_to_cloudinary
            saved_name, _ = upload_image_to_cloudinary(logo, 'brand_logos')
            if saved_name:
                instance.logo.name = saved_name
                instance.save()

        return instance

    def update(self, instance, validated_data):
        logo = validated_data.pop('logo', None)
        instance = super().update(instance, validated_data)

        if logo is not None:
            if logo:
                from .cloudinary_utils import upload_image_to_cloudinary
                saved_name, _ = upload_image_to_cloudinary(logo, 'brand_logos')
                if saved_name:
                    instance.logo.name = saved_name
            else:
                instance.logo = None
            instance.save()

        return instance


class LeadItemSerializer(serializers.ModelSerializer):
    """Serializer for LeadItem (admin)."""
    product_name = serializers.CharField(source='inventory_unit.product_template.product_name', read_only=True)
    unit_id = serializers.IntegerField(source='inventory_unit.id', read_only=True)
    
    class Meta:
        model = LeadItem
        fields = ('id', 'inventory_unit', 'unit_id', 'product_name', 'quantity', 'unit_price')
        read_only_fields = ('id', 'product_name', 'unit_id')


class LeadSerializer(serializers.ModelSerializer):
    """Serializer for Lead model (admin)."""
    items = LeadItemSerializer(many=True, read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assigned_salesperson_name = serializers.CharField(
        source='assigned_salesperson.user.username',
        read_only=True,
        allow_null=True
    )
    order_id = serializers.UUIDField(source='order.order_id', read_only=True, allow_null=True)
    customer_name_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Lead
        fields = (
            'id', 'lead_reference', 'customer_name', 'customer_phone', 'customer_email',
            'delivery_address', 'customer', 'brand', 'brand_name', 'submitted_at',
            'status', 'status_display', 'assigned_salesperson', 'assigned_salesperson_name',
            'contacted_at', 'converted_at', 'order', 'order_id', 'salesperson_notes',
            'customer_notes', 'total_value', 'expires_at', 'items', 'customer_name_display'
        )
        read_only_fields = (
            'lead_reference', 'submitted_at', 'converted_at', 'order_id'
        )
    
    def get_customer_name_display(self, obj):
        """Get customer name for display."""
        if obj.customer:
            return obj.customer.name or (obj.customer.user.username if obj.customer.user else 'Unknown')
        return obj.customer_name


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for CartItem (admin)."""
    product_name = serializers.CharField(source='inventory_unit.product_template.product_name', read_only=True)
    
    class Meta:
        model = CartItem
        fields = ('id', 'inventory_unit', 'product_name', 'quantity', 'added_at')
        read_only_fields = ('added_at',)


class CartSerializer(serializers.ModelSerializer):
    """Serializer for Cart (admin)."""
    items = CartItemSerializer(many=True, read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    total_value = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = (
            'id', 'session_key', 'customer', 'brand', 'brand_name',
            'customer_name', 'customer_phone', 'customer_email', 'delivery_address',
            'is_submitted', 'lead', 'created_at', 'updated_at', 'expires_at',
            'items', 'total_value'
        )
        read_only_fields = ('created_at', 'updated_at')
    
    def get_total_value(self, obj):
        total = Decimal('0.00')
        for item in obj.items.all():
            total += item.inventory_unit.selling_price * item.quantity
        return float(total)


# -------------------------------------------------------------------------
# PROMOTION SERIALIZERS
# -------------------------------------------------------------------------

class PromotionTypeSerializer(serializers.ModelSerializer):
    """Serializer for PromotionType model."""
    
    class Meta:
        from inventory.models import PromotionType
        model = PromotionType
        fields = ('id', 'name', 'code', 'description', 'is_active', 'display_order', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')


class PromotionSerializer(serializers.ModelSerializer):
    """Serializer for Promotion model (admin)."""
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    promotion_type_name = serializers.CharField(source='promotion_type.name', read_only=True)
    promotion_type_code = serializers.CharField(source='promotion_type.code', read_only=True)
    is_currently_active = serializers.BooleanField(read_only=True)
    product_count = serializers.SerializerMethodField()
    banner_image_url = serializers.SerializerMethodField(read_only=True)
    # banner_image is the model field (ImageField) - writable for uploads
    # We override to_representation to return optimized URL instead of raw URL
    banner_image = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = Promotion
        fields = (
            'id', 'brand', 'brand_name', 'promotion_type', 'promotion_type_name', 'promotion_type_code',
            'title', 'description', 'banner_image', 'banner_image_url', 'promotion_code', 'display_locations',
            'carousel_position', 'discount_percentage', 'discount_amount', 'start_date', 'end_date',
            'is_active', 'is_currently_active', 'products', 'product_types',
            'created_by', 'created_at', 'updated_at', 'product_count'
        )
        read_only_fields = ('created_at', 'updated_at', 'is_currently_active', 'product_count', 'banner_image_url')
    
    def to_representation(self, instance):
        """Override to return optimized banner_image URL in response."""
        representation = super().to_representation(instance)
        if instance.banner_image:
            # Replace the raw URL with optimized Cloudinary URL
            from .cloudinary_utils import get_optimized_image_url
            optimized_url = get_optimized_image_url(
                instance.banner_image, 
                width=1080, 
                height=1920, 
                crop='fill'
            )
            if optimized_url:
                representation['banner_image'] = optimized_url
        return representation

    def create(self, validated_data):
        banner_image = validated_data.pop('banner_image', None)
        instance = super().create(validated_data)

        if banner_image:
            from .cloudinary_utils import upload_image_to_cloudinary
            saved_name, _ = upload_image_to_cloudinary(banner_image, 'promotions')
            if saved_name:
                instance.banner_image.name = saved_name
                instance.save()

        return instance

    def update(self, instance, validated_data):
        banner_image = validated_data.pop('banner_image', None)
        instance = super().update(instance, validated_data)

        if banner_image is not None:
            if banner_image:
                from .cloudinary_utils import upload_image_to_cloudinary
                saved_name, _ = upload_image_to_cloudinary(banner_image, 'promotions')
                if saved_name:
                    instance.banner_image.name = saved_name
            else:
                instance.banner_image = None
            instance.save()

        return instance
    
    def get_banner_image(self, obj):
        """Return optimized banner image URL (prefer Cloudinary, fallback to absolute URL)"""
        if obj.banner_image:
            from .cloudinary_utils import get_optimized_image_url
            import os
            import cloudinary
            from cloudinary import CloudinaryImage
            from django.core.files.storage import default_storage
            request = self.context.get('request')
            
            # Check if the storage backend is Cloudinary
            is_cloudinary_storage = 'cloudinary' in str(type(default_storage)).lower()
            
            # Get the URL from the field - Cloudinary storage should return Cloudinary URL
            original_url = obj.banner_image.url
            
            # If already a Cloudinary URL, optimize it and return
            if 'cloudinary.com' in original_url or 'res.cloudinary.com' in original_url:
                cloudinary_url = get_optimized_image_url(obj.banner_image, width=1080, height=1920, crop='fill')
                return cloudinary_url if cloudinary_url else original_url
            
            # If URL is local (relative or absolute), try to construct Cloudinary URL from image name
            # This handles cases where images were uploaded before Cloudinary was configured
            is_local_path = (original_url.startswith('/media/') or original_url.startswith('/static/') or 
                           '/media/' in original_url or '/static/' in original_url)
            # Always try Cloudinary URL construction if we detect a local path
            # This handles images uploaded before Cloudinary was configured
            if is_local_path:
                if hasattr(obj.banner_image, 'name') and obj.banner_image.name:
                    try:
                        # Configure Cloudinary
                        cloudinary.config(
                            cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
                            api_key=os.environ.get('CLOUDINARY_API_KEY'),
                            api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
                            secure=True
                        )
                        
                        # Get public_id from the image field name
                        # IMPORTANT: django-cloudinary-storage stores files with 'media/' prefix
                        # because of MEDIA_URL='/media/' in settings
                        # DO NOT remove it - it's part of the actual Cloudinary public_id
                        public_id = obj.banner_image.name
                        
                        # Keep 'media/' prefix if present - it's part of the Cloudinary public_id
                        # django-cloudinary-storage uploads files with 'media/' prefix
                        
                        # Remove file extension for Cloudinary public_id
                        if '.' in public_id:
                            public_id = public_id.rsplit('.', 1)[0]
                        
                        # Try to build Cloudinary URL
                        cloudinary_img = CloudinaryImage(public_id)
                        cloudinary_url = cloudinary_img.build_url(transformation=[
                            {'width': 1080, 'height': 1920, 'crop': 'fill', 'quality': 'auto'}
                            # Removed 'format': 'auto' - Cloudinary handles auto-format automatically
                        ])
                        
                        # Verify it's a valid Cloudinary URL
                        if cloudinary_url and 'cloudinary.com' in cloudinary_url:
                            return cloudinary_url
                    except Exception as e:
                        # If Cloudinary construction fails, fall back to absolute URL
                        pass
            
            # If it's a local path, build absolute URL
            if (original_url.startswith('/media/') or original_url.startswith('/static/')) and request:
                return request.build_absolute_uri(original_url)
            elif original_url.startswith('/media/') or original_url.startswith('/static/'):
                # Construct absolute URL manually if no request context
                host = os.environ.get('DJANGO_HOST', 'affordable-gadgets-backend.onrender.com')
                protocol = 'https'
                return f"{protocol}://{host}{original_url}"
            
            # Return the URL as-is (might already be absolute)
            return original_url
        return None
    
    def get_banner_image_url(self, obj):
        """Return optimized banner image URL with Cloudinary transformations"""
        # Use the same logic as get_banner_image
        return self.get_banner_image(obj)
    
    def get_product_count(self, obj):
        """Get count of products this promotion applies to."""
        # If product_types is set, count all products of that type for the brand
        if obj.product_types:
            from inventory.models import Product
            type_products = Product.objects.filter(
                product_type=obj.product_types,
                brands=obj.brand
            )
            # If both product_types and specific products are set,
            # return the type count (which represents all products of that type)
            return type_products.count()
        
        # Only specific products are set (no product_types)
        return obj.products.count()