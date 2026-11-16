async def search(store, course_id, query, lecture_id=None):
    """Find the lecture passages whose meaning is closest to the question."""
    # Step 1: turn the question into numbers (an embedding).
    vectors = await store.embed([____])  # a list with just the question (query) in it
    question_vector = vectors[0]

    # Step 2: find the closest passages, only inside the chosen course (and lecture).
    return store.query_vectors(question_vector, ____, ____)  # course_id, then lecture_id
