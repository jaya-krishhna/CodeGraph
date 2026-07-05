import sys
sys.path.insert(0, "demo_repo")

import db
from auth import models, jwt_auth, dependencies
from crud import projects, tasks, comments
from notifications import notifier
from rag_service import retriever

print("All modules imported successfully.")

u = models.new_user("alice", "alice@example.com", "hashedpw", user_id=1)
db.get_db().insert("users", u.model_dump())
token = jwt_auth.create_access_token(u)
print("token issued:", token.access_token[:20], "...")

user_out = dependencies.get_current_user(f"Bearer {token.access_token}")
print("resolved current user:", user_out)

proj = projects.create_project("Demo Project", "desc", user_out)
task = tasks.create_task(proj["id"], "Write tests", user_out)
comments.create_comment(task["id"], "lgtm", user_out)
notifier.notify_task_assigned(user_out.id, task["title"])
print("unread notifications:", notifier.list_unread(user_out.id))

retriever.index_document("FastAPI JWT auth uses HS256 signed tokens.")
retriever.index_document("The RAG retriever is a standalone bag-of-words index.")
print("rag hits:", retriever.retrieve("JWT tokens"))

print("\nSMOKE TEST PASSED")
