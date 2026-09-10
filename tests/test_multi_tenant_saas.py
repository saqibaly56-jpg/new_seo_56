import os
import json
import uuid
import pytest
from unittest import mock
from fastapi.testclient import TestClient

from dashboard.app import app
from utils.db_models import SessionLocal, User, Job, JobEvent, Worker, UserSettings, ContentDraft, Subscription, ImageAsset
from dashboard.auth import hash_password, generate_session_token
from agents.content_agent import ContentAgent
from agents.discovery_agent import Candidate
from services.subscription_service import check_user_quota
from utils.db import get_db_connection

client = TestClient(app)

@pytest.fixture
def setup_test_users():
    with SessionLocal() as db:
        # Create User A (Normal User)
        user_a = db.query(User).filter(User.email == "usera@test.com").first()
        if not user_a:
            user_a = User(
                email="usera@test.com",
                password_hash=hash_password("PasswordA123!"),
                role="user",
                subscription_plan="free"
            )
            db.add(user_a)
            db.commit()
            db.refresh(user_a)
            sub_a = Subscription(user_id=user_a.id, plan="free", article_limit=5)
            db.add(sub_a)
            db.commit()

        # Create User B (Normal User)
        user_b = db.query(User).filter(User.email == "userb@test.com").first()
        if not user_b:
            user_b = User(
                email="userb@test.com",
                password_hash=hash_password("PasswordB123!"),
                role="user",
                subscription_plan="free"
            )
            db.add(user_b)
            db.commit()
            db.refresh(user_b)

        # Create Admin User
        admin = db.query(User).filter(User.email == "admin@test.com").first()
        if not admin:
            admin = User(
                email="admin@test.com",
                password_hash=hash_password("AdminPass123!"),
                role="admin",
                subscription_plan="business"
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        yield {
            "user_a_id": user_a.id,
            "user_b_id": user_b.id,
            "admin_id": admin.id
        }

def test_missing_facts_do_not_enable_fabricated_claims():
    """
    Verifies that missing facts are not passed to the model as permission to fabricate claims.
    """
    agent = ContentAgent()
    candidate = Candidate(game_name="Sweet Bonanza", provider="Pragmatic Play", source_url="https://example.com")
    context = {"theme": "Candy"}
    empty_facts = {} # Facts missing!
    
    with mock.patch("agents.content_agent.OpenRouterClient") as mock_client_class:
        mock_groq_client = mock.Mock()
        mock_client_class.return_value = mock_groq_client
        
        mock_response = mock.Mock()
        mock_response.choices = [
            mock.Mock(message=mock.Mock(content=json.dumps({
                "title": "Sweet Bonanza Review 2026",
                "seo_metadata": {"focus_keyword": "Sweet Bonanza", "meta_description": "Sweet Bonanza review"},
                "introduction": "<p>By our expert, introducing game...</p>",
                "sections": [{"heading": "Who This Game Suits", "content": "<p>Comparison details...</p>"}],
                "conclusion": "<p>Conclusion text...</p>",
                "faqs": []
            })))
        ]
        mock_groq_client.chat.completions.create.return_value = mock_response
        
        doc = agent.draft_article(candidate, context, empty_facts)
        assert doc is not None
        assert "Sweet Bonanza" in doc.title
        
        # The agent must explicitly prohibit fabricated factual figures.
        system_prompt_arg = mock_groq_client.chat.completions.create.call_args[1]["messages"][0]["content"]
        assert "do not invent" in system_prompt_arg.lower()

def test_tenant_data_isolation(setup_test_users):
    """
    Verifies User A cannot access User B's jobs or timeline.
    """
    user_a_id = setup_test_users["user_a_id"]
    user_b_id = setup_test_users["user_b_id"]
    
    job_b_id = f"job-userb-secret-{uuid.uuid4().hex[:6]}"
    with SessionLocal() as db:
        job = Job(id=job_b_id, user_id=user_b_id, game_name="Secret B Game", provider="Provider B", status="QUEUED")
        event = JobEvent(job_id=job_b_id, user_id=user_b_id, event_type="JOB_CREATED", stage="QUEUED", status="QUEUED")
        db.add(job)
        db.add(event)
        db.commit()
        
    # User A tries to fetch User B's timeline
    with SessionLocal() as db:
        # Create session token for User A
        token_a = generate_session_token()
        from utils.db import get_db_connection
        with get_db_connection() as conn:
            conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token_a, user_a_id))
            conn.commit()
            
    client.cookies.set("session_token", token_a)
    res = client.get(f"/api/user/jobs/{job_b_id}/timeline")
    assert res.status_code == 403 # Forbidden!

def test_admin_rbac_protection(setup_test_users):
    """
    Verifies normal users are denied access to /api/admin/* endpoints.
    """
    user_a_id = setup_test_users["user_a_id"]
    token_a = generate_session_token()
    from utils.db import get_db_connection
    with get_db_connection() as conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token_a, user_a_id))
        conn.commit()
        
    client.cookies.set("session_token", token_a)
    res = client.get("/api/admin/stats")
    assert res.status_code == 403 # Admin access denied!

def test_image_file_and_job_link_are_tenant_scoped(setup_test_users, tmp_path):
    user_a_id = setup_test_users["user_a_id"]
    user_b_id = setup_test_users["user_b_id"]
    job_b_id = f"job-userb-image-{uuid.uuid4().hex[:6]}"
    image_path = tmp_path / "private.jpg"
    image_path.write_bytes(b"not-a-real-image")

    with SessionLocal() as db:
        db.add(Job(id=job_b_id, user_id=user_b_id, game_name="Private", provider="Provider", status="QUEUED"))
        db.add(ImageAsset(
            id=f"img-{uuid.uuid4().hex[:12]}", user_id=user_b_id, filename="private.jpg",
            file_path=str(image_path), mime_type="image/jpeg", width=1, height=1, file_size=16
        ))
        db.commit()
        image_id = db.query(ImageAsset).filter(ImageAsset.user_id == user_b_id).order_by(ImageAsset.created_at.desc()).first().id

    token_a = generate_session_token()
    with get_db_connection() as conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token_a, user_a_id))
        conn.commit()
    client.cookies.set("session_token", token_a)

    assert client.get(f"/api/images/{image_id}/file").status_code == 404
    response = client.post("/api/images/link-job", json={"job_id": job_b_id, "image_ids": [image_id]})
    assert response.status_code == 404

def test_subscription_quota_enforcement(setup_test_users):
    """
    Verifies user article quotas are enforced.
    """
    user_a_id = setup_test_users["user_a_id"]
    assert check_user_quota(user_a_id) is True
