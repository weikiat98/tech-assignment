"""Approximate list prices, USD per 1M tokens (input, output). Verify against provider pricing pages."""

PRICES: dict[str, tuple[float, float]] = {
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "mock": (0.0, 0.0),
}


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, (1.0, 4.0))  # conservative default for unknown models
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000
