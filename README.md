# SearchCalc Agent

A small interactive function-calling demo for a personal website. The agent can search the web, calculate math expressions, and convert units, while the UI shows each tool call in a live trace panel.

## Run locally

```bash
pip install -r requirements.txt
uvicorn SearchAgent:app --reload
```

Open `http://127.0.0.1:8000`.

Create a `.env` file with:

```bash
OPENAI_API_KEY=your_api_key_here
```

## Features

- Chat interface for asking mixed search, math, and conversion questions
- Tool trace panel showing function name, arguments, and result
- Example prompts for quick portfolio demos
- Reset endpoint for clearing conversation history
- Safer AST-based math evaluator instead of raw `eval`

