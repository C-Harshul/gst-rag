# GST RAG Frontend

A simple, modern frontend interface for querying the GST RAG system.

## Features

- Clean, modern UI
- Real-time chat interface
- Responsive design
- Error handling
- Loading states

## Setup

1. Make sure the RAG API is running:
   ```bash
   cd GST-Rag
   export CHROMA_HOST=44.211.29.171
   export CHROMA_PORT=8000
   uvicorn rag.api:app --host 0.0.0.0 --port 8002 --reload
   ```

2. Update the API URL in `app.js` if needed:
   ```javascript
   const API_URL = 'http://localhost:8002';
   ```

3. Open `index.html` in a browser, or use a local server:
   ```bash
   cd frontend
   python -m http.server 3000
   ```
   Then open http://localhost:3000

## Usage

1. Type your question in the text area
2. Press Enter or click Send
3. View the AI-generated answer

## Files

- `index.html` - Main HTML structure
- `app.js` - JavaScript logic for API calls
- `style.css` - Styling and layout

