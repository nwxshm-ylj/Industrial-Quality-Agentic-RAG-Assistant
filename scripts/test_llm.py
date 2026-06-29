from langchain_openai import ChatOpenAI
from app.core.config import settings


def main():
    print("LLM_MODEL:", settings.llm_model)
    print("LLM_BASE_URL:", settings.llm_base_url)
    print("LLM_API_KEY exists:", bool(settings.llm_api_key))

    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.1,
        max_tokens=512,
    )

    response = llm.invoke("请用一句话介绍什么是RAG。")

    print("response:", response)
    print("content:", repr(response.content))


if __name__ == "__main__":
    main()