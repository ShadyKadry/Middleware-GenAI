from embedding_manager import search_similar

if __name__ == "__main__":
    results = search_similar("Middleware", top_k=5)
    print("Search results:")
    for r in results:
        print(r)
