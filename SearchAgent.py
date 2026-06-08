import ast
import json
import math
import os
from dataclasses import dataclass, asdict
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global client
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Create a .env file or set the environment variable."
        )
    if client is None:
        client = OpenAI()
    return client


# ============================
# Tool Implementations
# ============================

def search_web(query: str, num_results: int = 5) -> str:
    """Search with DuckDuckGo Instant Answer API."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results: list[str] = []

        if data.get("AbstractText"):
            results.append(f"Instant Answer: {data['AbstractText']}")
            if data.get("AbstractURL"):
                results.append(f"Source: {data['AbstractURL']}")

        for topic in data.get("RelatedTopics", [])[:num_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(f"- {topic['Text'][:240]}")

        if results:
            return "\n".join(results)
        return f"No direct results found for '{query}'. Try more specific keywords."
    except Exception as exc:
        return f"Search failed: {exc}. Please check your network connection."


ALLOWED_MATH_FUNCS = {
    "sqrt": math.sqrt,
    "pow": math.pow,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
}

ALLOWED_MATH_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
    "inf": math.inf,
}


class SafeMathEvaluator(ast.NodeVisitor):
    """Evaluate a small, explicit subset of Python math expressions."""

    def visit_Expression(self, node: ast.Expression) -> float:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> float:
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("Only numeric constants are supported")

    def visit_Name(self, node: ast.Name) -> float:
        if node.id in ALLOWED_MATH_CONSTANTS:
            return ALLOWED_MATH_CONSTANTS[node.id]
        raise ValueError(f"Unknown constant: {node.id}")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError("Unsupported unary operator")

    def visit_BinOp(self, node: ast.BinOp) -> float:
        left = self.visit(node.left)
        right = self.visit(node.right)
        operators = {
            ast.Add: lambda: left + right,
            ast.Sub: lambda: left - right,
            ast.Mult: lambda: left * right,
            ast.Div: lambda: left / right,
            ast.Pow: lambda: left ** right,
            ast.Mod: lambda: left % right,
            ast.FloorDiv: lambda: left // right,
        }
        for op_type, operation in operators.items():
            if isinstance(node.op, op_type):
                return operation()
        raise ValueError("Unsupported binary operator")

    def visit_Call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only direct math function calls are supported")
        func = ALLOWED_MATH_FUNCS.get(node.func.id)
        if not func:
            raise ValueError(f"Unsupported function: {node.func.id}")
        args = [self.visit(arg) for arg in node.args]
        return func(*args)

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def calculate(expression: str) -> str:
    """Evaluate a mathematical expression with a safe AST whitelist."""
    try:
        expression = expression.strip().replace("^", "**")
        parsed = ast.parse(expression, mode="eval")
        result = SafeMathEvaluator().visit(parsed)

        if isinstance(result, float) and result == int(result):
            return f"{expression} = {int(result)}"
        if isinstance(result, float):
            return f"{expression} = {result:.6g}"
        return f"{expression} = {result}"
    except ZeroDivisionError:
        return "Calculation error: division by zero"
    except OverflowError:
        return "Calculation error: result overflow"
    except Exception as exc:
        return f"Calculation error: {exc}. Please verify the expression format."


def unit_converter(value: float, from_unit: str, to_unit: str) -> str:
    """Convert common length, weight, temperature, and area units."""
    unit_aliases = {
        "meter": "m",
        "meters": "m",
        "kilometer": "km",
        "kilometers": "km",
        "centimeter": "cm",
        "centimeters": "cm",
        "millimeter": "mm",
        "millimeters": "mm",
        "inches": "inch",
        "ft": "foot",
        "feet": "foot",
        "mi": "mile",
        "miles": "mile",
        "yards": "yard",
        "kilogram": "kg",
        "kilograms": "kg",
        "gram": "g",
        "grams": "g",
        "milligram": "mg",
        "milligrams": "mg",
        "lb": "pound",
        "lbs": "pound",
        "pounds": "pound",
        "oz": "ounce",
        "ounces": "ounce",
        "tons": "ton",
        "c": "celsius",
        "f": "fahrenheit",
        "k": "kelvin",
        "square_meter": "m2",
        "square_meters": "m2",
        "square_kilometer": "km2",
        "square_kilometers": "km2",
        "acres": "acre",
        "hectares": "hectare",
    }

    conversions = {
        "m": 1.0,
        "km": 1000.0,
        "cm": 0.01,
        "mm": 0.001,
        "inch": 0.0254,
        "foot": 0.3048,
        "mile": 1609.344,
        "yard": 0.9144,
        "kg": 1.0,
        "g": 0.001,
        "mg": 0.000001,
        "pound": 0.453592,
        "ounce": 0.0283495,
        "ton": 1000.0,
        "m2": 1.0,
        "km2": 1000000.0,
        "cm2": 0.0001,
        "acre": 4046.86,
        "hectare": 10000.0,
    }

    original_from_unit = from_unit
    original_to_unit = to_unit
    from_unit = from_unit.lower().strip()
    to_unit = to_unit.lower().strip()
    from_unit = unit_aliases.get(from_unit, from_unit)
    to_unit = unit_aliases.get(to_unit, to_unit)

    if from_unit in ["celsius", "fahrenheit", "kelvin"]:
        if from_unit == "celsius" and to_unit == "fahrenheit":
            result = value * 9 / 5 + 32
        elif from_unit == "fahrenheit" and to_unit == "celsius":
            result = (value - 32) * 5 / 9
        elif from_unit == "celsius" and to_unit == "kelvin":
            result = value + 273.15
        elif from_unit == "kelvin" and to_unit == "celsius":
            result = value - 273.15
        elif from_unit == "fahrenheit" and to_unit == "kelvin":
            result = (value - 32) * 5 / 9 + 273.15
        elif from_unit == "kelvin" and to_unit == "fahrenheit":
            result = (value - 273.15) * 9 / 5 + 32
        else:
            result = value
        return f"{value} {original_from_unit} = {result:.4g} {original_to_unit}"

    if from_unit not in conversions or to_unit not in conversions:
        return f"Unsupported unit: {from_unit} or {to_unit}"

    result = value * conversions[from_unit] / conversions[to_unit]
    return f"{value} {original_from_unit} = {result:.6g} {original_to_unit}"


# ============================
# Tool Configuration
# ============================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the internet for current or factual information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Concise search keywords.",
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of related results to return, max 10.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Precisely evaluate mathematical expressions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, e.g. sqrt(2) * pi.",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "unit_converter",
            "description": "Convert common length, weight, temperature, and area units.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value": {"type": "number", "description": "Numeric value."},
                    "from_unit": {"type": "string", "description": "Source unit."},
                    "to_unit": {"type": "string", "description": "Target unit."},
                },
                "required": ["value", "from_unit", "to_unit"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "search_web": search_web,
    "calculate": calculate,
    "unit_converter": unit_converter,
}


@dataclass
class ToolTrace:
    step: int
    name: str
    arguments: dict[str, Any]
    result: str


class SearchCalcAgent:
    """OpenAI function-calling agent with a trace-friendly response."""

    def __init__(self):
        self.messages = [self._system_message()]

    @staticmethod
    def _system_message() -> dict[str, str]:
        return {
            "role": "system",
            "content": (
                "You are an intelligent assistant that can search the web, "
                "perform precise calculations, and convert units.\n\n"
                "Strategy:\n"
                "- Use search_web for current facts, prices, news, or references.\n"
                "- Use calculate for arithmetic and math expressions.\n"
                "- Use unit_converter for unit conversions.\n"
                "- Complex questions may require multiple tools.\n\n"
                "Answer concisely. Mention uncertainty when search results are weak."
            ),
        }

    def reset(self) -> None:
        self.messages = [self._system_message()]

    def chat(self, user_message: str) -> dict[str, Any]:
        self.messages.append({"role": "user", "content": user_message})
        traces: list[ToolTrace] = []
        max_steps = 8

        for _ in range(max_steps):
            response = get_openai_client().chat.completions.create(
                model="gpt-4o",
                messages=self.messages,
                tools=TOOLS,
                tool_choice="auto",
                parallel_tool_calls=True,
            )

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            self.messages.append(message)

            if finish_reason == "stop":
                return {
                    "answer": message.content or "",
                    "tool_calls": [asdict(trace) for trace in traces],
                }

            if finish_reason == "tool_calls" and message.tool_calls:
                for tool_call in message.tool_calls:
                    try:
                        func_name = tool_call.function.name
                        func_args = json.loads(tool_call.function.arguments)
                        func = TOOL_FUNCTIONS.get(func_name)
                        result = func(**func_args) if func else f"Unknown tool: {func_name}"
                    except Exception as exc:
                        func_name = tool_call.function.name
                        func_args = {}
                        result = f"Tool execution failed: {exc}"

                    traces.append(
                        ToolTrace(
                            step=len(traces) + 1,
                            name=func_name,
                            arguments=func_args,
                            result=str(result),
                        )
                    )
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result),
                        }
                    )

        return {
            "answer": "Maximum step limit reached before the agent produced a final answer.",
            "tool_calls": [asdict(trace) for trace in traces],
        }


# ============================
# Web App
# ============================

app = FastAPI(title="SearchCalc Agent")
agent = SearchCalcAgent()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse("static/index.html")


@app.post("/api/chat")
def api_chat(payload: ChatRequest) -> dict[str, Any]:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        return agent.chat(message)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Agent request failed: {exc}") from exc


@app.post("/api/reset")
def api_reset() -> dict[str, str]:
    agent.reset()
    return {"status": "reset"}
