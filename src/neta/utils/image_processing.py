import logging
import os
import tempfile
from typing import Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def compress_image(image_path: str, max_size_kb: int = 500, quality: int = 85) -> str:
    """
    Compress an image to reduce its file size while maintaining reasonable quality.

    Args:
        image_path: Path to the original image file
        max_size_kb: Maximum desired file size in kilobytes
        quality: Initial JPEG quality (0-100)

    Returns:
        Path to the compressed image file
    """
    try:
        # If the image is already small enough, return the original path
        original_size_kb = os.path.getsize(image_path) / 1024
        if original_size_kb <= max_size_kb:
            logger.info(
                f"Image already under {max_size_kb}KB ({original_size_kb:.1f}KB), no compression needed"
            )
            return image_path

        # Create a temporary file for the compressed image
        temp_dir = tempfile.gettempdir()
        original_filename = os.path.basename(image_path)
        compressed_filename = f"compressed_{original_filename.split('.')[0]}.jpg"
        compressed_path = os.path.join(temp_dir, compressed_filename)

        # Open the image using PIL
        with Image.open(image_path) as img:
            # Convert to RGB if needed (in case of RGBA, etc.)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Start with the initial quality setting
            current_quality = quality

            # Save and check size
            img.save(compressed_path, format="JPEG", quality=current_quality)
            compressed_size_kb = os.path.getsize(compressed_path) / 1024

            # If still too large, reduce quality iteratively
            while compressed_size_kb > max_size_kb and current_quality > 5:
                current_quality -= 5
                img.save(compressed_path, format="JPEG", quality=current_quality)
                compressed_size_kb = os.path.getsize(compressed_path) / 1024

            # As a last resort, resize the image if quality reduction wasn't enough
            if compressed_size_kb > max_size_kb:
                # Calculate new dimensions while maintaining aspect ratio
                width, height = img.size
                scale_factor = 0.9  # Reduce by 10% in each iteration

                while compressed_size_kb > max_size_kb and scale_factor > 0.1:
                    new_width = int(width * scale_factor)
                    new_height = int(height * scale_factor)
                    resized_img = img.resize((new_width, new_height), Image.LANCZOS)

                    # Save with the lowest quality we reached
                    resized_img.save(compressed_path, format="JPEG", quality=current_quality)
                    compressed_size_kb = os.path.getsize(compressed_path) / 1024

                    # Reduce size by another 10% if still too large
                    scale_factor *= 0.9

        final_size_kb = os.path.getsize(compressed_path) / 1024
        compression_ratio = original_size_kb / final_size_kb if final_size_kb > 0 else 0

        logger.info(
            f"Compressed image from {original_size_kb:.1f}KB to {final_size_kb:.1f}KB "
            f"(ratio: {compression_ratio:.1f}x, quality: {current_quality})"
        )

        return compressed_path

    except Exception as e:
        logger.error(f"Error compressing image {image_path}: {e}")
        # Return the original path if compression fails
        return image_path


def get_image_dimensions(image_path: str) -> Optional[Tuple[int, int]]:
    """
    Get the dimensions of an image.

    Args:
        image_path: Path to the image file

    Returns:
        Tuple of (width, height) or None if failed
    """
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        logger.error(f"Error getting image dimensions for {image_path}: {e}")
        return None
