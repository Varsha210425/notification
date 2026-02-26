# Notification Prioritization Engine

This repository contains a proof-of-concept notification prioritization service.  It demonstrates how incoming notification events can be classified as **Now**, **Later**, or **Never** based on rule-driven logic (dedupe, rate limits, urgency, etc.).

The project includes:

- `app/` - Python package holding core logic
  - `engine.py` - prioritization rules and decision engine
  - `store.py` - in-memory state store for testing
  - `models.py` - pydantic data models
  - `main.py` - FastAPI web server with API endpoints
  - `static/index.html` - interactive dashboard UI for demos
  - `DESIGN.md` - design overview
- `tests/` - unit tests for core engine
- `simulate.py` - script executing full simulation scenarios
- `requirements.txt` - Python dependencies

## Prerequisites

- Python 3.11+ installed
- Git (optional but used for source control)

## Setup

1. Clone the repository (or download):
   ```bash
   git clone <your-repo-url>
   cd "Notification Prioritation Engine"
   ```
2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   # Windows PowerShell
   .\venv\Scripts\Activate.ps1
   # or cmd
   venv\Scripts\activate.bat
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Project

### 1. Execute the Simulation
A complete end-to-end simulation covering all decision paths:
```bash
python simulate.py
```

### 2. Run Unit Tests
Verify core functionality with pytest:
```bash
python -m pytest tests/test_engine.py -v
```

### 3. Start the API + Dashboard
Launch the FastAPI server; the UI is served at `/`:
```bash
uvicorn app.main:app --reload --port 8000
```
Visit [http://localhost:8000](http://localhost:8000) in your browser.  Use the interactive form to send test notifications and view decisions.

#### API Endpoints
- `POST /v1/notifications/decide` – apply prioritization rules (JSON).
- `GET /v1/rules` and `POST /v1/rules` – read/update rule configuration.
- `GET /v1/users/{user_id}/history` – view recent events and audit records.
- `GET /v1/metrics` – snapshot metric counts.

## Project Structure
```
Notification Prioritation Engine/
├── app/
│   ├── engine.py
│   ├── main.py
│   ├── models.py
│   ├── store.py
│   ├── static/index.html
│   └── pyproject.toml
├── tests/test_engine.py
├── simulate.py
├── requirements.txt
└── README.md
```

## Demo Flow
1. Start server.
2. Open dashboard UI.
3. Fill notification form & submit.
4. Observe decision (Now/Later/Never) with explanation.
5. Check history panel for recent items.

## Notes for Non-Technical Users
The interface is intentionally simple: enter any notification details and the system will show whether the message would be sent now, later, or never—simulating the real behavior when deployed.

## License
MIT (or whatever you choose)
