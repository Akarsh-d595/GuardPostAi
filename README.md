
# GuardPost AI — Dataset-Based Prompt Injection Classifier

A local college-project prototype that classifies submitted text into five dataset labels:
- `safe`
- `prompt_injection`
- `jailbreak`
- `data_exfiltration`
- `unsafe_request`

**No Ollama, Gemini, LLM answer generation, web search, or evidence checking is included.**

## How it works
1. The FastAPI backend loads `data/prompt_dataset.csv`.
2. A TF-IDF + Logistic Regression pipeline is trained locally.
3. A user submits a prompt through the React interface.
4. The API returns the predicted dataset category, model confidence, a risk band, and a block/allow recommendation.
5. Recent scan events are stored locally in `data/events.sqlite3` and remain after restarting the app.
6. The Model Evaluation page reports accuracy, per-category metrics, and a confusion matrix from a stratified holdout split.

The confidence value is the model's estimated class probability, not a guarantee that the classification is correct. Risk bands are transparent category-based policy mappings, not calibrated security probabilities.
Evaluation results are a rough estimate based on the included synthetic dataset. The dashboard displays the latest 100 events; the local database retains scan history.

## Requirements
- Windows 10/11
- Python 3.10+ (Python 3.13 is supported if compatible wheels are available)
- Node.js 18+ and npm

## Run on Windows
1. Extract this ZIP.
2. Open the extracted `GuardPost_AI_Dataset_Classifier` folder.
3. Double-click `start.bat`.
4. On first run, the script installs dependencies and starts both servers.
5. Open http://localhost:5173

Backend API docs: http://localhost:8000/docs

To stop: close both terminal windows (or press Ctrl+C in each).

## Manual start
Backend:
```cmd
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r backend\requirements.txt
py -m uvicorn backend.app:app --reload --port 8000
```

Frontend (second terminal):
```cmd
cd frontend
npm install
npm run dev
```

## Dataset
The included CSV is a small **starter/example dataset** with synthetic examples. It is not the user's original 157-row file because that CSV was not available as an attachment in this conversation. Replace `data/prompt_dataset.csv` with your approved dataset, keeping the exact columns:
- `text`
- `label`

Keep the five labels consistent. For meaningful evaluation, use a larger, diverse, reviewed dataset and a stratified holdout set. The small included dataset is only for demonstrating the end-to-end workflow.

## Important limitations
- This is an academic prototype, not a production security gateway.
- Text classifiers can produce false positives and false negatives.
- TF-IDF is sensitive to wording and may not recognize novel or obfuscated attacks.
- A predicted `safe` label does not prove a prompt is safe.
- Do not rely on this prototype to protect real secrets or production systems.
- The starter dataset is synthetic and too small for real-world performance claims.

## Project structure
```text
GuardPost_AI_Dataset_Classifier/
  backend/
    app.py
    classifier.py
    schemas.py
    requirements.txt
  data/
    prompt_dataset.csv
  frontend/
    index.html
    package.json
    vite.config.ts
    tsconfig.json
    src/
      main.tsx
      App.tsx
      styles.css
  tests/
    test_classifier.py
  start.bat
  README.md
```
