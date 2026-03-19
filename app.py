import json
import streamlit as st
import pandas as pd
from scoring import validate_input, prepare_metrics, score_neighborhoods

st.set_page_config(page_title="Neighborhood Seller Targeting", layout="wide")
st.title("🏘️ Neighborhood Seller Targeting System")
st.caption("Upload CMA-style neighborhood data, then score and rank where to target sellers.")

with open("config/metrics.json", "r", encoding="utf-8") as f:
    default_config = json.load(f)

st.subheader("1) Upload Data")
uploaded = st.file_uploader("Upload CSV", type=["csv"])

st.subheader("2) Scoring Weights")
st.write("Adjust weights (auto-normalized to 100%).")

weight_cols = st.columns(len(default_config["metrics"]))
weight_inputs = {}
for i, m in enumerate(default_config["metrics"]):
    with weight_cols[i]:
        weight_inputs[m["name"]] = st.number_input(
            m["label"], min_value=0.0, max_value=100.0, value=float(m["weight"] * 100), step=1.0
        )

if uploaded is not None:
    df = pd.read_csv(uploaded)

    ok, errors = validate_input(df, default_config)
    if not ok:
        st.error("Input validation failed:")
        for e in errors:
            st.write(f"- {e}")
        st.stop()

    st.subheader("3) Preview Uploaded Data")
    st.dataframe(df, use_container_width=True)

    config = default_config.copy()
    total_ui_weight = sum(weight_inputs.values()) or 1.0
    for m in config["metrics"]:
        m["weight"] = weight_inputs[m["name"]] / total_ui_weight

    prepared = prepare_metrics(df)
    scored = score_neighborhoods(prepared, config)

    st.subheader("4) Ranked Neighborhoods")
    st.dataframe(
        scored[
            [
                "rank",
                "neighborhood",
                "city",
                "total_score",
                "tier",
                "top_positive_drivers",
                "top_negative_drivers",
            ]
        ],
        use_container_width=True,
    )

    st.subheader("5) Download Results")
    csv = scored.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download ranked results (CSV)",
        data=csv,
        file_name="neighborhood_rankings.csv",
        mime="text/csv",
    )
else:
    st.info("Upload a CSV to begin. Use data/template.csv as your starter format.")
