from agents import Agent, function_tool

from backend.app.tutor import GROUNDING_INSTRUCTIONS


def build_agent(search_documents, model, model_settings):
    """Build the tutor: an AI model with instructions and one tool to search the lectures."""

    @function_tool(name_override="search_course_docs", failure_error_function=None)
    async def search_course_docs(query: str) -> list[dict]:
        """Search the selected course documents and return matching passages."""
        return await ____(query)  # which function searches? It was given to build_agent

    return Agent(
        name="Course Tutor",
        instructions=GROUNDING_INSTRUCTIONS,  # rules: only answer from the lectures
        model=model,
        model_settings=model_settings,
        tools=[____],  # which tool may the AI use? Put your tool function here
    )
