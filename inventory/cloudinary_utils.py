"""
Utility functions for Cloudinary image and video transformations.
Provides helper methods to generate optimized URLs with transformations.
"""
import os
import cloudinary
import cloudinary.api


def _get_cloudinary_url_from_field(image_field):
    """
    Get Cloudinary URL from an image field, handling both Cloudinary storage and local storage.
    If the field has a public_id stored but URL is local, construct Cloudinary URL.
    For local files, return absolute URL.
    """
    if not image_field:
        return None
    
    base_url = image_field.url
    
    # If already a Cloudinary URL, return it
    if 'cloudinary.com' in base_url or 'res.cloudinary.com' in base_url:
        return base_url
    
    # If it's a local path, make it absolute
    if base_url.startswith('/media/') or base_url.startswith('/static/'):
        # Build absolute URL using Django settings
        from django.conf import settings
        request = getattr(image_field, '_request', None)
        if request:
            return request.build_absolute_uri(base_url)
        else:
            # Fallback: construct URL manually
            # In development, use localhost:8000
            host = os.environ.get('DJANGO_HOST', 'localhost:8000')
            protocol = 'https' if os.environ.get('DJANGO_USE_HTTPS', '').lower() == 'true' else 'http'
            return f"{protocol}://{host}{base_url}"
    
    # If it's a local path but we have the image name (which might be a public_id)
    # Try to construct Cloudinary URL
    if hasattr(image_field, 'name') and image_field.name:
        # Configure Cloudinary if not already configured
        try:
            cloudinary.config(
                cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
                api_key=os.environ.get('CLOUDINARY_API_KEY'),
                api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
                secure=True
            )
            
            # Check if the name looks like a Cloudinary public_id (no slashes at start, or has folder structure)
            public_id = image_field.name
            
            # Remove file extension if present (Cloudinary stores without extension)
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            # Build Cloudinary URL
            from cloudinary import CloudinaryImage
            cloudinary_img = CloudinaryImage(public_id)
            return cloudinary_img.build_url()
        except Exception:
            # If Cloudinary config fails, return the original URL as absolute
            if base_url.startswith('/'):
                host = os.environ.get('DJANGO_HOST', 'localhost:8000')
                protocol = 'https' if os.environ.get('DJANGO_USE_HTTPS', '').lower() == 'true' else 'http'
                return f"{protocol}://{host}{base_url}"
            pass
    
    return base_url


def get_optimized_image_url(image_field, width=None, height=None, quality='auto', format='auto', crop='fill'):
    """
    Get optimized image URL from Cloudinary with transformations.
    
    Args:
        image_field: Django ImageField instance
        width: Target width in pixels (optional)
        height: Target height in pixels (optional)
        quality: Image quality ('auto', 'best', 'good', 'eco', 'low', or number 1-100)
        format: Image format ('auto', 'jpg', 'png', 'webp', etc.)
        crop: Crop mode ('fill', 'fit', 'scale', 'thumb', etc.)
    
    Returns:
        Optimized Cloudinary URL string
    """
    if not image_field:
        return None
    
    # Get base Cloudinary URL
    base_url = _get_cloudinary_url_from_field(image_field)
    
    # If no transformations needed, return base URL with auto-optimization
    if not width and not height:
        # Add auto-optimization parameters if it's a Cloudinary URL
        if '/upload/' in base_url:
            return base_url.replace('/upload/', '/upload/q_auto,f_auto/')
        return base_url
    
    # Build transformation string
    transformations = []
    
    if width and height:
        transformations.append(f'w_{width},h_{height},c_{crop}')
    elif width:
        transformations.append(f'w_{width}')
    elif height:
        transformations.append(f'h_{height}')
    
    if quality:
        transformations.append(f'q_{quality}')
    
    if format:
        transformations.append(f'f_{format}')
    
    transform_str = ','.join(transformations)
    
    # Insert transformations into URL
    if '/upload/' in base_url:
        return base_url.replace('/upload/', f'/upload/{transform_str}/')
    
    return base_url


def get_thumbnail_url(image_field, size=200):
    """
    Get thumbnail URL for an image.
    
    Args:
        image_field: Django ImageField instance
        size: Size of thumbnail (square, in pixels)
    
    Returns:
        Thumbnail URL string
    """
    return get_optimized_image_url(
        image_field,
        width=size,
        height=size,
        crop='fill',
        quality='auto',
        format='auto'
    )


def get_product_image_url(image_field, size='medium'):
    """
    Get product image URL with predefined sizes.
    
    Args:
        image_field: Django ImageField instance
        size: 'thumbnail' (200x200), 'small' (400x400), 'medium' (800x800), 
              'large' (1200x1200), or 'original'
    
    Returns:
        Optimized product image URL
    """
    size_map = {
        'thumbnail': (200, 200),
        'small': (400, 400),
        'medium': (800, 800),
        'large': (1200, 1200),
    }
    
    if size == 'original':
        return get_optimized_image_url(image_field)
    
    if size in size_map:
        width, height = size_map[size]
        return get_optimized_image_url(
            image_field,
            width=width,
            height=height,
            crop='fill',
            quality='auto',
            format='auto'
        )
    
    # Default to medium
    return get_optimized_image_url(
        image_field,
        width=800,
        height=800,
        crop='fill',
        quality='auto',
        format='auto'
    )


def get_video_url(video_field, width=None, height=None, quality='auto', format='auto'):
    """
    Get optimized video URL from Cloudinary with transformations.
    
    Args:
        video_field: Django FileField instance (video)
        width: Target width in pixels (optional)
        height: Target height in pixels (optional)
        quality: Video quality ('auto', 'best', 'good', 'eco', 'low')
        format: Video format ('auto', 'mp4', 'webm', etc.)
    
    Returns:
        Optimized Cloudinary video URL string
    """
    if not video_field:
        return None
    
    # Get base Cloudinary URL (same logic as images)
    base_url = _get_cloudinary_url_from_field(video_field)
    
    # If no transformations needed, return base URL with auto-optimization
    if not width and not height:
        if '/upload/' in base_url:
            return base_url.replace('/upload/', '/upload/q_auto,f_auto/')
        return base_url
    
    # Build transformation string for video
    transformations = []
    
    if width and height:
        transformations.append(f'w_{width},h_{height},c_fill')
    elif width:
        transformations.append(f'w_{width}')
    elif height:
        transformations.append(f'h_{height}')
    
    if quality:
        transformations.append(f'q_{quality}')
    
    if format:
        transformations.append(f'f_{format}')
    
    transform_str = ','.join(transformations)
    
    # Insert transformations into URL
    if '/upload/' in base_url:
        return base_url.replace('/upload/', f'/upload/{transform_str}/')
    
    return base_url


def get_video_thumbnail_url(video_field, width=640, height=360):
    """
    Get thumbnail/poster image for a video.
    
    Args:
        video_field: Django FileField instance (video)
        width: Thumbnail width (default 640)
        height: Thumbnail height (default 360)
    
    Returns:
        Video thumbnail URL string
    """
    if not video_field:
        return None
    
    base_url = video_field.url
    
    # Extract public_id from URL and generate thumbnail
    # Cloudinary automatically generates thumbnails for videos
    if '/upload/' in base_url:
        # Add video thumbnail transformation
        return base_url.replace('/upload/', f'/upload/w_{width},h_{height},c_fill,q_auto,f_jpg/')
    
    return base_url

