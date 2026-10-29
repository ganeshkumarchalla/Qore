"""First-visit lessons must not exhaust the assistant's shared provider quota."""


def test_first_visit_question_uses_local_pool_by_default(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-provider-value")
    monkeypatch.delenv("QORE_AI_QUIZ_ENABLED", raising=False)

    class UnexpectedProviderCall:
        def __init__(self, **_options):
            raise AssertionError("First-visit lessons should not call the provider by default")

    monkeypatch.setattr("qore.main.httpx.AsyncClient", UnexpectedProviderCall)
    response = client.get("/api/quantum/onboarding-question")
    assert response.status_code == 200
    question = response.json()
    assert isinstance(question["question"], str) and question["question"]
    assert len(question["options"]) == 4
    assert sum(option["correct"] is True for option in question["options"]) == 1
