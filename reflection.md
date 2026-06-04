## Week 4 Reflection

1. The biggest change from Week 3 was moving book data out of a Python list and into PostgreSQL. That made the API feel more like a real application because the data still exists after the backend restarts.

2. SQLAlchemy helps the Python code talk to the database using models instead of writing raw SQL for every operation. The `Book` model represents the `books` table, and each row becomes a Python object.

3. CORS is needed because the frontend runs on `http://localhost:3000` while the backend runs on `http://localhost:8000`. Without CORS, the browser would block frontend requests to the API.

4. Environment variables are important because database URLs and secrets should not be hard-coded or committed to Git. The `.env` file stays local, while `.env.example` documents what values are needed.

## Week 5 Reflection

1. A system prompt tells the AI how to behave across the conversation, while a user message is the specific request the user wants answered right now. The separation matters because the app can keep stable rules in the system prompt, such as being concise or using the saved book list for recommendations, while still letting each user message change the immediate task. It also helps prevent app instructions from getting mixed into normal user text.

2. Changing system prompts in Part 4 changed the assistant's style, structure, and boundaries. The opinionated professor prompt made the assistant sound more confident and evaluative. The structured recommendation prompt made answers easier to scan because the model organized recommendations into a predictable format. The books-only constraint reduced off-topic answers and helped keep the assistant focused on the purpose of the app.

3. One potential harm is that the AI could give overly confident recommendations that reinforce a narrow reading pattern or misrepresent a book's content. A mitigation is to keep responses concise, include the user's saved books as context, ask the model to be honest when unsure, and let the user make the final choice instead of presenting recommendations as objective truth.

4. With infinite Claude credits, I would build a reading coach that analyzes each user's library over time and creates a personalized reading path. Technically, the backend would add endpoints for periodic library analysis, store generated insights in a database table, and call Claude with the user's read books, ratings, current books, and stated goals. The frontend would show a dashboard with recommended next books, reading challenges, and short explanations for why each item fits.

## Prompt Engineering Experiments

1. Opinionated literature professor / Marcus: This prompt gave the assistant a strong personality and made recommendations feel more decisive. The expected behavior is more interpretive commentary, sharper opinions, and less neutral wording.

2. Structured recommendation format: This prompt asked for recommendations in a consistent format, such as title, reason, and why it fits the reader's history. The expected behavior is easier-to-read output with less rambling and more predictable sections.

3. Books-only constraint: This prompt told the assistant to stay focused on books, authors, genres, reading habits, and recommendations. The expected behavior is fewer off-topic responses and clearer redirection when the user asks for something unrelated.
