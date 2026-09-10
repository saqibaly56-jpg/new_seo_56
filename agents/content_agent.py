import json
import random
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from utils.logger import get_logger
from agents.discovery_agent import Candidate
from adapters.themes.appyn import AppynAdapter
from utils.openrouter import OpenRouterClient
from config.settings import settings
from core.universal_model import ContentDocument, SeoMetadata, Section, FAQ

logger = get_logger("content_agent")

@dataclass
class ArticleDraft:
    title: str
    body: str
    facts_used: Dict[str, Any]

class ContentAgent:
    def draft_article(self, candidate: Candidate, context: Dict[str, Any], verified_facts: Dict[str, Any], template: Optional[Dict[str, Any]] = None) -> ContentDocument:
        """
        Drafts the article using context, verified facts, and selected template structure.
        Outputs directly to the Universal Content Model (ContentDocument) with stable section_ids.
        """
        logger.info(f"Drafting article for {candidate.game_name} via OpenRouter JSON mode...")
        
        client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
        )
        
        template_instructions = ""
        if template and template.get("sections"):
            t_secs = template["sections"]
            lines = []
            for idx, ts in enumerate(t_secs, 1):
                sec_id = ts.get("id", "")
                name = ts.get("name", "")
                req = "REQUIRED" if ts.get("required") else "OPTIONAL"
                c_type = ts.get("content_type", "paragraph")
                ai_inst = ts.get("ai_instruction", "")
                lines.append(f"{idx}. Heading: '{name}' [section_id: '{sec_id}'] ({req}, format: {c_type}). Instruction: {ai_inst}")
            template_instructions = "TEMPLATE SECTIONS TO GENERATE:\n" + "\n".join(lines) + "\n\n"
        else:
            template_instructions = (
                "MANDATORY SECTIONS (Ensure these headings exist in the sections array):\n"
                "1. Features (Must be at least 300 words)\n"
                "2. Pros and Cons (use <ul> for lists in content, must be at least 200 words)\n"
                "3. How to Get Started (Register, Login, Download) (Must be at least 250 words)\n"
                "4. How to Deposit & Withdraw Money (Must be at least 250 words)\n"
                "5. Games/Bet Types Available (Must be at least 250 words)\n"
                "6. Rewards and Bonuses (Must be at least 200 words)\n"
                "7. Personal Review (MUST begin the content with the exact phrase 'By our expert,')\n"
                "8. Who This Game Suits (MUST use this exact heading text)\n"
                "9. How It Compares (MUST include the word 'comparison' in the content)\n\n"
            )

        system_prompt = (
            "You are an expert casino game reviewer writing for a Pakistani iGaming SEO blog. "
            "Write a highly engaging, SEO-optimized review. "
            "Use Verified Facts when provided. If a fact is missing, do not invent numbers, bonus percentages, RTP, maximum wins, or other specific figures; omit the claim or state that it requires verification.\n\n"
            "CRITICAL SEO INSTRUCTIONS:\n"
            "1. The Focus Keyword is EXACTLY the game name provided.\n"
            "2. You MUST use the Focus Keyword at the very beginning of the SEO meta description.\n"
            "3. You MUST use the Focus Keyword in the introduction (first 10% of the content).\n"
            "4. You MUST use the Focus Keyword in at least 2 section headings.\n"
            "5. You MUST maintain a Keyword Density of around 1% to 1.5%.\n"
            "6. You MUST include at least one DoFollow external link to an authoritative resource.\n"
            "7. You MUST include at least one internal link.\n"
            "8. You MUST bold important LSI keywords using HTML <strong> tags ONLY. Do NOT use **markdown**.\n"
            "9. MANDATORY LENGTH REQUIREMENT: The total word count MUST exceed 1500 words. To achieve this, EACH SECTION must contain at least 250-300 words of detailed, descriptive text. Do not summarize; write extensively.\n\n"
            f"{template_instructions}"
            "OUTPUT FORMAT: You MUST return a valid JSON object matching the following structure exactly:\n"
            "{\n"
            '  "title": "A catchy title including the Focus Keyword, a power word, and 2026",\n'
            '  "seo_metadata": {\n'
            '    "focus_keyword": "exact game name",\n'
            '    "meta_description": "1-2 sentence catchy SEO meta description starting with the Focus Keyword",\n'
            '    "meta_title": "Optimized SEO title"\n'
            '  },\n'
            '  "introduction": "2-3 long paragraphs introducing the game/platform (use <p> tags)",\n'
            '  "sections": [\n'
            '    {\n'
            '      "section_id": "MUST exactly match the section_id provided in the instructions",\n'
            '      "heading": "Must exactly match the Heading provided in the instructions",\n'
            '      "content": "<p>Intro to features</p>",\n'
            '      "subsections": []\n'
            '    }\n'
            '  ],\n'
            '  "faqs": [\n'
            '    {"question": "Is it safe?", "answer": "Yes..."}\n'
            '  ],\n'
            '  "conclusion": "2 long paragraphs, ending with a responsible-gaming reminder (use <p> tags)"\n'
            "}\n\n"
            "Return ONLY the raw JSON object. Do not wrap it in ```json blocks."
        )
        
        user_prompt = f"Game: {candidate.game_name}\nProvider: {candidate.provider}\nContext: {json.dumps(context)}\nVerified Facts: {json.dumps(verified_facts)}"
        
        try:
            try:
                response = client.chat.completions.create(
                    model=settings.openrouter_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4500,
                    response_format={"type": "json_object"}
                )
            except Exception as e:
                if '429' in str(e) or 'rate_limit' in str(e).lower():
                    logger.warning("OpenRouter rate limit hit for primary model. Retrying with the configured model...")
                    response = client.chat.completions.create(
                        model=settings.openrouter_model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=0.7,
                        max_tokens=4000,
                        response_format={"type": "json_object"}
                    )
                else:
                    raise e

            raw_json = response.choices[0].message.content
            raw_json = raw_json.strip()
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:]
            if raw_json.endswith("```"):
                raw_json = raw_json[:-3]
                
            data = json.loads(raw_json)
            
            # Providers sometimes double-encode: the result is a string instead of a dict
            if isinstance(data, str):
                data = json.loads(data)
            
            if not isinstance(data, dict):
                raise ValueError(f"OpenRouter returned unexpected type: {type(data)}")
            
            clean_game_name = candidate.game_name.replace('-', ' ').title()
            
            seo_raw = data.get("seo_metadata", {})
            if not isinstance(seo_raw, dict):
                seo_raw = {"focus_keyword": clean_game_name, "meta_description": ""}
            seo = SeoMetadata(**seo_raw)
            
            sections = []
            tmpl_secs_by_name = {}
            if template and template.get("sections"):
                for ts in template["sections"]:
                    tmpl_secs_by_name[ts.get("name", "").lower().strip()] = ts.get("id", "")

            for sec in data.get("sections", []):
                if not isinstance(sec, dict):
                    continue
                subsections = []
                for sub in sec.get("subsections", []):
                    if not isinstance(sub, dict):
                        continue
                    sub_c = sub.get("content", "")
                    if isinstance(sub_c, list):
                        sub_c = "\n".join(sub_c)
                    subsections.append(Section(heading=sub.get("heading", ""), content=sub_c, subsections=[]))
                
                sec_c = sec.get("content", "")
                if isinstance(sec_c, list):
                    sec_c = "\n".join(sec_c)
                    
                heading_text = sec.get("heading", "")
                sec_id_from_ai = sec.get("section_id") or sec.get("id") or ""
                # Force heading match if available
                sec_id = tmpl_secs_by_name.get(heading_text.lower().strip(), "")
                if not sec_id:
                    # If heading didn't match, maybe AI kept the section_id but changed heading
                    if str(sec_id_from_ai) in [str(x) for x in tmpl_secs_by_name.values()]:
                        sec_id = str(sec_id_from_ai)
                    else:
                        sec_id = sec_id_from_ai
                
                sections.append(Section(
                    section_id=sec_id,
                    heading=heading_text,
                    content=sec_c,
                    subsections=subsections
                ))
                
            faqs_raw = data.get("faqs", [])
            faqs = []
            for faq in faqs_raw:
                if isinstance(faq, dict):
                    faqs.append(FAQ(**faq))
            
            intro_data = data.get("introduction", "")
            if isinstance(intro_data, list):
                intro_data = "\n".join(intro_data)
                
            conc_data = data.get("conclusion", "")
            if isinstance(conc_data, list):
                conc_data = "\n".join(conc_data)
                
            doc = ContentDocument(
                title=data.get("title", f"Ultimate {clean_game_name} Review"),
                seo_metadata=seo,
                introduction=intro_data,
                sections=sections,
                conclusion=conc_data,
                faqs=faqs,
                custom_fields={"verified_facts": verified_facts}
            )
            AppynAdapter.ensure_custom_fields(doc)
            
            logger.info(f"Draft generated for {candidate.game_name}.")
            return doc
            
        except Exception as e:
            logger.error(f"Failed to generate structured draft with OpenRouter: {e}")
            return ContentDocument(
                title=f"Fallback {candidate.game_name}",
                seo_metadata=SeoMetadata(focus_keyword=candidate.game_name, meta_description=""),
                introduction="Generation failed.",
                sections=[],
                conclusion=""
            )

def check_differentiation(doc: Any) -> bool:
    """
    Ensures the draft contains at least one of the expected editorial markers.
    Accepts either a structured document, an ArticleDraft, or a raw string.
    """
    if isinstance(doc, str):
        full_text = doc.lower()
    elif hasattr(doc, "body"):
        full_text = str(doc.body).lower()
    elif isinstance(doc, ContentDocument):
        full_text = doc.introduction.lower()
        for sec in doc.sections:
            full_text += " " + sec.heading.lower() + " " + sec.content.lower()
            for sub in sec.subsections:
                full_text += " " + sub.heading.lower() + " " + sub.content.lower()
    else:
        full_text = str(doc or "").lower()

    required_markers = [
        "by our expert",
        "who this game suits",
        "compar"
    ]

    if not any(marker in full_text for marker in required_markers):
        logger.warning("Differentiation check: Draft is missing mandatory editorial markers.")
        return False

    return True
