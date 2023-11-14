from fuzzomatic.tools import llm


def test_4k_prompt():
    llm.load_openai_api_key()
    llm.reset_ask_llm_counts()
    prompt = "How many words are in the following sentence?\n"
    prompt += "blabla " * 1300
    response = llm.ask_llm(prompt)
    print(response)
    assert response is not None


def test_16k_prompt():
    llm.load_openai_api_key()
    llm.reset_ask_llm_counts()
    prompt = "How many words are in the following sentence?\n"
    prompt += "blabla " * 6000
    response = llm.ask_llm(prompt)
    print(response)
    assert response is None
