# TreePilot 🌳

**AI-Powered Genealogy Research Agent** built with the [GitHub Copilot SDK](https://github.com/github/copilot-sdk)

> Built for the [Copilot SDK Weekend Contest](https://www.reddit.com/r/GithubCopilot/comments/1qkz7oj/lets_build_copilot_sdk_weekend_contest_with_prizes/)

## Features

- **GEDCOM Import** - Load your family tree from standard GEDCOM files
- **Interactive Ancestor Tree** - D3.js visualization of your ancestors
- **AI Research Agent** - Powered by GitHub Copilot SDK with custom tools
- **Multi-Source Research** - Searches Wikipedia, Wikidata, historical newspapers, and Google Books

## Screenshots

*Coming soon!*

## Tech Stack

### Backend
- **Python 3.9+** with FastAPI
- **GitHub Copilot SDK** for agent orchestration
- **python-gedcom** for GEDCOM parsing
- Custom research tools:
  - Wikipedia REST API
  - Wikidata SPARQL queries
  - Chronicling America (historical newspapers 1770-1963)
  - Google Books API

### Frontend
- **React 18** with TypeScript
- **Vite** for fast development
- **TailwindCSS** for styling
- **D3.js** for family tree visualization
- **React Markdown** for rendering AI responses

## Prerequisites

1. **GitHub Copilot subscription** (or free tier)
2. **Copilot CLI** installed:
   ```bash
   # Install GitHub CLI if not already installed
   winget install GitHub.cli   # Windows
   brew install gh             # macOS
   
   # Install Copilot extension
   gh extension install github/gh-copilot
   
   # Verify installation
   gh copilot --version
   ```
3. **Python 3.9+** and **Node.js 18+**

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/treepilot.git
cd treepilot
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

copilot --server --port 4321 #can be changed, but change the binding in main.py

# Install dependencies
pip install -r requirements.txt

# Start the server
python main.py
```

The backend runs on `http://localhost:8000`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend runs on `http://localhost:5173`

### 4. Open TreePilot

Navigate to `http://localhost:5173` in your browser.

## Usage

1. **Import GEDCOM** - Upload your family tree file (or use the included `sample-family.ged`)
2. **Browse Tree** - Click on individuals to see their ancestor tree
3. **Research** - Click a person and switch to the Research tab to have the AI agent search for information

## Sample GEDCOM

A sample GEDCOM file is included (`sample-family.ged`) with a fictional 4-generation family including:
- Immigration from Ireland, Poland, and Sweden
- Various occupations and locations across the US
- 20 individuals spanning 1880-1992

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/upload-gedcom` | POST | Upload and parse GEDCOM file |
| `/individuals` | GET | List all individuals |
| `/tree/{person_id}` | GET | Get ancestor tree for a person |
| `/youngest` | GET | Get youngest generation |
| `/chat` | POST | Non-streaming chat |
| `/chat/stream` | POST | Streaming chat (SSE) |

## Research Tools

The AI agent has access to:

1. **Wikipedia** (`search_wikipedia`)
   - Biographical information
   - Historical context
   - Notable individuals

2. **Wikidata** (`search_wikidata`)
   - Structured data (birth/death dates, places)
   - Family relationships
   - Occupations

3. **Chronicling America** (`search_newspapers`)
   - Historical newspapers 1770-1963
   - Obituaries, birth/marriage announcements
   - Local news mentions

4. **Google Books** (`search_books`)
   - Genealogy guides
   - Local histories
   - Biographical works

## Environment Variables

Create a `.env` file in the `backend` folder:

```env
# Optional: Google Books API key for higher rate limits
GOOGLE_BOOKS_API_KEY=your_api_key_here
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [GitHub Copilot SDK](https://github.com/github/copilot-sdk) - Agent framework
- [Chronicling America](https://chroniclingamerica.loc.gov/) - Library of Congress newspaper archive
- [Wikidata](https://www.wikidata.org/) - Free knowledge base
- [python-gedcom](https://github.com/nickreynke/python-gedcom) - GEDCOM parsing library

---

**Built with ❤️ for the Copilot SDK Weekend Contest**
