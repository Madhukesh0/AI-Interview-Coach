# -*- coding: utf-8 -*-
"""
auth.py - IBM Cloud IAM token retrieval.

Fetches a short-lived Bearer token from the IBM IAM endpoint using the
API key stored in st.secrets (Streamlit Cloud) or the .env file (local).
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

IAM_TOKEN_URL = "https://iam.cloud.ibm.com/identity/token"


def _get_api_key() -> str:
    """Read IAM_API_KEY from st.secrets (Streamlit Cloud) or os.environ (.env)."""
    try:
        import streamlit as st
        return st.secrets.get("IAM_API_KEY", "") or os.getenv("IAM_API_KEY", "")
    except Exception:
        return os.getenv("IAM_API_KEY", "")


def get_iam_token(api_key: str = "") -> str:
    """
    Exchange an IBM Cloud API key for a Bearer access token.

    Parameters
    ----------
    api_key : str
        Override the key from the environment (useful for testing).

    Returns
    -------
    str
        The raw access_token string (no "Bearer" prefix).

    Raises
    ------
    RuntimeError
        If the IAM endpoint returns a non-200 status or the response does
        not contain an access_token field.
    """
    key = api_key or _get_api_key()
    if not key:
        raise RuntimeError(
            "IAM_API_KEY is not set. Add it to your .env file or Streamlit secrets."
        )

    payload = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": key,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    resp = requests.post(IAM_TOKEN_URL, data=payload, headers=headers, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(
            f"IAM token request failed [{resp.status_code}]: {resp.text}"
        )

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in IAM response: {data}")

    return token
