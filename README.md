# Previously On Episodic Recaps through LLM Based Semantic Narrative Analysis

## Installation

### Backend Setup

1. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate     # On Windows
   ```

2. **Install Python requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install PyTorch requirements:**
   ```bash
   pip install -r requirements_torch.txt
   ```

4. **Download spaCy English model:**
   ```bash
   python -m spacy download en_core_web_trf
   ```

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

3. **Start development server:**
   ```bash
   npm run dev
   ```

## Running the Application

### Backend Server

To start the backend webserver:

```bash
uvicorn api.api_main_updated:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

The frontend will be available at `http://localhost:3000` when running in development mode.

## Requirements

- Python 3.8+
- Node.js 16+
- Virtual environment (recommended)


