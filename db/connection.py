import psycopg


def get_connection():
    # For now, we hardcode the local dev DB.
    # Later we can move this to environment variables.
    return psycopg.connect(
        "postgresql://middleware_user:middleware_pwd@localhost:5434/middleware_genai"
    )
