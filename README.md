# insectapel-curation

Pass 3 curation app (Streamlit) — review flagged chemical structures from the 1947 King USDA repellent dataset.

## Run locally

```bash
pip install -r requirements.txt
streamlit run pass3_curation_app.py
```

## Deploy

Hosted on [Streamlit Community Cloud](https://share.streamlit.io). Main file: `pass3_curation_app.py`.

**Important:** In **Advanced settings**, set **Python version to 3.11**. RDKit has no wheels for 3.13+; the cloud default (3.14) will fail. If already deployed on the wrong version, delete the app and redeploy with 3.11 selected.

## Data

`dataset_from_ccast.xlsx` — Pass 3 output with SMARTS and CCAST columns (do not commit `.env` or API caches).
