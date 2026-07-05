"""
Sub-region cropping service for screenshot analysis.

When a full-image similarity search fails (e.g., a screenshot with UI chrome),
this service generates multiple cropped sub-regions using a sliding window
approach. Each sub-region can then be independently embedded and compared
against the database to find the actual document content within the screenshot.

Uses only Pillow (already a project dependency) — no new packages required.
"""
import logging
import os
import uuid
from PIL import Image
from django.conf import settings as django_settings
logger = logging.getLogger(__name__)

class CroppingService:

    @staticmethod
    def generate_crop_regions(image_path):
        """
    Generate cropped sub-regions from an image using a multi-scale sliding window.

    The function creates crops at multiple scales (e.g., 50% and 70% of the
    original dimensions) with configurable overlap. Each crop is saved as a
    temporary file for downstream embedding extraction.

    Args:
        image_path: Path to the source image file.

    Returns:
        list[str]: List of file paths to the generated crop images.
                   Caller is responsible for cleanup via cleanup_crops().
    """
        scales = getattr(django_settings, 'CROP_SCALES', [0.5, 0.7])
        overlap = getattr(django_settings, 'CROP_OVERLAP', 0.5)
        min_size = getattr(django_settings, 'CROP_MIN_SIZE', 100)
        try:
            img = Image.open(image_path).convert('RGB')
        except Exception as e:
            logger.error(f'Failed to open image for cropping: {e}')
            return []
        img_w, img_h = img.size
        crop_paths = []
        crop_dir = os.path.join(django_settings.MEDIA_ROOT, 'temp_crops')
        os.makedirs(crop_dir, exist_ok=True)
        for scale in scales:
            win_w = int(img_w * scale)
            win_h = int(img_h * scale)
            if win_w < min_size or win_h < min_size:
                logger.debug(f'Skipping scale {scale}: window {win_w}x{win_h} below minimum {min_size}px')
                continue
            step_x = max(1, int(win_w * (1 - overlap)))
            step_y = max(1, int(win_h * (1 - overlap)))
            y = 0
            while y + win_h <= img_h:
                x = 0
                while x + win_w <= img_w:
                    box = (x, y, x + win_w, y + win_h)
                    cropped = img.crop(box)
                    crop_filename = f'crop_{uuid.uuid4().hex[:12]}.jpg'
                    crop_path = os.path.join(crop_dir, crop_filename)
                    cropped.save(crop_path, 'JPEG', quality=90)
                    crop_paths.append(crop_path)
                    x += step_x
                y += step_y
        logger.info(f'Generated {len(crop_paths)} crop regions from {image_path} (original: {img_w}x{img_h}, scales: {scales}, overlap: {overlap})')
        return crop_paths

    @staticmethod
    def cleanup_crops(crop_paths):
        """
    Delete temporary crop files from disk.

    Args:
        crop_paths: List of file paths to delete.
    """
        removed = 0
        for path in crop_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    removed += 1
            except Exception as e:
                logger.warning(f'Failed to remove crop file {path}: {e}')
        logger.info(f'Cleaned up {removed}/{len(crop_paths)} crop files')