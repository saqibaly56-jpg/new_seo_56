import uuid
import datetime
from typing import List, Dict, Any, Optional
from utils.db_models import SessionLocal, ContentTemplate, TemplateSection, User
from core.universal_model import ContentTemplateCreate, TemplateSectionSchema

DEFAULT_SECTIONS = [
    {"name": "Features", "order": 1, "required": True, "content_type": "paragraph", "ai_instruction": "Detail key features of the platform or game."},
    {"name": "Pros and Cons", "order": 2, "required": True, "content_type": "bullet_list", "ai_instruction": "List benefits and minor drawbacks using HTML <ul>/<li> tags."},
    {"name": "How to Get Started", "order": 3, "required": True, "content_type": "paragraph", "ai_instruction": "Explain registration, login, and access steps."},
    {"name": "How to Deposit & Withdraw Money", "order": 4, "required": True, "content_type": "paragraph", "ai_instruction": "Detail payment methods, limits, and processing times."},
    {"name": "Games/Bet Types Available", "order": 5, "required": True, "content_type": "paragraph", "ai_instruction": "Describe available categories, odds, and game modes."},
    {"name": "Rewards and Bonuses", "order": 6, "required": True, "content_type": "paragraph", "ai_instruction": "Explain promotional offers and wagering terms."},
    {"name": "Personal Review", "order": 7, "required": True, "content_type": "paragraph", "ai_instruction": "MUST begin the section content with the exact phrase 'By our expert,'."},
    {"name": "Who This Game Suits", "order": 8, "required": True, "content_type": "paragraph", "ai_instruction": "Target audience breakdown."},
    {"name": "How It Compares", "order": 9, "required": True, "content_type": "paragraph", "ai_instruction": "MUST include the word 'comparison' in the content."}
]

from sqlalchemy.orm import joinedload

def seed_default_template(user_id: int) -> ContentTemplate:
    """
    Ensures a default template with stable UUID section_ids exists for the user.
    """
    with SessionLocal() as db:
        tmpl = db.query(ContentTemplate).options(joinedload(ContentTemplate.sections)).filter(ContentTemplate.user_id == user_id, ContentTemplate.is_default == True).first()
        if not tmpl:
            tmpl = ContentTemplate(
                user_id=user_id,
                name="Default Optimized Format",
                description="Predefined optimized structure for SEO reviews",
                mode="default",
                is_default=True,
                version=1
            )
            db.add(tmpl)
            db.commit()
            db.refresh(tmpl)
            
            for s in DEFAULT_SECTIONS:
                sec_id = f"sec-{uuid.uuid4().hex[:12]}"
                sec = TemplateSection(
                    id=sec_id,
                    template_id=tmpl.id,
                    name=s["name"],
                    order=s["order"],
                    required=s["required"],
                    content_type=s["content_type"],
                    ai_instruction=s["ai_instruction"]
                )
                db.add(sec)
            db.commit()
            tmpl = db.query(ContentTemplate).options(joinedload(ContentTemplate.sections)).filter(ContentTemplate.id == tmpl.id).first()
        return tmpl

def get_user_templates(user_id: int) -> List[Dict[str, Any]]:
    seed_default_template(user_id)
    with SessionLocal() as db:
        templates = db.query(ContentTemplate).filter(ContentTemplate.user_id == user_id).all()
        result = []
        for t in templates:
            sec_list = [
                {
                    "id": s.id,
                    "name": s.name,
                    "order": s.order,
                    "required": s.required,
                    "content_type": s.content_type,
                    "ai_instruction": s.ai_instruction
                }
                for s in t.sections
            ]
            result.append({
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "mode": t.mode,
                "is_default": t.is_default,
                "version": t.version,
                "sections": sec_list
            })
        return result

def get_template_by_id(template_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with SessionLocal() as db:
        t = db.query(ContentTemplate).filter(ContentTemplate.id == template_id, ContentTemplate.user_id == user_id).first()
        if not t:
            return None
        sec_list = [
            {
                "id": s.id,
                "name": s.name,
                "order": s.order,
                "required": s.required,
                "content_type": s.content_type,
                "ai_instruction": s.ai_instruction
            }
            for s in t.sections
        ]
        return {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "mode": t.mode,
            "is_default": t.is_default,
            "version": t.version,
            "sections": sec_list
        }

def create_custom_template(user_id: int, payload: ContentTemplateCreate) -> ContentTemplate:
    with SessionLocal() as db:
        tmpl = ContentTemplate(
            user_id=user_id,
            name=payload.name,
            description=payload.description or "",
            mode=payload.mode,
            is_default=payload.is_default,
            version=1
        )
        db.add(tmpl)
        db.commit()
        db.refresh(tmpl)
        
        for idx, sec_data in enumerate(payload.sections):
            sec_id = sec_data.id or f"sec-{uuid.uuid4().hex[:12]}"
            sec = TemplateSection(
                id=sec_id,
                template_id=tmpl.id,
                name=sec_data.name,
                order=sec_data.order or (idx + 1),
                required=sec_data.required,
                content_type=sec_data.content_type,
                ai_instruction=sec_data.ai_instruction
            )
            db.add(sec)
        db.commit()
        db.refresh(tmpl)
        return tmpl

def duplicate_template(template_id: int, user_id: int) -> Optional[ContentTemplate]:
    with SessionLocal() as db:
        src = db.query(ContentTemplate).filter(ContentTemplate.id == template_id, ContentTemplate.user_id == user_id).first()
        if not src:
            return None
            
        dup = ContentTemplate(
            user_id=user_id,
            name=f"{src.name} (Copy)",
            description=src.description,
            mode=src.mode,
            is_default=False,
            version=1
        )
        db.add(dup)
        db.commit()
        db.refresh(dup)
        
        for s in src.sections:
            sec_id = f"sec-{uuid.uuid4().hex[:12]}"
            sec = TemplateSection(
                id=sec_id,
                template_id=dup.id,
                name=s.name,
                order=s.order,
                required=s.required,
                content_type=s.content_type,
                ai_instruction=s.ai_instruction
            )
            db.add(sec)
        db.commit()
        db.refresh(dup)
        return dup

def set_template_default(template_id: int, user_id: int) -> bool:
    with SessionLocal() as db:
        db.query(ContentTemplate).filter(ContentTemplate.user_id == user_id).update({"is_default": False})
        t = db.query(ContentTemplate).filter(ContentTemplate.id == template_id, ContentTemplate.user_id == user_id).first()
        if t:
            t.is_default = True
            db.commit()
            return True
        db.commit()
        return False

def delete_template(template_id: int, user_id: int) -> bool:
    with SessionLocal() as db:
        t = db.query(ContentTemplate).filter(ContentTemplate.id == template_id, ContentTemplate.user_id == user_id).first()
        if not t or t.is_default:
            return False
        db.delete(t)
        db.commit()
        return True
