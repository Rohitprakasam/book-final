# BookUdecate V1.0

BookUdecate is a powerful AI-driven pipeline for expanding and publishing educational textbooks. It intelligently deconstructs existing material, expands upon theory and practical questions using Large Language Models, and compiles beautiful Typst-typeset PDF outputs in seconds.

## Key Features

- **Lightning Fast Compilation**: Swapped legacy LaTeX (xelatex) for modern Typst rendering, cutting PDF build times from minutes to milliseconds.
- **Multi-Page Dashboard**: A fully routed React frontend (`react-router-dom`) offering seamless navigation between Home, Creation, Live Progress tracking, and Generation History.
- **Dual AI Providers**: Execute generations using either the cloud-hosted Google Gemini API or a completely local/networked Ollama model.
- **Smart Image Placeholders**: When "Placeholders Only" is toggled, it skips slow AI image generation and natively renders colorful geometric placeholders with embedded titles.
- **Robust Math Parsing**: Automatically structures display and inline math with native Typst `$ ... $` syntax.
- **Zero-Error Sanitization**: Fully resilient to LLM hallucinations with auto-balancing and structure sanitizers.

## Project Structure

- `frontend/`: The web-based user interface for managing generation jobs and viewing status.
- `backend/`: The core Python pipeline, consisting of the FastAPI server, LangGraph agent swarm, PDF processing tools, and Typst renderers.

## Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up your `.env` file with necessary API keys (e.g., `GOOGLE_API_KEY`).
5. Run the server:
   ```bash
   python -m uvicorn server.api:app --reload --host 0.0.0.0 --port 8000
   ```

## Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```

## Prerequisites

- Python 3.10+
- Node.js 18+
- [Typst CLI](https://typst.app/) (v0.14+ recommended) available in your system path.
