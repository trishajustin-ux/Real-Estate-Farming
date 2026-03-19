import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "period",
    "neighborhood",
    "city",
    "active_listings",
    "pending_listings",
    "closed_sales",
    "median_dom_sold",
    "median_sold_price",
]

def validate_input(df: pd.DataFrame, config: dict):
    errors = []
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    if "list_to_sale_ratio_pct" not in df.columns and "median_list_price" not in df.columns:
        errors.append("Provide either 'list_to_sale_ratio_pct' or 'median_list_price'.")

    for c in ["active_listings", "pending_listings", "closed_sales", "median_dom_sold", "median_sold_price"]:
        if c in df.columns:
            if pd.to_numeric(df[c], errors="coerce").isna().any():
                errors.append(f"Column has non-numeric values: {c}")

    return (len(errors) == 0), errors

def prepare_metrics(df: pd.DataFrame):
    d = df.copy()

    for c in ["active_listings", "pending_listings", "closed_sales", "median_dom_sold", "median_sold_price"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    if "list_to_sale_ratio_pct" in d.columns:
        d["list_to_sale_ratio_pct"] = pd.to_numeric(d["list_to_sale_ratio_pct"], errors="coerce")
    else:
        d["median_list_price"] = pd.to_numeric(d["median_list_price"], errors="coerce")
        d["list_to_sale_ratio_pct"] = np.where(
            d["median_list_price"] > 0,
            (d["median_sold_price"] / d["median_list_price"]) * 100.0,
            np.nan,
        )

    monthly_sales_rate = d["closed_sales"] / 12.0
    d["months_supply"] = np.where(monthly_sales_rate > 0, d["active_listings"] / monthly_sales_rate, np.nan)
    d["demand_pressure"] = np.where(
        d["active_listings"] > 0,
        (d["pending_listings"] + monthly_sales_rate) / d["active_listings"],
        np.nan,
    )

    return d

def minmax(series: pd.Series, higher_better=True):
    s = series.astype(float)
    if s.nunique(dropna=True) <= 1:
        base = pd.Series([50.0] * len(s), index=s.index)
    else:
        base = (s - s.min()) / (s.max() - s.min()) * 100.0
    return base if higher_better else (100.0 - base)

def tier(score):
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    return "C"

def score_neighborhoods(df: pd.DataFrame, config: dict):
    d = df.copy()

    for m in config["metrics"]:
        metric = m["name"]
        direction = m["direction"]
        d[f"{metric}_score"] = minmax(d[metric], higher_better=(direction == "higher_better"))

    d["total_score"] = 0.0
    for m in config["metrics"]:
        metric = m["name"]
        weight = m["weight"]
        d["total_score"] += d[f"{metric}_score"] * weight

    d["total_score"] = d["total_score"].round(2)
    d["tier"] = d["total_score"].apply(tier)
    d = d.sort_values("total_score", ascending=False).reset_index(drop=True)
    d["rank"] = d.index + 1

    metric_score_cols = [f'{m["name"]}_score' for m in config["metrics"]]
    labels = {m["name"]: m["label"] for m in config["metrics"]}

    pos_drivers = []
    neg_drivers = []
    for _, row in d.iterrows():
        vals = {c.replace("_score", ""): row[c] for c in metric_score_cols}
        top_pos = sorted(vals.items(), key=lambda x: x[1], reverse=True)[:3]
        top_neg = sorted(vals.items(), key=lambda x: x[1])[:3]
        pos_drivers.append(", ".join([labels[k] for k, _ in top_pos]))
        neg_drivers.append(", ".join([labels[k] for k, _ in top_neg]))

    d["top_positive_drivers"] = pos_drivers
    d["top_negative_drivers"] = neg_drivers

    return d
