"""Small accessibility fallback; the primary UI is the React command center served by FastAPI."""
import duckdb
import streamlit as st

from src.config import settings

st.set_page_config(page_title="AdShield AI", layout="wide")
st.title("AdShield AI — Commercial Ads Risk Governance Copilot")
st.caption("Real public data only · deterministic fallback enabled")
if not settings.db_path.exists():
    st.warning("Run `make ingest && make transform` first.")
else:
    with duckdb.connect(str(settings.db_path), read_only=True) as db:
        st.dataframe(db.execute("SELECT case_id, source, risk_score, risk_category, severity, recommended_action FROM ad_risk_scores ORDER BY risk_score DESC LIMIT 200").fetchdf(), use_container_width=True)
