from agents import RunConfig, Runner

PRIVATE = RunConfig(tracing_disabled=True, trace_include_sensitive_data=False)


async def ask_tutor(agent, message, session, max_turns):
    """Send ONE new message to the tutor. The session adds the earlier conversation."""
    return await Runner.run(
        ____,  # who answers? the agent
        ____,  # what is asked? only the new message
        session=____,  # where is the conversation remembered? the session
        max_turns=max_turns,  # safety limit on how often the AI may use its tool
        run_config=PRIVATE,  # do not send traces of the conversation to OpenAI
    )
