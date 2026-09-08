def cmd_ingest(args) -> None:
    settings = load_settings()
    chunks = load_chunks(settings)
    embedder = Embedder(settings)
    print(f"embedding {len(chunks)} chunks with {settings.embed_model} ...")
    vectors = embedder.embed_documents([c.text for c in chunks])
    store = Store(settings.db_path)
    store.replace_all(chunks, vectors)
    print(f"stored {store.count()} chunks, dim={vectors.shape[1]}")