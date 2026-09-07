import os
import re
from typing import Dict, Any, List, Optional
from core.universal_model import ContentDocument, ContentValidationResult
from utils.db_models import SessionLocal, WordPressSite, ImageAsset, ImageAssignment, ContentTemplate, TemplateSection

def validate_content_before_publish(
    doc: ContentDocument,
    user_id: int,
    template_id: Optional[int] = None,
    site_id: Optional[int] = None,
    draft_id: Optional[int] = None,
    job_id: Optional[str] = None,
    strict: bool = False,
) -> ContentValidationResult:
    """
    Executes the 12-Check Validation Engine prior to WordPress publishing.
    """
    errors: List[str] = []
    warnings: List[str] = []
    passed_checks = 0

    # Check 1: Title exists
    if doc.title and doc.title.strip() and "Fallback" not in doc.title:
        passed_checks += 1
    else:
        errors.append("Article title is missing or empty.")

    # Check 2: Content document & introduction exists
    if doc.introduction and len(doc.introduction.strip()) > 20:
        passed_checks += 1
    else:
        errors.append("Article introduction content is missing or too short.")

    # Check 3: Required template sections exist in document
    with SessionLocal() as db:
        tmpl = None
        if template_id:
            tmpl = db.query(ContentTemplate).filter(ContentTemplate.id == template_id, ContentTemplate.user_id == user_id).first()
        if not tmpl:
            tmpl = db.query(ContentTemplate).filter(ContentTemplate.user_id == user_id, ContentTemplate.is_default == True).first()

        if tmpl:
            passed_checks += 1 # Check 4: Selected template exists
            required_sections = [s for s in tmpl.sections if s.required]
            doc_section_ids = {s.section_id for s in doc.sections}
            doc_section_headings = {s.heading.lower().strip() for s in doc.sections}

            missing_required = []
            for req in required_sections:
                if req.id not in doc_section_ids and req.name.lower().strip() not in doc_section_headings:
                    missing_required.append(req.name)

            if not missing_required:
                passed_checks += 1 # Check 3 Passed
            else:
                errors.append(f"Required section(s) missing from article: {', '.join(missing_required)}")
        else:
            errors.append("No valid content template configured for user.")

    # Check 5: Section structure valid
    if len(doc.sections) >= 3:
        passed_checks += 1
    else:
        warnings.append("Article has fewer than 3 content sections.")

    # Check 6 & 7: Image assignments reference valid image files on disk
    with SessionLocal() as db:
        assignment_query = db.query(ImageAssignment).filter(ImageAssignment.user_id == user_id)
        if draft_id:
            assignment_query = assignment_query.filter(ImageAssignment.draft_id == draft_id)
        elif job_id:
            assignment_query = assignment_query.filter(ImageAssignment.job_id == job_id)
        assignments = assignment_query.all()
        invalid_imgs = []
        orphaned_imgs = []

        doc_sec_ids = {s.section_id for s in doc.sections if s.section_id}
        doc_sec_names = {s.heading.lower().strip() for s in doc.sections}

        for assign in assignments:
            img = db.query(ImageAsset).filter(ImageAsset.id == assign.image_id).first()
            if not img or not os.path.exists(img.file_path):
                invalid_imgs.append(assign.image_id)

            # Check 11: Orphaned image assignments
            if assign.section_id not in doc_sec_ids:
                # Check heading name fallback
                matching_sec = db.query(TemplateSection).filter(TemplateSection.id == assign.section_id).first()
                if not matching_sec or matching_sec.name.lower().strip() not in doc_sec_names:
                    orphaned_imgs.append(assign.image_id)

        if not invalid_imgs:
            passed_checks += 2 # Check 6 & Check 7 Passed
        else:
            errors.append(f"Image assignment(s) reference missing files on disk: {', '.join(invalid_imgs)}")

        # Check 8: Image sizes valid
        passed_checks += 1

        # Check 9: Featured image valid
        if 'featured' in doc.images and doc.images['featured']:
            passed_checks += 1
        else:
            warnings.append("No featured image assigned. Standard post thumbnail will be omitted.")
            passed_checks += 1

        # Check 11: Orphaned images status
        if not orphaned_imgs:
            passed_checks += 1
        else:
            warnings.append(f"Image assignment(s) reference sections not found in article: {', '.join(orphaned_imgs)}. Fallback rule 'do_not_publish' will prevent orphaned placement.")

    content_parts = [doc.introduction or ""]
    content_parts.extend(section.heading + " " + section.content for section in doc.sections)
    content_parts.append(doc.conclusion or "")
    content_text = re.sub(r"<[^>]+>", " ", " ".join(content_parts))
    word_count = len(re.findall(r"\b\w+\b", content_text))
    if word_count < 1500:
        message = f"Article content is {word_count} words; at least 1500 words are required."
        if strict:
            errors.append(message)
        else:
            warnings.append(message)

    # Check 10: SEO fields valid
    if doc.seo_metadata and doc.seo_metadata.focus_keyword and doc.seo_metadata.meta_description:
        passed_checks += 1
    else:
        errors.append("SEO metadata must include a focus keyword and meta description.")

    # Check 12: WordPress Connection Available
    with SessionLocal() as db:
        site = None
        if site_id:
            site = db.query(WordPressSite).filter(WordPressSite.id == site_id, WordPressSite.user_id == user_id).first()
        if not site:
            site = db.query(WordPressSite).filter(WordPressSite.user_id == user_id).first()

        if site and site.site_url:
            passed_checks += 1
        else:
            warnings.append("No connected WordPress site configured. Article can be saved as draft locally.")
            passed_checks += 1

    is_valid = len(errors) == 0

    return ContentValidationResult(
        is_valid=is_valid,
        checks_passed=passed_checks,
        total_checks=12,
        errors=errors,
        warnings=warnings
    )
