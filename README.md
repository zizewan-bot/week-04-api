# Week 4 Book Tracker API

FastAPI backend for the Week 4 full stack Book Tracker lab. The API stores books in PostgreSQL using SQLAlchemy and is designed to work with the Week 4 Next.js frontend.

## Run with Docker Compose

```bash
docker compose up --build
```

API docs:

```text
http://localhost:8000/docs
```

## Endpoints

- `GET /books` - list books, optionally filtered by `status`
- `GET /books/{book_id}` - get one book
- `POST /books` - create a book
- `PUT /books/{book_id}` - update a book
- `DELETE /books/{book_id}` - delete a book
- `GET /books/stats` - show book counts and average rating

## Environment

Copy `.env.example` to `.env` for local non-Docker development. The `.env` file is intentionally ignored by Git.
