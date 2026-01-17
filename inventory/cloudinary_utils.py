"""
Utility functions for Cloudinary image and video transformations.
Provides helper methods to generate optimized URLs with transformations.
"""
import os
import logging
import uuid
import cloudinary
import cloudinary.api

logger = logging.getLogger(__name__)

# Configure Cloudinary once at module load (if credentials are available)
_cloudinary_configured = False

def _ensure_cloudinary_configured():
    """Ensure Cloudinary is configured with credentials from environment."""
    global _cloudinary_configured
    
    if _cloudinary_configured:
        return True
    
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
    
    if not all([cloud_name, api_key, api_secret]):
        logger.warning(
            "Cloudinary credentials not fully configured. "
            "Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET environment variables."
        )
        return False
    
    try:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        _cloudinary_configured = True
        logger.info("Cloudinary configured successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to configure Cloudinary: {e}")
        return False


def upload_image_to_cloudinary(file_obj, folder):
    """
    Save an image file directly to Cloudinary storage.

    Returns a tuple of (file_name, url).
    """
    if not file_obj:
        return None, None

    # Ensure Cloudinary is configured before saving
    if not _ensure_cloudinary_configured():
        raise ValueError("Cloudinary is not configured")

    from cloudinary_storage.storage import MediaCloudinaryStorage

    storage = MediaCloudinaryStorage()
    ext = os.path.splitext(getattr(file_obj, 'name', '') or '')[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = f"{folder.strip('/')}/{unique_name}"
    saved_name = storage.save(storage_path, file_obj)
    return saved_name, storage.url(saved_name)


def upload_video_to_cloudinary(file_obj, folder):
    """
    Save a video file directly to Cloudinary storage.

    Returns a tuple of (file_name, url).
    """
    if not file_obj:
        return None, None

    # Ensure Cloudinary is configured before saving
    if not _ensure_cloudinary_configured():
        raise ValueError("Cloudinary is not configured")

    from cloudinary_storage.storage import MediaCloudinaryStorage

    storage = MediaCloudinaryStorage()
    ext = os.path.splitext(getattr(file_obj, 'name', '') or '')[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    storage_path = f"{folder.strip('/')}/{unique_name}"
    saved_name = storage.save(storage_path, file_obj)
    return saved_name, storage.url(saved_name)


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
        # Ensure Cloudinary is configured
        if not _ensure_cloudinary_configured():
            # If Cloudinary is not configured, return absolute URL
            if base_url.startswith('/'):
                host = os.environ.get('DJANGO_HOST', 'localhost:8000')
                protocol = 'https' if os.environ.get('DJANGO_USE_HTTPS', '').lower() == 'true' else 'http'
                return f"{protocol}://{host}{base_url}"
            return base_url
        
        try:
            # Check if the name looks like a Cloudinary public_id (no slashes at start, or has folder structure)
            public_id = image_field.name
            
            # Remove file extension if present (Cloudinary stores without extension)
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            # Build Cloudinary URL
            from cloudinary import CloudinaryImage
            cloudinary_img = CloudinaryImage(public_id)
            return cloudinary_img.build_url()
        except Exception as e:
            logger.warning(f"Failed to build Cloudinary URL from public_id '{image_field.name}': {e}")
            # If Cloudinary URL construction fails, return the original URL as absolute
            if base_url.startswith('/'):
                host = os.environ.get('DJANGO_HOST', 'localhost:8000')
                protocol = 'https' if os.environ.get('DJANGO_USE_HTTPS', '').lower() == 'true' else 'http'
                return f"{protocol}://{host}{base_url}"
            # If base_url is already absolute or doesn't start with '/', return it as-is
            return base_url
    
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
    
    # CRITICAL: Always use image_field.name FIRST - it contains the actual public_id
    # django-cloudinary-storage stores files with 'media/' prefix, so name will be 'media/promotions/...'
    # The URL from storage might not include 'media/', but the actual public_id does
    if hasattr(image_field, 'name') and image_field.name:
        try:
            from cloudinary import CloudinaryImage
            
            public_id = image_field.name
            # Remove file extension for public_id
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            # DEBUG: Log the public_id to help diagnose issues
            logger.debug(f"Building Cloudinary URL from public_id: {public_id}")
            
            # Build transformation parameters
            transformation_params = {}
            if width and height:
                transformation_params['width'] = width
                transformation_params['height'] = height
                transformation_params['crop'] = crop
            elif width:
                transformation_params['width'] = width
            elif height:
                transformation_params['height'] = height
            
            if quality and quality != 'auto':
                transformation_params['quality'] = quality
            
            # Don't pass format='auto' - Cloudinary handles auto-format automatically
            if format and format != 'auto':
                transformation_params['format'] = format
            
            # Build URL with transformations using the actual public_id
            # IMPORTANT: public_id should include 'media/' prefix if django-cloudinary-storage added it
            cloudinary_img = CloudinaryImage(public_id)
            built_url = cloudinary_img.build_url(**transformation_params)
            logger.debug(f"Built Cloudinary URL: {built_url}")
            return built_url
        except Exception as e:
            logger.warning(f"Failed to build Cloudinary URL from image_field.name '{image_field.name}': {e}")
            # Fall through to URL-based method
    
    # Fallback: Use image_field.url if name-based method failed
    base_url = image_field.url if hasattr(image_field, 'url') else None
    if base_url and ('cloudinary.com' in base_url or 'res.cloudinary.com' in base_url):
        # URL is already from Cloudinary - add transformations to existing URL
        # This preserves the correct public_id that Cloudinary storage backend knows about
        try:
            # Check if transformations are already in the URL
            if '/upload/' in base_url:
                # Extract the transformation part and the public_id part
                parts = base_url.split('/upload/')
                if len(parts) == 2:
                    # Check if transformations already exist
                    after_upload = parts[1]
                    # If transformations exist, they come before the version or public_id
                    # Format: /upload/TRANSFORMATIONS/v1/public_id or /upload/TRANSFORMATIONS/public_id
                    
                    # Build transformation string
                    transformations = []
                    if width and height:
                        transformations.append(f'w_{width},h_{height},c_{crop}')
                    elif width:
                        transformations.append(f'w_{width}')
                    elif height:
                        transformations.append(f'h_{height}')
                    
                    if quality and quality != 'auto':
                        transformations.append(f'q_{quality}')
                    
                    # Don't add f_auto - Cloudinary handles auto-format automatically
                    if format and format != 'auto':
                        transformations.append(f'f_{format}')
                    
                    if transformations:
                        transform_str = ','.join(transformations)
                        # Insert transformations after /upload/
                        # If there are already transformations, replace them; otherwise add new ones
                        if ',' in after_upload.split('/')[0] or any(x in after_upload.split('/')[0] for x in ['w_', 'h_', 'c_', 'q_', 'f_']):
                            # Replace existing transformations
                            path_parts = after_upload.split('/')
                            path_parts[0] = transform_str
                            new_after_upload = '/'.join(path_parts)
                        else:
                            # Add new transformations
                            new_after_upload = f'{transform_str}/{after_upload}'
                        
                        return f"{parts[0]}/upload/{new_after_upload}"
            
            # If we can't parse it, fall through to reconstruction method
        except Exception as e:
            logger.warning(f"Failed to add transformations to existing Cloudinary URL: {e}. Reconstructing...")
            # Fall through to reconstruction method
    
    # Fallback: Parse from URL if name-based method didn't work
    if hasattr(image_field, 'name') and image_field.name:
        try:
            from cloudinary import CloudinaryImage
            
            public_id = image_field.name
            # Remove file extension for public_id
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            # DEBUG: Log the public_id to help diagnose issues
            logger.debug(f"Building Cloudinary URL from public_id: {public_id}")
            
            # Build transformation parameters
            transformation_params = {}
            if width and height:
                transformation_params['width'] = width
                transformation_params['height'] = height
                transformation_params['crop'] = crop
            elif width:
                transformation_params['width'] = width
            elif height:
                transformation_params['height'] = height
            
            if quality and quality != 'auto':
                transformation_params['quality'] = quality
            
            # Don't pass format='auto' - Cloudinary handles auto-format automatically
            # Only pass format if it's a specific format (jpg, png, webp, etc.)
            if format and format != 'auto':
                transformation_params['format'] = format
            
            # Try with the public_id as-is first (preserves any prefix that was used during upload)
            try:
                cloudinary_img = CloudinaryImage(public_id)
                built_url = cloudinary_img.build_url(**transformation_params)
                logger.debug(f"Built Cloudinary URL: {built_url}")
                return built_url
            except Exception as e:
                logger.warning(f"Failed to build Cloudinary URL with public_id '{public_id}': {e}")
            
            # If that failed, try without 'media/' prefix if it was present
            if public_id.startswith('media/'):
                try:
                    public_id_no_media = public_id[6:]  # Remove 'media/' prefix
                    cloudinary_img = CloudinaryImage(public_id_no_media)
                    built_url = cloudinary_img.build_url(**transformation_params)
                    logger.debug(f"Built Cloudinary URL without 'media/' prefix: {built_url}")
                    return built_url
                except Exception as e:
                    logger.warning(f"Failed to build Cloudinary URL without 'media/' prefix: {e}")
            
            # If both attempts failed, try adding 'media/' prefix if it wasn't there
            if not public_id.startswith('media/'):
                try:
                    public_id_with_media = f'media/{public_id}'
                    cloudinary_img = CloudinaryImage(public_id_with_media)
                    built_url = cloudinary_img.build_url(**transformation_params)
                    logger.debug(f"Built Cloudinary URL with 'media/' prefix: {built_url}")
                    return built_url
                except Exception as e:
                    logger.warning(f"Failed to build Cloudinary URL with 'media/' prefix: {e}")
        except Exception as e:
            logger.warning(f"Failed to build Cloudinary URL from image_field.name '{image_field.name}': {e}")
            # Fall through to URL parsing method
    
    # Fallback: Get base Cloudinary URL and parse it
    base_url = _get_cloudinary_url_from_field(image_field)
    
    if not base_url:
        return None
    
    # If it's not a Cloudinary URL, return as-is (no transformations possible)
    if '/upload/' not in base_url or 'cloudinary.com' not in base_url:
        return base_url
    
    # Use Cloudinary's URL building for better reliability
    try:
        from cloudinary import CloudinaryImage
        from urllib.parse import urlparse
        
        # Extract public_id from Cloudinary URL
        # Format: https://res.cloudinary.com/cloud_name/image/upload/v123/public_id.jpg
        parsed = urlparse(base_url)
        path_parts = parsed.path.split('/')
        
        # Find the upload segment and get everything after it
        try:
            upload_idx = path_parts.index('upload')
            # Get everything after 'upload' (skip version if present)
            after_upload = path_parts[upload_idx + 1:]
            # Remove version if present (starts with 'v' followed by numbers)
            if after_upload and after_upload[0].startswith('v') and after_upload[0][1:].isdigit():
                after_upload = after_upload[1:]
            # Remove transformation parameters if present
            if after_upload and ',' in after_upload[0]:
                after_upload = after_upload[1:]
            
            public_id = '/'.join(after_upload)
            # Remove file extension for public_id
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            # CRITICAL: If URL doesn't have 'media/' but file was uploaded with it, add it
            # Check if the original URL path suggests 'media/' should be present
            # django-cloudinary-storage adds 'media/' prefix because of MEDIA_URL='/media/'
            if not public_id.startswith('media/') and hasattr(image_field, 'name') and image_field.name and 'media/' in image_field.name:
                # The file was uploaded with 'media/' prefix, so add it back
                public_id = 'media/' + public_id
            
            # Build transformation parameters
            transformation_params = {}
            if width and height:
                transformation_params['width'] = width
                transformation_params['height'] = height
                transformation_params['crop'] = crop
            elif width:
                transformation_params['width'] = width
            elif height:
                transformation_params['height'] = height
            
            if quality and quality != 'auto':
                transformation_params['quality'] = quality
            
            # Don't pass format='auto' - Cloudinary handles auto-format automatically
            if format and format != 'auto':
                transformation_params['format'] = format
            
            # Build URL with transformations
            cloudinary_img = CloudinaryImage(public_id)
            return cloudinary_img.build_url(**transformation_params)
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse Cloudinary URL '{base_url}': {e}. Using string replacement method.")
            # Fallback to string replacement method
            pass
            public_id = image_field.name
            # Remove file extension for public_id
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            # DEBUG: Log the public_id to help diagnose issues
            logger.debug(f"Building Cloudinary URL from public_id: {public_id}")
            
            # Build transformation parameters
            transformation_params = {}
            if width and height:
                transformation_params['width'] = width
                transformation_params['height'] = height
                transformation_params['crop'] = crop
            elif width:
                transformation_params['width'] = width
            elif height:
                transformation_params['height'] = height
            
            if quality and quality != 'auto':
                transformation_params['quality'] = quality
            
            # Don't pass format='auto' - Cloudinary handles auto-format automatically
            if format and format != 'auto':
                transformation_params['format'] = format
            
            # Build URL with transformations using the actual public_id
            # IMPORTANT: public_id should include 'media/' prefix if django-cloudinary-storage added it
            cloudinary_img = CloudinaryImage(public_id)
            built_url = cloudinary_img.build_url(**transformation_params)
            logger.debug(f"Built Cloudinary URL: {built_url}")
            return built_url
        
        # Fallback: Parse from URL if name is not available
        from urllib.parse import urlparse
        
        # Extract public_id from Cloudinary URL
        # Format: https://res.cloudinary.com/cloud_name/image/upload/v123/public_id.jpg
        parsed = urlparse(base_url)
        path_parts = parsed.path.split('/')
        
        # Find the upload segment and get everything after it
        try:
            upload_idx = path_parts.index('upload')
            # Get everything after 'upload' (skip version if present)
            after_upload = path_parts[upload_idx + 1:]
            # Remove version if present (starts with 'v' followed by numbers)
            if after_upload and after_upload[0].startswith('v') and after_upload[0][1:].isdigit():
                after_upload = after_upload[1:]
            # Remove transformation parameters if present
            if after_upload and ',' in after_upload[0]:
                after_upload = after_upload[1:]
            
            public_id = '/'.join(after_upload)
            # Remove file extension for public_id
            if '.' in public_id:
                public_id = public_id.rsplit('.', 1)[0]
            
            # Build transformation parameters
            transformation_params = {}
            if width and height:
                transformation_params['width'] = width
                transformation_params['height'] = height
                transformation_params['crop'] = crop
            elif width:
                transformation_params['width'] = width
            elif height:
                transformation_params['height'] = height
            
            if quality and quality != 'auto':
                transformation_params['quality'] = quality
            
            # Don't pass format='auto' - Cloudinary handles auto-format automatically
            if format and format != 'auto':
                transformation_params['format'] = format
            
            # Build URL with transformations
            cloudinary_img = CloudinaryImage(public_id)
            return cloudinary_img.build_url(**transformation_params)
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse Cloudinary URL '{base_url}': {e}. Using string replacement method.")
            # Fallback to string replacement method
            pass
    
    except Exception as e:
        logger.warning(f"Failed to build Cloudinary URL with transformations: {e}. Using string replacement method.")
        # Fallback to string replacement method
    
    # Fallback: Use string replacement (original method)
    # If no transformations needed, return base URL as-is
    # Cloudinary handles auto-optimization automatically, no need to add f_auto
    if not width and not height:
        return base_url
    
    # Build transformation string
    transformations = []
    
    if width and height:
        transformations.append(f'w_{width},h_{height},c_{crop}')
    elif width:
        transformations.append(f'w_{width}')
    elif height:
        transformations.append(f'h_{height}')
    
    if quality and quality != 'auto':
        transformations.append(f'q_{quality}')
    
    # Don't add f_auto - Cloudinary handles auto-format automatically
    if format and format != 'auto':
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
    
    if quality and quality != 'auto':
        transformations.append(f'q_{quality}')
    
    # Don't add f_auto - Cloudinary handles auto-format automatically
    if format and format != 'auto':
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

