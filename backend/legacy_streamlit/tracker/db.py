import os

import streamlit as st
from dotenv import load_dotenv
from pymongo import MongoClient


@st.cache_resource
def get_db():
    load_dotenv()
    uri = os.getenv("MONGODB_URI", "")
    if not uri:
        st.error("Missing MONGODB_URI. Set it in your .env or env vars.")
        st.stop()
    client = MongoClient(uri)
    db_name = os.getenv("MONGODB_DB", "trade_tracker")
    return client[db_name]
