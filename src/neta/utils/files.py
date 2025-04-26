import os
import time
import logging
import base64
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class ImageManager:
    """
    Manage temporary image files for processing.
    """
    
    def __init__(self, image_dir=None):
        """
        Initialize image manager.
        
        Args:
            image_dir: Directory for temporary images (default: system temp directory)
        """
        if image_dir is None:
            image_dir = os.path.join(tempfile.gettempdir(), "neta_temp_images")
            
        self.image_dir = Path(image_dir)
        
        # Create directory for temporary image storage if it doesn't exist
        if not self.image_dir.exists():
            os.makedirs(self.image_dir, exist_ok=True)
            logger.info(f"Created temp image directory: {self.image_dir}")
    
    def save_image_from_base64(self, base64_data, prefix="whatsapp_image"):
        """
        Save base64 encoded image to temporary file.
        
        Args:
            base64_data: Base64 encoded image data
            prefix: Filename prefix
            
        Returns:
            Path to saved image file
        """
        try:
            # Extract base64 data if it contains data URL prefix
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]
                
            img_bytes = base64.b64decode(base64_data)
            img_path = self.image_dir / f"{prefix}_{int(time.time())}.png"
            
            with open(img_path, "wb") as img_file:
                img_file.write(img_bytes)
                
            logger.info(f"Saved image to {img_path}")
            return str(img_path)
        except Exception as e:
            logger.error(f"Error saving base64 image: {e}")
            return None
    
    def save_image_from_blob(self, blob_data_url, prefix="whatsapp_image"):
        """
        Save blob data URL to temporary file.
        
        Args:
            blob_data_url: Data URL from blob
            prefix: Filename prefix
            
        Returns:
            Path to saved image file
        """
        try:
            if blob_data_url and blob_data_url.startswith("data:image"):
                # Extract base64 data
                img_data = blob_data_url.split(",")[1]
                return self.save_image_from_base64(img_data, prefix)
            else:
                logger.error("Invalid blob data URL format")
                return None
        except Exception as e:
            logger.error(f"Error saving blob image: {e}")
            return None
    
    def cleanup_old_files(self, max_age_seconds=3600):
        """
        Clean up temporary image files older than specified age.
        
        Args:
            max_age_seconds: Maximum age in seconds (default: 1 hour)
        """
        try:
            current_time = time.time()
            cleaned_count = 0
            
            for file_path in self.image_dir.glob("*"):
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        cleaned_count += 1
                        
            if cleaned_count > 0:
                logger.info(f"Deleted {cleaned_count} old temporary files")
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")