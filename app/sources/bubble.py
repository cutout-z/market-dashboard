"""AI Bubble Tracker — reference data for AI model capabilities over time."""

import asyncio
from app.sources.base import BaseSource

# ─── Context Window Expansion ───
CONTEXT_WINDOWS = [
    {"model": "GPT-3",           "date": "2020-06", "tokens": 4096,     "provider": "OpenAI"},
    {"model": "GPT-3.5",         "date": "2022-11", "tokens": 4096,     "provider": "OpenAI"},
    {"model": "Claude 1",        "date": "2023-03", "tokens": 9000,     "provider": "Anthropic"},
    {"model": "GPT-4",           "date": "2023-03", "tokens": 8192,     "provider": "OpenAI"},
    {"model": "GPT-4 32K",       "date": "2023-03", "tokens": 32768,    "provider": "OpenAI"},
    {"model": "Claude 2",        "date": "2023-07", "tokens": 100000,   "provider": "Anthropic"},
    {"model": "GPT-4 Turbo",     "date": "2023-11", "tokens": 128000,   "provider": "OpenAI"},
    {"model": "Gemini 1.5 Pro",  "date": "2024-02", "tokens": 1000000,  "provider": "Google"},
    {"model": "Claude 3",        "date": "2024-03", "tokens": 200000,   "provider": "Anthropic"},
    {"model": "GPT-4o",          "date": "2024-05", "tokens": 128000,   "provider": "OpenAI"},
    {"model": "Claude 3.5",      "date": "2024-06", "tokens": 200000,   "provider": "Anthropic"},
    {"model": "Gemini 2.0",      "date": "2024-12", "tokens": 1000000,  "provider": "Google"},
    {"model": "Claude Opus 4",   "date": "2025-05", "tokens": 1000000,  "provider": "Anthropic"},
]

# ─── Benchmark Performance ───
# Each benchmark: list of {model, date, score, provider}
BENCHMARKS = {
    "MMLU": {
        "description": "Massive Multitask Language Understanding — 57 subjects, knowledge breadth",
        "max_score": 100,
        "scores": [
            {"model": "GPT-4",           "date": "2023-03", "score": 86.4,  "provider": "OpenAI"},
            {"model": "Claude 2",        "date": "2023-07", "score": 78.5,  "provider": "Anthropic"},
            {"model": "Gemini Ultra",     "date": "2023-12", "score": 90.0,  "provider": "Google"},
            {"model": "Claude 3 Opus",   "date": "2024-03", "score": 86.8,  "provider": "Anthropic"},
            {"model": "GPT-4o",          "date": "2024-05", "score": 88.7,  "provider": "OpenAI"},
            {"model": "Claude 3.5 Sonnet","date": "2024-06", "score": 88.7,  "provider": "Anthropic"},
            {"model": "Gemini 1.5 Pro",  "date": "2024-08", "score": 85.9,  "provider": "Google"},
            {"model": "o1",              "date": "2024-09", "score": 92.3,  "provider": "OpenAI"},
            {"model": "Claude 4 Opus",   "date": "2025-05", "score": 93.0,  "provider": "Anthropic"},
        ],
    },
    "MMLU-Pro": {
        "description": "Harder, more discriminating MMLU variant — 10-option MCQ, expert-level",
        "max_score": 100,
        "scores": [
            {"model": "GPT-4o",          "date": "2024-05", "score": 72.6,  "provider": "OpenAI"},
            {"model": "Claude 3.5 Sonnet","date": "2024-06", "score": 78.0,  "provider": "Anthropic"},
            {"model": "Gemini 1.5 Pro",  "date": "2024-08", "score": 69.1,  "provider": "Google"},
            {"model": "o1",              "date": "2024-09", "score": 80.3,  "provider": "OpenAI"},
            {"model": "Claude 4 Opus",   "date": "2025-05", "score": 84.0,  "provider": "Anthropic"},
        ],
    },
    "GPQA Diamond": {
        "description": "Graduate-level science QA — physics, chemistry, biology expert questions",
        "max_score": 100,
        "scores": [
            {"model": "GPT-4",           "date": "2023-03", "score": 39.7,  "provider": "OpenAI"},
            {"model": "Claude 3 Opus",   "date": "2024-03", "score": 60.4,  "provider": "Anthropic"},
            {"model": "GPT-4o",          "date": "2024-05", "score": 53.6,  "provider": "OpenAI"},
            {"model": "Claude 3.5 Sonnet","date": "2024-06", "score": 65.0,  "provider": "Anthropic"},
            {"model": "o1",              "date": "2024-09", "score": 78.0,  "provider": "OpenAI"},
            {"model": "Claude 4 Opus",   "date": "2025-05", "score": 75.0,  "provider": "Anthropic"},
        ],
    },
    "Humanity's Last Exam": {
        "description": "Extremely hard questions from domain experts — ceiling test for frontier models",
        "max_score": 100,
        "scores": [
            {"model": "GPT-4o",          "date": "2024-05", "score": 3.3,   "provider": "OpenAI"},
            {"model": "Claude 3.5 Sonnet","date": "2024-06", "score": 4.3,   "provider": "Anthropic"},
            {"model": "o1",              "date": "2024-09", "score": 9.1,   "provider": "OpenAI"},
            {"model": "o3",              "date": "2025-01", "score": 18.6,  "provider": "OpenAI"},
            {"model": "Gemini 2.5 Pro",  "date": "2025-03", "score": 18.8,  "provider": "Google"},
            {"model": "Claude 4 Opus",   "date": "2025-05", "score": 14.0,  "provider": "Anthropic"},
        ],
    },
    "SWE-Bench Verified": {
        "description": "Real-world GitHub issue resolution — end-to-end software engineering",
        "max_score": 100,
        "scores": [
            {"model": "GPT-4",           "date": "2023-03", "score": 1.7,   "provider": "OpenAI"},
            {"model": "Claude 3 Opus",   "date": "2024-03", "score": 4.7,   "provider": "Anthropic"},
            {"model": "Claude 3.5 Sonnet","date": "2024-06", "score": 49.0,  "provider": "Anthropic"},
            {"model": "o1",              "date": "2024-09", "score": 41.0,  "provider": "OpenAI"},
            {"model": "Claude 3.5 Sonnet (new)","date": "2024-10", "score": 53.6, "provider": "Anthropic"},
            {"model": "o3",              "date": "2025-01", "score": 71.7,  "provider": "OpenAI"},
            {"model": "Claude 4 Opus",   "date": "2025-05", "score": 72.5,  "provider": "Anthropic"},
        ],
    },
}

# ─── Task Complexity / Capability Milestones ───
CAPABILITY_MILESTONES = [
    {"date": "2020-06", "event": "GPT-3: few-shot learning",           "complexity": 1},
    {"date": "2022-11", "event": "ChatGPT: conversational AI",         "complexity": 2},
    {"date": "2023-03", "event": "GPT-4: multimodal, reasoning",       "complexity": 3},
    {"date": "2023-07", "event": "Claude 2: 100K context",             "complexity": 3.5},
    {"date": "2023-11", "event": "GPT-4 Turbo: 128K, function calling","complexity": 4},
    {"date": "2024-02", "event": "Gemini 1.5: 1M context",            "complexity": 4.5},
    {"date": "2024-03", "event": "Claude 3: tool use, vision",        "complexity": 5},
    {"date": "2024-06", "event": "Claude 3.5: artifacts, coding",      "complexity": 6},
    {"date": "2024-09", "event": "o1: chain-of-thought reasoning",     "complexity": 7},
    {"date": "2024-10", "event": "Claude computer use",                "complexity": 7.5},
    {"date": "2025-01", "event": "o3: advanced reasoning, ARC-AGI",    "complexity": 8},
    {"date": "2025-02", "event": "Claude Code: autonomous coding",     "complexity": 8.5},
    {"date": "2025-05", "event": "Claude 4: extended thinking, agents","complexity": 9},
]


class BubbleTrackerSource(BaseSource):
    cache_key = "bubble_tracker"
    refresh_interval = 86400  # daily — static reference data

    async def fetch(self) -> dict:
        return await asyncio.to_thread(self._load_data)

    def _load_data(self) -> dict:
        return {
            "context_windows": CONTEXT_WINDOWS,
            "benchmarks": BENCHMARKS,
            "milestones": CAPABILITY_MILESTONES,
        }
