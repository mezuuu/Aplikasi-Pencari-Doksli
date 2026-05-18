"""
Digital forensic analysis service.

Provides Error Level Analysis (ELA) for detecting image manipulation.
ELA works by re-compressing the image at a known quality level and
comparing the difference — edited regions show higher error levels
because they were saved at different compression levels.

The ELA score is integrated into the overall similarity ranking
to help distinguish authentic documents from manipulated ones.
"""

import logging
import os
import uuid

import numpy as np
from PIL import Image, ImageChops, ImageEnhance

from django.conf import settings as django_settings

logger = logging.getLogger(__name__)

# ─── Configuration ───
ELA_QUALITY = 90       # JPEG re-compression quality for ELA
ELA_SCALE = 15         # Amplification factor for visualization
ELA_THRESHOLD = 25.0   # Mean error above this = likely edited


def perform_ela(image_path, quality=ELA_QUALITY, scale=ELA_SCALE):
    """
    Perform Error Level Analysis on an image.

    Process:
    1. Re-save the image at a known JPEG quality level
    2. Compute pixel-by-pixel difference between original and re-saved
    3. Amplify differences for visibility
    4. Calculate overall manipulation score

    Args:
        image_path: Path to the image file.
        quality: JPEG quality level for re-compression (default: 90).
        scale: Amplification factor for the error image (default: 15).

    Returns:
        dict with:
            - ela_score: float — average error level (0-255, higher = more suspicious)
            - max_error: float — maximum regional error
            - is_suspicious: bool — True if ela_score > ELA_THRESHOLD
            - ela_image_path: str — path to the ELA visualization image (or None)
            - error_distribution: dict — distribution of error levels
    """
    result = {
        'ela_score': 0.0,
        'max_error': 0.0,
        'is_suspicious': False,
        'ela_image_path': None,
        'error_distribution': {
            'low': 0.0,     # % of pixels with low error (< 10)
            'medium': 0.0,  # % of pixels with medium error (10-50)
            'high': 0.0,    # % of pixels with high error (> 50)
        }
    }

    try:
        # Open original image
        original = Image.open(image_path).convert('RGB')

        # Re-save at known quality
        temp_dir = os.path.join(django_settings.MEDIA_ROOT, 'temp_ela')
        os.makedirs(temp_dir, exist_ok=True)

        resaved_path = os.path.join(temp_dir, f"ela_resaved_{uuid.uuid4().hex[:8]}.jpg")
        original.save(resaved_path, 'JPEG', quality=quality)

        # Re-open the re-saved version
        resaved = Image.open(resaved_path).convert('RGB')

        # Compute pixel difference
        diff = ImageChops.difference(original, resaved)

        # Convert to numpy for analysis
        diff_np = np.array(diff, dtype=np.float32)

        # Calculate per-pixel error magnitude (average across RGB channels)
        error_magnitude = np.mean(diff_np, axis=2)

        # ─── Compute statistics ───
        result['ela_score'] = float(np.mean(error_magnitude))
        result['max_error'] = float(np.max(error_magnitude))

        total_pixels = error_magnitude.size
        result['error_distribution'] = {
            'low': float(np.sum(error_magnitude < 10) / total_pixels * 100),
            'medium': float(np.sum((error_magnitude >= 10) & (error_magnitude <= 50)) / total_pixels * 100),
            'high': float(np.sum(error_magnitude > 50) / total_pixels * 100),
        }

        result['is_suspicious'] = result['ela_score'] > ELA_THRESHOLD

        # ─── Generate ELA visualization ───
        # Amplify the difference for visibility
        extrema = diff.getextrema()
        max_diff = max([ex[1] for ex in extrema])

        if max_diff > 0:
            amplification = 255.0 / max_diff * scale
            ela_image = ImageEnhance.Brightness(diff).enhance(amplification)
        else:
            ela_image = diff

        # Save ELA visualization
        ela_filename = f"ela_{uuid.uuid4().hex[:12]}.png"
        ela_image_path = os.path.join(temp_dir, ela_filename)
        ela_image.save(ela_image_path, 'PNG')
        result['ela_image_path'] = ela_image_path

        # Clean up resaved temp file
        try:
            os.remove(resaved_path)
        except OSError:
            pass

        logger.info(
            f"[ELA] Analysis complete: score={result['ela_score']:.2f}, "
            f"max_error={result['max_error']:.2f}, "
            f"suspicious={result['is_suspicious']}, "
            f"high_error_pct={result['error_distribution']['high']:.1f}%"
        )

    except Exception as e:
        logger.error(f"[ELA] Analysis failed: {e}")

    return result


def cleanup_ela_files(ela_image_path):
    """Remove temporary ELA visualization files."""
    if ela_image_path and os.path.exists(ela_image_path):
        try:
            os.remove(ela_image_path)
        except OSError as e:
            logger.warning(f"Failed to clean up ELA file: {e}")


def compute_manipulation_confidence(ela_result):
    """
    Convert ELA results into a manipulation confidence score (0.0 - 1.0).

    This score can be used to adjust the overall similarity ranking.
    A high manipulation confidence means the query image is likely edited.

    Args:
        ela_result: dict from perform_ela()

    Returns:
        float: Manipulation confidence (0.0 = likely original, 1.0 = likely edited)
    """
    if not ela_result:
        return 0.0

    score = ela_result.get('ela_score', 0.0)
    high_pct = ela_result.get('error_distribution', {}).get('high', 0.0)

    # Normalize ELA score to 0-1 range (cap at 100)
    score_normalized = min(score / 100.0, 1.0)

    # Normalize high-error percentage (cap at 30%)
    high_normalized = min(high_pct / 30.0, 1.0)

    # Weighted combination
    confidence = 0.6 * score_normalized + 0.4 * high_normalized

    return round(min(confidence, 1.0), 4)
