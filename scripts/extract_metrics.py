"""Extract structured financial metrics from 10-K Balance Sheet, Income Statement, Cash Flow.

The financial tables are space-aligned with format:
    label  2025-09-27  2024-09-28  2023-09-30
    Revenue  416161000000.0  391035000000.0  ...

We extract only the FIRST value column (current filing year) for each section,
since each fiscal year has its own section record, avoiding duplicates.
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

INCOME_METRICS = {
    "Revenue": "net_sales",
    "Net Revenue": "net_sales",
    "Net Sales": "net_sales",
    "Cost of Revenue": "cost_of_sales",
    "Gross Profit": "gross_profit",
    "Research and Development Expense": "rd_expense",
    "Selling, General and Administrative Expense": "sga_expense",
    "Operating Expenses": "operating_expenses",
    "Operating Income": "operating_income",
    "Nonoperating Income/Expense": "nonoperating_income",
    "Income Before Tax": "income_before_tax",
    "Income Tax Expense": "income_tax",
    "Net Income": "net_income",
    "Earnings Per Share": "eps_basic",
    "Earnings Per Share (Diluted)": "eps_diluted",
    "Shares Outstanding": "shares_outstanding",
    "Shares Outstanding (Diluted)": "shares_diluted",
}

BALANCE_METRICS = {
    "Cash and Cash Equivalents": "cash_and_equivalents",
    "Marketable Securities": "marketable_securities_current",
    "Accounts Receivable": "accounts_receivable",
    "Inventory": "inventory",
    "Total Current Assets": "total_current_assets",
    "Total Assets": "total_assets",
    "Accounts Payable": "accounts_payable",
    "Short-Term Debt": "short_term_debt",
    "Total Current Liabilities": "total_current_liabilities",
    "Long-Term Debt": "long_term_debt",
    "Total Liabilities": "total_liabilities",
    "Common Stock Shares Outstanding": "common_shares_outstanding",
    "Retained Earnings": "retained_earnings",
    "Total Stockholders' Equity": "total_equity",
}

CASHFLOW_METRICS = {
    "Net Cash from Operating Activities": "operating_cash_flow",
    "Net Cash from Investing Activities": "investing_cash_flow",
    "Net Cash from Financing Activities": "financing_cash_flow",
    "Payments of Dividends": "dividends_paid",
    "Repurchases of common stock": "share_repurchases",
    "Depreciation and amortization": "depreciation_amortization",
    "Payments for Property, Plant and Equipment": "capex",
    "Net Change in Cash": "net_change_in_cash",
    "Share-based compensation expense": "stock_comp",
}


def _parse_table(text: str) -> list[tuple[str, float]]:
    """Parse a space-aligned financial table, returning (label, first_value) pairs.

    We only take the first numeric column value for each row, since the section
    already belongs to a specific fiscal_year and other columns are prior-year data.
    """
    results = []
    seen_labels = set()
    lines = text.strip().split("\n")

    for line in lines:
        # Match: label followed by one or more numbers like 12345000000.0 or -12345000000.0
        # The numbers are separated by whitespace
        numbers = re.findall(r"-?\d+(?:\.\d+)?", line)
        if not numbers:
            continue

        # Try to isolate the label: everything before the first number
        first_num_match = re.search(r"\s+-?\d+(?:\.\d+)?", line)
        if not first_num_match:
            continue

        label = line[:first_num_match.start()].strip()
        if len(label) < 3:
            continue

        # Skip header rows (e.g., "label 2025-09-27 2024-09-28")
        if label.lower() == "label":
            continue
        # Skip date-looking rows
        if re.match(r"\d{4}-\d{2}-\d{2}", label):
            continue

        # Take the first numeric value (current year)
        try:
            val = float(numbers[0])
        except ValueError:
            continue

        # Deduplicate: skip if we already have this label (e.g. "Net Income" appears twice in cash flow)
        label_key = label.lower().strip()
        if label_key in seen_labels:
            continue
        seen_labels.add(label_key)

        results.append((label, val))

    return results


def _determine_unit(value: float, label: str) -> str:
    label_lower = label.lower()
    if "per share" in label_lower or "earnings per share" in label_lower:
        return "per_share"
    if "shares" in label_lower:
        return "shares"
    return "USD"


def _match_metric(label: str, mappings: dict[str, str]) -> str | None:
    """Find best matching metric name for a label."""
    label_lower = label.lower().strip()
    for key, metric_name in mappings.items():
        if key.lower() == label_lower:
            return metric_name
    # Partial match
    for key, metric_name in mappings.items():
        if key.lower() in label_lower or label_lower in key.lower():
            return metric_name
    return None


def extract_metrics_from_section(section: dict) -> list[dict]:
    """Extract structured metrics from a single financial section."""
    title = section["section_title"]
    text = section["section_text"]
    fy = section["file_fiscal_year"]
    symbol = section["symbol"]

    if "Income Statement" in title:
        mappings = INCOME_METRICS
    elif "Balance Sheet" in title:
        mappings = BALANCE_METRICS
    elif "Cash Flow" in title:
        mappings = CASHFLOW_METRICS
    else:
        return []

    rows = _parse_table(text)
    metrics = []
    seen_metric_names = set()

    for label, value in rows:
        metric_name = _match_metric(label, mappings)
        if metric_name is None:
            continue
        if metric_name in seen_metric_names:
            continue
        seen_metric_names.add(metric_name)

        # Normalize signs for certain metrics
        if metric_name in ("cost_of_sales", "operating_expenses", "income_tax",
                          "dividends_paid", "share_repurchases", "capex",
                          "rd_expense", "sga_expense"):
            value = abs(value)

        unit = _determine_unit(value, label)
        metric_id = f"{symbol}_{fy}_{metric_name}"

        metrics.append({
            "id": metric_id,
            "symbol": symbol,
            "fiscal_year": fy,
            "metric_name": metric_name,
            "metric_value": value,
            "metric_unit": unit,
            "source_section": title,
            "source_ref": f"{symbol}_{fy}_{section['section_id']}_0",
        })

    return metrics


def extract_all_metrics(sections: list[dict]) -> list[dict]:
    """Extract metrics from all financial statement sections."""
    all_metrics = []
    financial_sections = 0

    for section in sections:
        title = section["section_title"]
        if any(kw in title for kw in ("Income Statement", "Balance Sheet", "Cash Flow")):
            financial_sections += 1
            metrics = extract_metrics_from_section(section)
            all_metrics.extend(metrics)

    logger.info("Extracted %d metrics from %d financial sections", len(all_metrics), financial_sections)

    metric_names = sorted(set(m["metric_name"] for m in all_metrics))
    logger.info("Unique metrics: %s", metric_names)

    fy_counts = {}
    for m in all_metrics:
        fy_counts[m["fiscal_year"]] = fy_counts.get(m["fiscal_year"], 0) + 1
    for fy in sorted(fy_counts):
        logger.info("  FY%d: %d metrics", fy, fy_counts[fy])

    return all_metrics
