# SearchCalc Agent

An interactive function-calling agent demo. The app lets users ask mixed questions that may require web lookup, precise math, and unit conversion, then exposes the agent's tool-use trace so the reasoning path is visible instead of hidden behind a chat bubble.

## Overview

SearchCalc Agent is built around a simple idea: a chat response is more useful when users can see which tools the model used to produce it. Instead of returning only the final answer, the app shows the function-calling loop as a traceable sequence of steps:

- The model receives the user prompt and decides whether a tool is needed
- The backend executes the selected tool with structured arguments
- The tool result is added back into the conversation
- The frontend renders both the final answer and the intermediate tool calls

## Core Features

- **Transparent agent trace**: every tool call is shown as a step-by-step timeline
- **Multi-tool reasoning**: the agent can combine search, calculation, and unit conversion in one answer
- **Safe math evaluation**: math expressions are evaluated through an AST whitelist instead of raw `eval`
- **Unit conversion aliases**: supports common aliases such as `kilometers`, `miles`, `mi`, `feet`, and `lbs`
- **Lightweight web UI**: chat interface with example prompts and a live tool trace panel
- **Backend-only API key handling**: the OpenAI API key stays in `.env` and is never exposed to browser code

## Technical Stack

- **Backend**: FastAPI
- **Frontend**: HTML, CSS, vanilla JavaScript
- **LLM API**: OpenAI Chat Completions with function calling
- **Search demo endpoint**: DuckDuckGo Instant Answer API
- **Tooling**: Python, requests, pydantic, python-dotenv

## Architecture

```text
User prompt
   |
   v
FastAPI /api/chat
   |
   v
SearchCalcAgent
   |
   +--> OpenAI model selects tools
   |
   +--> search_web()
   +--> calculate()
   +--> unit_converter()
   |
   v
Tool results are appended to the conversation
   |
   v
Final answer + tool trace returned to frontend
```

## Implementation Details

- The agent loop supports multiple tool calls before producing a final answer.
- Tool schemas are defined with explicit names, descriptions, parameters, and required fields.
- Backend failures are converted into readable API errors so the frontend can show useful messages.
- Math expressions are parsed with Python's `ast` module and evaluated through a whitelist of supported operators, functions, and constants.
- Unit conversion normalizes common aliases such as `kilometers`, `miles`, `mi`, `feet`, and `lbs`.
- The frontend consumes a structured response containing both `answer` and `tool_calls`, which keeps the UI simple and makes the trace easy to inspect.

## Example Prompts

```text
How far is the Earth from the Moon in kilometers? Convert it to miles.
```

```text
If I save $2,000 per month at 3% annual interest for 5 years, how much will I have?
```

```text
What are the important new features in Python 3.12?
```

```text
Convert 180 cm to feet.
```

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```bash
OPENAI_API_KEY=your_api_key_here
```

Start the app:

```bash
python -m uvicorn SearchAgent:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Notes And Limitations

- The current search tool uses DuckDuckGo's free Instant Answer API, which is not the same as DuckDuckGo's full web search page. Some queries may return no API results even when the browser search page has results.
- For a production-grade agent, replace the search tool with a dedicated search API such as Tavily, Brave Search, or SerpAPI.
- The app currently stores conversation state in a single in-memory agent instance, which is sufficient for a demo but should be replaced with session-scoped state for multi-user deployment.
