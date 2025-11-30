import psycopg

conn = psycopg.connect("postgresql://middleware_user:middleware_pwd@localhost:5434/middleware_genai")


with conn:
    with conn.cursor() as cur:
        # insert a test document
        cur.execute(
            """
            INSERT INTO documents (title, content)
            VALUES (%s, %s)
            RETURNING id;
            """,
            ("Test document", "This is a test document stored from Python."),
        )
        doc_id = cur.fetchone()[0]
        print("Inserted document with id:", doc_id)

        # read it back
        cur.execute("SELECT id, title, content FROM documents WHERE id = %s;", (doc_id,))
        row = cur.fetchone()
        print("Fetched document:", row)

conn.close()
