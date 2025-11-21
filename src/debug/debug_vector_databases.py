import asyncio

from ..qdrant_store import QdrantVectorStore
from ..embedding_manager import EmbeddingManager
from ..embedding_backend import StubEmbeddingModel

""" 
    How to run it, in:
     - Terminal: /absolute/path/to/git/repo/Middleware-GenAI/{your_venv_name}/bin/python debug_vector_databases.py (on MacOS)
     - PyCharm debugger:
            - go to debugger config and reference the following:
                            - Run using: your venv's python (path as for terminal)
                            - Script: absolute/path/to/repo/Middleware-GenAI/debug_vector_databases.py
                            - Working directory: absolute/path/to/repo/Middleware-GenAI
    
    IMPORTANT: 
        Make sure that the Qdrant docker image is up and running on port 6333. If not, open Docker Desktop and execute 
        the following in a terminal session: 
                        docker run -p 6333:6333 qdrant/qdrant

"""
# TODO: if debugging other vector databases it might be beneficial to make this dynamic
# TODO: write tests with it ?

async def main():
    store = QdrantVectorStore()
    model = StubEmbeddingModel(dim=256)
    em = EmbeddingManager(embedding_model=model, vector_store=store)

    print("Bootstrapping demo corpus...")
    await store.bootstrap_demo_corpus(model, collection="demo_corpus")

    query = "I would like to learn more about RAG."
    print("Running semantic search for:", query)

    result = await em.semantic_search(
        user_id="user",        # important: see note below
        corpus_id="demo_corpus",
        query=query,
        k=5,
    )

    print("RESULT:")
    for hit in result["results"]:
        print(f"- score={hit['score']:.4f} text=\"{hit['payload']['text']}\"")


if __name__ == "__main__":
    asyncio.run(main())