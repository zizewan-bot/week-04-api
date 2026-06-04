import os
from typing import Optional

from anthropic import Anthropic
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Book Tracker API", version="2.0.0")

ANTHROPIC_MODEL = "claude-sonnet-4-6"
BOOK_ASSISTANT_SYSTEM_PROMPT = (
    "You are a helpful book assistant. Give clear, concise answers about books, "
    "reading habits, and recommendations. Be honest when you are unsure."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def validate_book_rules(status: str, rating: Optional[int]) -> None:
    if status != "read" and rating is not None:
        raise HTTPException(
            status_code=400,
            detail="rating can only be set when status is 'read'",
        )

    if status == "read" and rating is None:
        raise HTTPException(
            status_code=400,
            detail="rating is required when status is 'read'",
        )


def get_book_or_404(book_id: int, db: Session) -> models.Book:
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


def get_anthropic_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured in the backend environment.",
        )
    return Anthropic(api_key=api_key)


def normalize_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    messages = []
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})
    return messages


def extract_reply_text(response) -> str:
    text_parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]
    reply = "\n".join(text_parts).strip()
    if not reply:
        raise HTTPException(
            status_code=502,
            detail="Anthropic returned an empty response.",
        )
    return reply


def call_claude(
    system_prompt: str,
    messages: list[dict[str, str]],
    max_tokens: int = 600,
) -> str:
    client = get_anthropic_client()
    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic API error: {exc}",
        ) from exc

    return extract_reply_text(response)


def format_books_for_prompt(books: list[models.Book]) -> str:
    if not books:
        return "No books are saved yet."

    status_labels = {
        "read": "Read books",
        "reading": "Currently reading",
        "want_to_read": "Want to read",
    }
    sections = []
    for status in ["read", "reading", "want_to_read"]:
        matching_books = [book for book in books if book.status == status]
        if not matching_books:
            sections.append(f"{status_labels[status]}: none")
            continue

        lines = []
        for book in matching_books:
            rating = f", rating {book.rating}/5" if book.rating is not None else ""
            lines.append(f"- {book.title} by {book.author}{rating}")
        sections.append(f"{status_labels[status]}:\n" + "\n".join(lines))

    return "\n\n".join(sections)


@app.get("/")
def read_root():
    return {"message": "Welcome to Book Tracker API"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ai/chat", response_model=schemas.AIChatResponse)
def ai_chat(request: schemas.AIChatRequest):
    history = normalize_history(request.conversation_history)
    messages = [*history, {"role": "user", "content": request.message}]
    reply = call_claude(BOOK_ASSISTANT_SYSTEM_PROMPT, messages)

    updated_history = [*messages, {"role": "assistant", "content": reply}]
    return {"reply": reply, "updated_history": updated_history}


@app.post("/ai/recommend", response_model=schemas.AIChatResponse)
def ai_recommend(request: schemas.AIChatRequest, db: Session = Depends(get_db)):
    books = db.query(models.Book).order_by(models.Book.id).all()
    book_context = format_books_for_prompt(books)
    system_prompt = (
        "You are a concise personalized book recommendation assistant. Use the "
        "reader's saved book list as the main evidence, especially read books, "
        "currently reading books, authors, and ratings when available. Avoid "
        "recommending books already saved unless the user asks about them. Keep "
        "the response practical and brief.\n\n"
        f"Reader book context:\n{book_context}"
    )

    history = normalize_history(request.conversation_history)
    messages = [*history, {"role": "user", "content": request.message}]
    reply = call_claude(system_prompt, messages, max_tokens=700)

    updated_history = [*messages, {"role": "assistant", "content": reply}]
    return {"reply": reply, "updated_history": updated_history}


@app.get("/books", response_model=list[schemas.BookRead])
def get_books(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Book).order_by(models.Book.id)

    if status is not None:
        if status not in schemas.VALID_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="status filter must be reading, read, or want_to_read",
            )
        query = query.filter(models.Book.status == status)

    return query.all()


@app.get("/books/stats", response_model=schemas.BookStats)
def get_stats(db: Session = Depends(get_db)):
    books = db.query(models.Book).all()
    read_ratings = [
        book.rating
        for book in books
        if book.status == "read" and book.rating is not None
    ]

    return {
        "total_books": len(books),
        "by_status": {
            "want_to_read": sum(1 for book in books if book.status == "want_to_read"),
            "reading": sum(1 for book in books if book.status == "reading"),
            "read": sum(1 for book in books if book.status == "read"),
        },
        "average_rating_for_read_books": (
            sum(read_ratings) / len(read_ratings) if read_ratings else 0
        ),
    }


@app.get("/books/{book_id}", response_model=schemas.BookRead)
def get_book(book_id: int, db: Session = Depends(get_db)):
    return get_book_or_404(book_id, db)


@app.post("/books", response_model=schemas.BookRead, status_code=201)
def create_book(book: schemas.BookCreate, db: Session = Depends(get_db)):
    validate_book_rules(book.status, book.rating)

    db_book = models.Book(
        title=book.title,
        author=book.author,
        status=book.status,
        rating=book.rating,
    )
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book


@app.put("/books/{book_id}", response_model=schemas.BookRead)
def update_book(
    book_id: int,
    updates: schemas.BookUpdate,
    db: Session = Depends(get_db),
):
    book = get_book_or_404(book_id, db)

    new_status = updates.status if updates.status is not None else book.status
    new_rating = updates.rating if updates.rating is not None else book.rating

    if updates.status is not None and updates.status != "read" and updates.rating is None:
        new_rating = None

    validate_book_rules(new_status, new_rating)

    if updates.title is not None:
        book.title = updates.title
    if updates.author is not None:
        book.author = updates.author
    if updates.status is not None:
        book.status = updates.status
    if updates.status is not None and updates.status != "read" and updates.rating is None:
        book.rating = None
    elif updates.rating is not None:
        book.rating = updates.rating

    db.commit()
    db.refresh(book)
    return book


@app.delete("/books/{book_id}")
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = get_book_or_404(book_id, db)
    db.delete(book)
    db.commit()
    return {"message": f"Book {book_id} deleted successfully"}
