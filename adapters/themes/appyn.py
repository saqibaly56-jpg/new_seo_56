import random
from typing import Dict, Any, Tuple
from core.universal_model import ContentDocument
from utils.logger import get_logger
from utils.http import request_with_retry

logger = get_logger("theme_appyn")

class AppynAdapter:
    @staticmethod
    def _random_version() -> str:
        major = random.choice([1, 2, 3])
        minor = random.randint(0, 4)
        patch = random.randint(0, 9)
        return f"{major}.{minor}.{patch}"

    @staticmethod
    def _random_size() -> str:
        choices = ["7.2MB", "12.5MB", "18.4MB", "24.8MB", "31.6MB", "42.1MB", "56.7MB", "68.3MB"]
        return random.choice(choices)

    @staticmethod
    def _random_updated_at() -> str:
        choices = ["Just now", "1 hour ago", "3 hours ago", "Today", "Yesterday", "2 days ago", "This week"]
        return random.choice(choices)

    @staticmethod
    def _random_requirements() -> str:
        choices = ["Android 8.0+", "Android 9.0+", "Android 10.0+", "Android 11.0+", "Android 12.0+"]
        return random.choice(choices)

    @staticmethod
    def _random_downloads() -> str:
        choices = ["5k+", "12k+", "25k+", "50k+", "100k+", "250k+", "500k+"]
        return random.choice(choices)

    @staticmethod
    def _random_category(title: str) -> str:
        lower_title = title.lower()
        if any(word in lower_title for word in ["game", "apk", "casino", "slots", "bet", "gaming"]):
            return "GAMES"
        if any(word in lower_title for word in ["finance", "bank", "pay", "wallet"]):
            return "FINANCE"
        if any(word in lower_title for word in ["photo", "camera", "editor", "gallery"]):
            return "PHOTOGRAPHY"
        return "APPS"

    @staticmethod
    def _random_os() -> str:
        return "ANDROID"

    @staticmethod
    def _random_rating() -> str:
        choices = ["4.6", "4.7", "4.8", "4.9", "5.0"]
        return random.choice(choices)

    @staticmethod
    def ensure_custom_fields(doc: ContentDocument) -> None:
        if not isinstance(doc.custom_fields, dict):
            doc.custom_fields = {}

        doc.custom_fields.setdefault("version", AppynAdapter._random_version())
        doc.custom_fields.setdefault("size", AppynAdapter._random_size())
        doc.custom_fields.setdefault("updated_at", AppynAdapter._random_updated_at())
        doc.custom_fields.setdefault("requirements", AppynAdapter._random_requirements())
        doc.custom_fields.setdefault("downloads", AppynAdapter._random_downloads())
        doc.custom_fields.setdefault("category", AppynAdapter._random_category(doc.title))
        doc.custom_fields.setdefault("os", AppynAdapter._random_os())
        if not doc.custom_fields.get("rating"):
            doc.custom_fields["rating"] = doc.custom_fields.get("stars") or AppynAdapter._random_rating()

    @staticmethod
    def apply_custom_fields(doc: ContentDocument, post_id: str, site_url: str, auth: Tuple[str, str], headers: Dict[str, str]) -> bool:
        """
        Pushes custom fields required by the Appyn Theme using the seo-automation endpoint.
        """
        # Determine Appyn description (fallback to excerpt or first paragraph logic)
        appyn_desc = doc.seo_metadata.meta_description
        if not appyn_desc and doc.introduction:
            appyn_desc = doc.introduction[:300] + ('...' if len(doc.introduction) > 300 else '')
        elif not appyn_desc:
            appyn_desc = "A high-quality APK release with strong performance and modern features."
            
        payload = {
            "post_id": int(post_id),
            "datos_informacion": {
                "app_status": "new",
                "descripcion": appyn_desc,
                "version": doc.custom_fields.get("version") or AppynAdapter._random_version(),
                "tamano": doc.custom_fields.get("size") or AppynAdapter._random_size(),
                "fecha_actualizacion": doc.custom_fields.get("updated_at") or AppynAdapter._random_updated_at(),
                "requerimientos": doc.custom_fields.get("requirements") or AppynAdapter._random_requirements(),
                "descargas": doc.custom_fields.get("downloads") or AppynAdapter._random_downloads(),
                "categoria_app": doc.custom_fields.get("category") or AppynAdapter._random_category(doc.title),
                "os": doc.custom_fields.get("os") or AppynAdapter._random_os(),
                "offer": {"amount": "", "currency": "USD"},
                "rating": doc.custom_fields.get("rating") or doc.custom_fields.get("stars") or AppynAdapter._random_rating()
            },
            "datos_download": {
                "option": "links",
                "type": "apk",
                "0": {
                    "link": "#",
                    "texto": "DOWNLOAD APK"
                }
            }
        }
        
        url = f"{site_url.rstrip('/')}/wp-json/seo-automation/v1/update-meta"
        headers = headers.copy()
        headers.setdefault("Content-Type", "application/json")
        logger.info(f"Sending Appyn custom fields for post {post_id} to {url}")
        logger.debug(f"Appyn custom fields payload: {payload}")
        try:
            resp = request_with_retry('POST', url, json=payload, headers=headers, auth=auth, timeout=15)
            logger.info(f"Appyn custom fields response status: {resp.status_code}")
            logger.debug(f"Appyn custom fields response body: {resp.text}")
            if resp.status_code in [200, 201]:
                logger.info(f"Appyn custom fields successfully applied for Post {post_id}.")
                return True
            else:
                logger.warning(f"Appyn update failed with status {resp.status_code}")
        except Exception as e:
            logger.error(f"Failed to update Appyn custom fields: {e}")
            
        return False
