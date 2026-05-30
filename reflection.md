## Week 4 Reflection

1. The biggest change from Week 3 was moving book data out of a Python list and into PostgreSQL. That made the API feel more like a real application because the data still exists after the backend restarts.

2. SQLAlchemy helps the Python code talk to the database using models instead of writing raw SQL for every operation. The `Book` model represents the `books` table, and each row becomes a Python object.

3. CORS is needed because the frontend runs on `http://localhost:3000` while the backend runs on `http://localhost:8000`. Without CORS, the browser would block frontend requests to the API.

4. Environment variables are important because database URLs and secrets should not be hard-coded or committed to Git. The `.env` file stays local, while `.env.example` documents what values are needed.
