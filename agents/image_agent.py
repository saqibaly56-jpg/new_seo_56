from typing import Dict, Any, Optional
import os
import requests
from PIL import Image
from io import BytesIO
from utils.logger import get_logger
from agents.discovery_agent import Candidate

logger = get_logger("image_agent")

class ImageAgent:
    def __init__(self):
        default_data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        if (
            os.getenv('APP_ENV', 'development').strip().lower() in {'production', 'prod'}
            or os.getenv('RAILWAY_ENVIRONMENT')
        ):
            default_data_dir = os.path.join('/tmp', 'seo_automation')
        data_dir = os.getenv('DATA_DIR', default_data_dir)
        self.tmp_dir = os.path.join(data_dir, 'tmp_images')
        os.makedirs(self.tmp_dir, exist_ok=True)
        
    def _download_and_resize(self, url: str, filename: str) -> Optional[str]:
        if not url:
            return None
        try:
            logger.info(f"Downloading image from {url}")
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            img = Image.open(BytesIO(response.content))
            
            # Convert to RGB if necessary (e.g. for PNGs with alpha channel when saving as JPEG)
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Maintain aspect ratio and high quality (max 1200px)
            img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            img_resized = img            
            save_path = os.path.join(self.tmp_dir, filename)
            img_resized.save(save_path, 'JPEG', quality=90)
            logger.info(f"Saved resized image to {save_path}")
            return save_path
        except Exception as e:
            logger.error(f"Failed to process image {url}: {e}")
            return None

    def process_images(self, candidate: Candidate) -> Dict[str, str]:
        """
        Downloads and resizes all available Airtable images for the candidate.
        Returns a dictionary mapping image types to local file paths.
        """
        results = {}
        prefix = f"{candidate.provider}_{candidate.game_name}".replace(' ', '_').replace('/', '_')
        
        if candidate.featured_image_url:
            path = self._download_and_resize(candidate.featured_image_url, f"{prefix}_featured.jpg")
            if path: results['featured'] = path
            
        if candidate.description_image_url:
            path = self._download_and_resize(candidate.description_image_url, f"{prefix}_description.jpg")
            if path: results['description'] = path
            
        if candidate.login_image_url:
            path = self._download_and_resize(candidate.login_image_url, f"{prefix}_login.jpg")
            if path: results['login'] = path
            
        if candidate.transaction_image_url:
            path = self._download_and_resize(candidate.transaction_image_url, f"{prefix}_transaction.jpg")
            if path: results['transaction'] = path
            
        return results

    def process_custom_image(self, file_path: str, target_width: Optional[int] = None, target_height: Optional[int] = None, quality: int = 90) -> Dict[str, Any]:
        """
        Processes a local uploaded image using Pillow, maintaining aspect ratio unless specified.
        Returns width, height, file_size, and updated file_path.
        """
        try:
            img = Image.open(file_path)
            orig_w, orig_h = img.size

            if target_width or target_height:
                if target_width and not target_height:
                    ratio = target_width / float(orig_w)
                    new_h = int(orig_h * ratio)
                    img = img.resize((target_width, new_h), Image.Resampling.LANCZOS)
                elif target_height and not target_width:
                    ratio = target_height / float(orig_h)
                    new_w = int(orig_w * ratio)
                    img = img.resize((new_w, target_height), Image.Resampling.LANCZOS)
                elif target_width and target_height:
                    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            out_w, out_h = img.size
            img.save(file_path, 'JPEG', quality=quality)
            file_size = os.path.getsize(file_path)

            return {
                "width": out_w,
                "height": out_h,
                "file_size": file_size,
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Failed custom image processing for {file_path}: {e}")
            return {
                "width": 0,
                "height": 0,
                "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                "file_path": file_path
            }
