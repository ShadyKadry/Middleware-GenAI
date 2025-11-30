from content_manager import create_document, get_document

if __name__ == "__main__":
    doc_id = create_document("Middleware doc", "This document is stored via content_manager.")
    print("Created document with id:", doc_id)

    doc = get_document(doc_id)
    print("Fetched document:", doc)
