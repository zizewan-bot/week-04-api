from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Book Tracker API", version="2.0.0")

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


@app.get("/")
def read_root():
    return {"message": "Welcome to Book Tracker API"}


@app.get("/health")
def health():
    return {"status": "ok"}


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
