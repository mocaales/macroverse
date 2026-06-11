import base64
import json
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client

from app.core.config import get_settings


def _credential():
    encoded = get_settings().firebase_service_account_base64
    if not encoded:
        return None
    payload = json.loads(base64.b64decode(encoded).decode("utf-8"))
    return credentials.Certificate(payload)


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        settings = get_settings()
        options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None
        return firebase_admin.initialize_app(_credential(), options)


@lru_cache
def get_firestore_client() -> Client:
    return firestore.client(app=get_firebase_app())
