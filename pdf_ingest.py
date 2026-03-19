import re
from typing import Dict, Any
import pandas as pd
import pdfplumber


def _money_to_float(x: str):
    if x is None:
        return None
    x = str(x).strip()
    if not x:
        return None
    x = x.replace("$", "").replace(",", "").replace(" ", "")
    try:
        return float(x)
    except ValueError:
        return None


def _num_to_float(x: str):
    if x is None:
        return None
    x = str(x).strip().replace(",", "")
    if not x:
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _extract_number_of_properties(text: str, section_label: str):
    # Example: "RESIDENTIAL - Active ... Number of Properties: 5"
    pattern = rf"{section_label}.*?Number of Properties:\s*([0-9]+)"
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return int(m.group(1)) if m else None


def _extract_community(text: str):
    # Pull first visible community in row area, e.g. "Glen Allan"
    # This is heuristic; can be tightened after first few real PDFs
    m = re.search(r"\b(Glen\s+Allan|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", text)
    return m.group(1) if m else "Unknown"


def _extract_med_dom_and_prices(text: str) -> Dict[str, Any]:
    """
    Try to find 'Med' summary row in Active/Sold sections.
    In your sample:
      Active Med row has DOM and List$
      Sold area has sold rows; we approximate median sold from sold values if needed.
    """
    result = {
        "median_dom_sold": None,
        "median_list_price": None,
        "median_sold_price": None,
    }

    # Active "Med" row often includes DOM and List$
    # Example line fragments: "Med ... DOM 8 ... $595,000 ..."
    med_line_candidates = re.findall(r"^.*\bMed\b.*$", text, flags=re.IGNORECASE | re.MULTILINE)
    if med_line_candidates:
        line = med_line_candidates[0]
        # grab first integer near DOM-like location
        dom_match = re.search(r"\b([0-9]{1,3})\b", line)
        if dom_match:
            result["median_dom_sold"] = float(dom_match.group(1))
        money_vals = re.findall(r"\$[0-9,]+", line)
        if money_vals:
            result["median_list_price"] = _money_to_float(money_vals[0])

    # Sold$ column values from sold rows -> compute median if possible
    sold_money = re.findall(r"\$[0-9]{2,3},[0-9]{3}", text)
    sold_vals = [_money_to_float(v) for v in sold_money if _money_to_float(v) is not None]
    if sold_vals:
        result["median_sold_price"] = float(pd.Series(sold_vals).median())

    return result


def parse_paragon_cma_pdf(file_like, period: str) -> pd.DataFrame:
    """
    Returns a single-row dataframe matching app schema.
    """
    all_text = []
    with pdfplumber.open(file_like) as pdf:
        for p in pdf.pages:
            t = p.extract_text() or ""
            all_text.append(t)

    text = "\n".join(all_text)

    active_listings = _extract_number_of_properties(text, r"RESIDENTIAL\s*-\s*Active")
    closed_sales = _extract_number_of_properties(text, r"RESIDENTIAL\s*-\s*Sold")
    pending_listings = 0  # usually not present in this report; set default

    med = _extract_med_dom_and_prices(text)
    neighborhood = _extract_community(text)
    city = "Unknown"

    row = {
        "period": period,
        "neighborhood": neighborhood,
        "city": city,
        "active_listings": active_listings if active_listings is not None else 0,
        "pending_listings": pending_listings,
        "closed_sales": closed_sales if closed_sales is not None else 0,
        "median_dom_sold": med["median_dom_sold"] if med["median_dom_sold"] is not None else 0,
        "median_sold_price": med["median_sold_price"] if med["median_sold_price"] is not None else 0,
        "median_list_price": med["median_list_price"] if med["median_list_price"] is not None else 0,
    }

    df = pd.DataFrame([row])

    # hard clean numeric fields
    for c in [
        "active_listings",
        "pending_listings",
        "closed_sales",
        "median_dom_sold",
        "median_sold_price",
        "median_list_price",
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df