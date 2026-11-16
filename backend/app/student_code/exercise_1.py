async def ask_model(client, settings, prompt):
    """Send one question to the AI model and return its answer as text."""
    response = await client.responses.create(
        model=____,  # which model? It is stored in settings.model
        input=____,  # what do we ask? The question is in prompt
        max_output_tokens=settings.max_output_tokens,  # limits answer length (and cost)
        store=False,  # do not keep this request on OpenAI's servers
    )
    return response.output_text
