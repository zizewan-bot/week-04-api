import os

from anthropic import Anthropic
from dotenv import load_dotenv


MODEL = "claude-sonnet-4-6"
PROMPT = "What is the book '1984' about in one paragraph?"


def main() -> None:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not configured. Add it to backend .env to run this test."
        )

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system="You are a helpful book assistant.",
        messages=[{"role": "user", "content": PROMPT}],
    )

    text = "\n".join(
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    )
    print(text.strip())


if __name__ == "__main__":
    main()
