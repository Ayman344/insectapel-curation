"""Generate HTML structure galleries from resolved SMILES rows."""
from __future__ import annotations

import base64
import io
from pathlib import Path

import pandas as pd
from rdkit import Chem
from rdkit.Chem import Draw
from rdkit import RDLogger

RDLogger.DisableLog("rdApp.*")


def _name_column(df: pd.DataFrame) -> pd.Series:
    if "_name" in df.columns:
        return df["_name"]
    if "Chemical" in df.columns:
        return df["Chemical"]
    raise KeyError("Dataframe needs '_name' or 'Chemical' column")


def generate_structure_html(
    dataframe: pd.DataFrame,
    output_html: str | Path,
    *,
    title: str = "Resolved Chemical Structures Report",
    subtitle: str | None = None,
) -> int:
    resolved_df = dataframe[dataframe["SMILES"].notna()].copy()
    total = len(resolved_df)
    if total == 0:
        print("No resolved structures to export.")
        return 0

    names = _name_column(resolved_df)
    if subtitle is None:
        subtitle = f"Total successfully resolved compounds: {total}"

    print(f"Generating HTML report for {total} resolved compounds...")

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
    body {{ font-family: Arial, sans-serif; background-color: #f8f9fa; margin: 20px; color: #333; }}
    h1 {{ text-align: center; color: #2c3e50; margin-bottom: 5px; }}
    .subtitle {{ text-align: center; color: #7f8c8d; margin-bottom: 30px; font-size: 14px; }}
    .grid-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; }}
    .card {{ background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transition: transform 0.2s; }}
    .card:hover {{ transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); }}
    .card img {{ max-width: 100%; height: auto; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; }}
    .placeholder-img {{ height: 220px; display: flex; align-items: center; justify-content: center; background-color: #f1f5f9; color: #94a3b8; font-size: 11px; border-bottom: 1px solid #e2e8f0; margin-bottom: 10px; border-radius: 4px; }}
    .card h4 {{ font-size: 13px; margin: 10px 0 5px 0; word-break: break-word; color: #2c3e50; }}
    .card p {{ font-size: 10px; color: #64748b; word-break: break-all; margin: 0; line-height: 1.4; }}
</style>
</head>
<body>
    <h1>{title}</h1>
    <p class="subtitle">{subtitle}</p>
    <div class="grid-container">
"""

    for (_, row), display_name in zip(resolved_df.iterrows(), names, strict=False):
        mol = Chem.MolFromSmiles(str(row["SMILES"]))
        safe_name = str(display_name).replace('"', "&quot;")
        if mol:
            img = Draw.MolToImage(mol, size=(220, 220))
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            img_element = f'<img src="data:image/png;base64,{img_str}" alt="{safe_name}">'
        else:
            img_element = '<div class="placeholder-img">Structure Drawing Unavailable</div>'

        html_content += f"""
        <div class="card">
            {img_element}
            <h4>{safe_name}</h4>
            <p><strong>SMILES:</strong> {row['SMILES']}</p>
        </div>"""

    html_content += """
    </div>
</body>
</html>
"""

    output_path = Path(output_html)
    output_path.write_text(html_content, encoding="utf-8")
    print(f"HTML report successfully saved to: {output_path}")
    return total
