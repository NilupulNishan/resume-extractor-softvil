from resume_pipeline.clients import openai_client, EMBEDDING_DEPLOYMENT, EMBEDDING_DIMENSIONS
# Must match the `dimensions` in the AI Search HNSW vector config (resumes-index)

def generate_embedding(embedding_text: str) -> list[float]:
    """
    Generate a 1536-dimension vector from a semantic text summary.

    The returned list is written directly to the AI Search `embedding` field
    (Collection(Edm.Single)) via writer.py. No transformation needed.
    """
    if not embedding_text or not embedding_text.strip():
        raise ValueError(
            "embedding_text is empty. "
            "Pass the embeddingText from structurer.py, not raw resume text."
        )

    response = openai_client.embeddings.create(
        model=EMBEDDING_DEPLOYMENT,       # text-embedding-3-small
        input=embedding_text.strip(),
    )

    vector = response.data[0].embedding  # list[float] from Azure OpenAI

    # Hard guard — dimensions must match AI Search index config exactly
    # If this fails, the write to AI Search will be rejected
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding dimension mismatch. "
            f"Got {len(vector)}, expected {EMBEDDING_DIMENSIONS}. "
            f"Check AZURE_OPENAI_EMBEDDING_DEPLOYMENT in .env — "
            f"must be text-embedding-3-small."
        )

    return vector