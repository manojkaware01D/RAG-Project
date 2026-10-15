# Ledgerline Banking RAG

A small Streamlit banking-support app with local TF-IDF passage retrieval, source citations, document uploads, and public GitHub repository imports. The answer is extractive: it quotes the best matching passages rather than calling a hosted language model.

## Run locally

Requires Python 3.10 or newer.

```powershell
cd python_rag
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

The app opens at the local URL printed by Streamlit. Uploaded files and imported repository text are stored in `python_rag/.app_data/documents.json` and are excluded from Git.

## Sources

Upload TXT, Markdown, or CSV files from **Knowledge library**. GitHub imports accept public repository URLs and index up to eight README, Markdown, reStructuredText, text, or CSV files, each up to 75 KB. GitHub's unauthenticated API rate limit applies. Private repositories are not supported.

## Tests

```powershell
python -m pytest
```