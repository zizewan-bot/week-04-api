import json
import os
from typing import Any

from anthropic import Anthropic
from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
import schemas


ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_AGENT_ITERATIONS = 5
AGENT_SYSTEM_PROMPT = """
You manage a personal book tracker.

Use tools whenever the user asks about their actual collection or wants to change it.
Do not pretend to know the database without calling tools first.
Ask for clarification before destructive actions when the target is ambiguous.
Summarize actions clearly after tool calls run.
If a rating is used, it must be 1 to 5 stars.
Never guess a book id. Look it up first when a request names a title or author.
When the user asks for a specific list, use the matching status filter:
- reading list -> status "reading"
- want-to-read list -> status "want_to_read"
- read books or finished books -> status "read"
When you change the database and the user also asks about the resulting state, make the
change first and then call another tool to check the updated state.
When the user asks to delete or update a book described by title or author instead of id,
look up the collection first and only act when there is one clear match.
""".strip()


TOOLS = [
    {
        "name": "get_books",
        "description": (
            "Fetch all books in the tracker. Optionally filter by one status such as "
            "want_to_read, reading, or read."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["want_to_read", "reading", "read"],
                    "description": "Optional status filter.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "get_book_by_id",
        "description": "Fetch one book from the tracker by its numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "The numeric id of the book to fetch.",
                }
            },
            "required": ["id"],
        },
    },
    {
        "name": "add_book",
        "description": (
            "Add a new book to the tracker with title, author, and status. Rating is "
            "optional, but only valid when the status is read."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title of the book to add.",
                },
                "author": {
                    "type": "string",
                    "description": "The author of the book to add.",
                },
                "status": {
                    "type": "string",
                    "enum": ["want_to_read", "reading", "read"],
                    "description": "The reading status to save for the new book.",
                },
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Optional 1 to 5 star rating for read books.",
                },
            },
            "required": ["title", "author", "status"],
        },
    },
    {
        "name": "update_book_status",
        "description": (
            "Update the reading status for one book by id. Optionally set a 1 to 5 star "
            "rating when the book is marked read."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "The numeric id of the book to update.",
                },
                "status": {
                    "type": "string",
                    "enum": ["want_to_read", "reading", "read"],
                    "description": "The new reading status.",
                },
                "rating": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Optional 1 to 5 star rating for a read book.",
                },
            },
            "required": ["id", "status"],
        },
    },
    {
        "name": "delete_book",
        "description": "Delete one book from the tracker by its numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "The numeric id of the book to delete.",
                }
            },
            "required": ["id"],
        },
    },
]


def get_anthropic_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured in the backend environment.",
        )
    return Anthropic(api_key=api_key)


def serialize_book(book: models.Book) -> dict[str, Any]:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "status": book.status,
        "rating": book.rating,
    }


def validate_rating_rules(status: str, rating: int | None) -> None:
    if status != "read" and rating is not None:
        raise ValueError("rating can only be set when status is 'read'")
    if status == "read" and rating is None:
        raise ValueError("rating is required when status is 'read'")


def get_books_tool(tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    status = tool_input.get("status")
    if status is not None and status not in schemas.VALID_STATUSES:
        return {
            "status": "error",
            "message": "status must be reading, read, or want_to_read",
        }

    query = db.query(models.Book).order_by(models.Book.id)
    if status is not None:
        query = query.filter(models.Book.status == status)

    books = [serialize_book(book) for book in query.all()]
    return {"status": "ok", "count": len(books), "books": books}


def get_book_by_id_tool(tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    book_id = tool_input.get("id")
    if not isinstance(book_id, int):
        return {"status": "error", "message": "id must be an integer"}

    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if book is None:
        return {"status": "not_found", "message": f"Book {book_id} was not found"}

    return {"status": "ok", "book": serialize_book(book)}


def add_book_tool(tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    try:
        book_data = schemas.BookCreate.model_validate(tool_input)
        validate_rating_rules(book_data.status, book_data.rating)
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    db_book = models.Book(
        title=book_data.title,
        author=book_data.author,
        status=book_data.status,
        rating=book_data.rating,
    )
    db.add(db_book)
    db.commit()
    db.refresh(db_book)

    return {"status": "ok", "book": serialize_book(db_book)}


def update_book_status_tool(tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    book_id = tool_input.get("id")
    status = tool_input.get("status")
    rating = tool_input.get("rating")

    if not isinstance(book_id, int):
        return {"status": "error", "message": "id must be an integer"}
    if status not in schemas.VALID_STATUSES:
        return {
            "status": "error",
            "message": "status must be reading, read, or want_to_read",
        }
    if rating is not None and not isinstance(rating, int):
        return {"status": "error", "message": "rating must be an integer from 1 to 5"}
    if isinstance(rating, int) and not 1 <= rating <= 5:
        return {"status": "error", "message": "rating must be an integer from 1 to 5"}

    try:
        validate_rating_rules(status, rating)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if book is None:
        return {"status": "not_found", "message": f"Book {book_id} was not found"}

    book.status = status
    book.rating = rating if status == "read" else None
    db.commit()
    db.refresh(book)

    return {"status": "ok", "book": serialize_book(book)}


def delete_book_tool(tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    book_id = tool_input.get("id")
    if not isinstance(book_id, int):
        return {"status": "error", "message": "id must be an integer"}

    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if book is None:
        return {"status": "not_found", "message": f"Book {book_id} was not found"}

    deleted_book = serialize_book(book)
    db.delete(book)
    db.commit()

    return {"status": "ok", "deleted_book": deleted_book}


TOOL_FUNCTIONS = {
    "get_books": get_books_tool,
    "get_book_by_id": get_book_by_id_tool,
    "add_book": add_book_tool,
    "update_book_status": update_book_status_tool,
    "delete_book": delete_book_tool,
}


def serialize_content_block(block: Any) -> dict[str, Any]:
    if getattr(block, "type", None) == "text":
        return {"type": "text", "text": block.text}
    if getattr(block, "type", None) == "tool_use":
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": dict(block.input),
        }
    return {"type": getattr(block, "type", "unknown")}


def extract_text_from_blocks(blocks: list[Any]) -> str:
    text_parts = [
        block.text
        for block in blocks
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]
    return "\n".join(text_parts).strip()


def execute_tool(tool_name: str, tool_input: dict[str, Any], db: Session) -> dict[str, Any]:
    tool_function = TOOL_FUNCTIONS.get(tool_name)
    if tool_function is None:
        return {"status": "error", "message": f"Unknown tool: {tool_name}"}

    try:
        return tool_function(tool_input, db)
    except Exception as exc:
        db.rollback()
        return {"status": "error", "message": str(exc)}


def run_agent(message: str, db: Session, max_iterations: int = MAX_AGENT_ITERATIONS):
    client = get_anthropic_client()
    messages: list[dict[str, Any]] = [{"role": "user", "content": message.strip()}]
    agent_steps: list[dict[str, Any]] = []

    # When stop_reason == "tool_use", Claude is asking us to pause normal text
    # generation and execute one or more tool calls before it can continue.
    # The tool_use_id links each later tool_result back to the exact tool call
    # Claude made, which is how the model knows which result belongs where.
    # Tool results go back as a user-role message because they become new context
    # the model should read and react to on the next pass through the loop.
    # max_iterations prevents the agent from getting stuck in an endless cycle of
    # repeated tool calls if the model keeps requesting more actions.
    for _ in range(max_iterations):
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=900,
                system=AGENT_SYSTEM_PROMPT,
                messages=messages,
                tools=TOOLS,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Anthropic API error: {exc}",
            ) from exc

        assistant_content = [serialize_content_block(block) for block in response.content]
        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason != "tool_use":
            final_text = extract_text_from_blocks(response.content)
            if not final_text:
                final_text = "I completed the agent run but did not receive a text reply."
            return {"response": final_text, "agent_steps": agent_steps}

        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue

            tool_input = dict(block.input)
            result = execute_tool(block.name, tool_input, db)
            agent_steps.append(
                {"tool": block.name, "input": tool_input, "result": result}
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return {
        "response": (
            "I stopped after reaching the agent safety limit before the task fully "
            "finished. Please try again with a more specific request."
        ),
        "agent_steps": agent_steps,
    }
