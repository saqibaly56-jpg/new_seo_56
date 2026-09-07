import os
from typing import Dict, Any, Optional

from core.universal_model import ContentDocument
from adapters.wp_base import BaseWordPressAdapter
from adapters.editors.classic import ClassicEditorAdapter
from adapters.editors.gutenberg import GutenbergAdapter
from adapters.seo.rankmath import RankMathAdapter
from adapters.seo.yoast import YoastAdapter
from adapters.themes.appyn import AppynAdapter
from utils.http import request_with_retry
from utils.logger import get_logger

logger = get_logger("wordpress_publisher")


class WordPressPublisher(BaseWordPressAdapter):
    """
    Orchestrates the publishing process by dynamically delegating formatting
    and metadata application to the appropriate adapters based on the Site Profile.
    """
    def publish(self, doc: ContentDocument, image_assignments: Optional[list] = None, post_status: str = "publish") -> Optional[str]:
        logger.info(f"Starting publish process for '{doc.title}' to {self.site_url}")
        self.last_errors = []

        featured_image_id = None
        for key, path in list(doc.images.items()):
            if not str(path).startswith('http'):
                upload_result = self.upload_media(path)
                if upload_result:
                    doc.images[key] = upload_result['url']
                    if key == 'featured':
                        featured_image_id = upload_result['id']
                else:
                    logger.warning(f"Failed to upload image '{key}', removing from document.")
                    del doc.images[key]

        if image_assignments:
            for assignment in image_assignments:
                path = assignment.get('file_path')
                if path and not str(path).startswith('http'):
                    upload_result = self.upload_media(path)
                    if upload_result:
                        assignment['url'] = upload_result['url']
                        if assignment.get('section_id') == 'featured':
                            featured_image_id = upload_result['id']
                    else:
                        logger.warning(f"Failed to upload assigned image: {path}")

        active_theme = self.profile.get('active_theme', 'unknown').lower()
        if active_theme == 'appyn' or 'appyn' in active_theme:
            AppynAdapter.ensure_custom_fields(doc)

        editor_type = self.profile.get('editor_type', 'classic').lower()
        if editor_type == 'gutenberg':
            logger.info("Using Gutenberg Editor Adapter")
            payload = GutenbergAdapter.format_content(doc, image_assignments, post_status=post_status)
        else:
            logger.info("Using Classic Editor Adapter")
            payload = ClassicEditorAdapter.format_content(doc, image_assignments, post_status=post_status)

        payload["categories"] = doc.categories if doc.categories else [2, 4, 7]

        if doc.seo_metadata and doc.seo_metadata.meta_description:
            payload["excerpt"] = doc.seo_metadata.meta_description

        if featured_image_id:
            payload["featured_media"] = featured_image_id

        seo_plugin = self.profile.get('seo_plugin', 'none').lower()
        if seo_plugin != 'none' and doc.seo_metadata:
            if "meta" not in payload:
                payload["meta"] = {}
            if seo_plugin == 'rankmath':
                payload["meta"]["rank_math_focus_keyword"] = doc.seo_metadata.focus_keyword
                payload["meta"]["rank_math_description"] = doc.seo_metadata.meta_description
                if doc.seo_metadata.meta_title:
                    payload["meta"]["rank_math_title"] = doc.seo_metadata.meta_title
            elif seo_plugin == 'yoast':
                payload["meta"]["_yoast_wpseo_focuskw"] = doc.seo_metadata.focus_keyword
                payload["meta"]["_yoast_wpseo_metadesc"] = doc.seo_metadata.meta_description
                if doc.seo_metadata.meta_title:
                    payload["meta"]["_yoast_wpseo_title"] = doc.seo_metadata.meta_title

        post_id = self._push_post(payload)
        if not post_id:
            logger.error("Failed to create base post. Aborting metadata application.")
            return None

        logger.info(f"Base post created with ID {post_id}")

        if seo_plugin == 'rankmath':
            if not RankMathAdapter.apply_metadata(doc, post_id, self.site_url, self.auth, self.headers):
                self.last_errors.append("Rank Math metadata update failed")
        elif seo_plugin == 'yoast':
            if not YoastAdapter.apply_metadata(doc, post_id, self.site_url, self.auth, self.headers):
                self.last_errors.append("Yoast metadata update failed")

        active_theme = self.profile.get('active_theme', 'unknown').lower()
        if active_theme == 'appyn' or 'appyn' in active_theme:
            if not AppynAdapter.apply_custom_fields(doc, post_id, self.site_url, self.auth, self.headers):
                self.last_errors.append("Appyn custom fields update failed")

        return post_id


class WordPressAgent:
    """Compatibility wrapper used by the test suite and simple WP publishing flows."""

    def __init__(self, site_url: Optional[str] = None, username: Optional[str] = None, app_password: Optional[str] = None):
        self.site_url = (site_url or os.getenv("WP_URL", "http://test")).rstrip('/')
        self.username = username or os.getenv("WP_USERNAME", "user")
        self.app_password = app_password or os.getenv("WP_APP_PASSWORD", "password")
        self.auth = (self.username, self.app_password)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }

    def push_draft(self, draft: Any) -> Optional[str]:
        content = getattr(draft, 'body', str(draft))
        payload = {
            'title': getattr(draft, 'title', 'Untitled Draft'),
            'status': 'draft',
            'content': f"{content}\n\n<p><strong>Responsible Gambling Notice:</strong> Please gamble responsibly. Only bet what you can afford to lose. If you need help, seek professional advice.</p>"
        }

        try:
            response = request_with_retry('POST', f"{self.site_url}/wp-json/wp/v2/posts", json=payload, headers=self.headers, auth=self.auth, timeout=15)
            status_code = getattr(response, 'status_code', 200)
            data = response.json()
            if status_code not in (200, 201, None) and not isinstance(data, dict):
                return None
            if isinstance(data, dict) and data.get('id') is not None:
                return str(data.get('id'))
            if status_code in (200, 201):
                return str(data.get('id', '')) if isinstance(data, dict) else None
            return None
        except Exception as exc:
            logger.warning(f"WordPress draft push failed: {exc}")
            return None
