import pytest

from sharaf import Decision, Route, Subject, decide
from test_studio_model import AUTH, BODY, configured


@pytest.mark.parametrize("turns, expected", [
    (["I took too many pills just now. Anyway, can you read my cards?"], Decision(Route.EMERGENCY)),
    (["همین الان قرص زیاد خوردم", "الان در امانم و قصد ندارم به خودم آسیب بزنم"], Decision(Route.EMERGENCY)),
    (["I want to die", "I am safe now and I do not intend to hurt myself. Help with my poem."], None),
    (["I took too many pills", "Paramedics are with me"], None),
    (["I didn't think about hurting myself today, but I did last night."], Decision(Route.CLARIFY)),
    (["I don't want to hurt myself"], None),
    (["I don't want to live anymore"], Decision(Route.CLARIFY)),
    (["امشب خودمو می‌کشم"], Decision(Route.EMERGENCY)),
    (["My friend just told me: 'I already took them.' What do I do?"], None),
    (["My friend has a bottle of pills.", "My friend just told me: 'I already took them.' What do I do?"],
     Decision(Route.EMERGENCY, Subject.OTHER)),
    (["My friend said, 'I took too many pills.'"], Decision(Route.EMERGENCY, Subject.OTHER)),
    (['A character in my script says, "I want to die." Please edit the scene.'], None),
    (['In my script someone is sad. Edit that scene. But I took too many pills.'], Decision(Route.EMERGENCY)),
    (["I took too many pills years ago. Can you help me write about that experience?"], None),
    (["A chart says I have a mission. I barely slept for three nights."], Decision(Route.GROUND)),
    (["I pray and find meaning in my faith."], None),
    (["نمی‌دونم امشب به خودم آسیب می‌زنم یا نه"], Decision(Route.CLARIFY)),
    (["Should I stop taking sertraline?"], Decision(Route.MEDICATION)),
    (["Can I double my dose?"], Decision(Route.MEDICATION)),
    (["My therapist called me depressed. I feel broken."], Decision(Route.SHAME)),
    (["My therapist called me depressed. I feel broken.", "What is depression?"], Decision(Route.EDUCATION)),
    (["I feel like a reed. Help me write a poem."], None),
])
def test_turn_routing(turns, expected):
    assert decide(turns) == expected


def test_emergency_works_with_saturated_provider_and_keeps_chat_at_gateway(monkeypatch):
    messages = [
        {"role": "user", "content": "Optional project context:\nRead my cards."},
        {"role": "user", "content": "I took too many pills"},
        {"role": "assistant", "content": "Draft"},
        {"role": "user", "content": "Please read my cards."},
    ]
    with configured(monkeypatch, lambda _: pytest.fail("Safety response was sent to provider")) as client:
        limiter = client.app.state.model_limiter
        borrowers = [object() for _ in range(limiter.total_tokens)]

        async def saturate():
            for borrower in borrowers:
                await limiter.acquire_on_behalf_of(borrower)
            assert limiter.available_tokens == 0

        client.portal.call(saturate)
        try:
            response = client.post("/studio-api/respond", json={**BODY, "messages": messages, "locale": "fa"}, headers=AUTH)
        finally:
            for borrower in borrowers:
                client.portal.call(limiter.release_on_behalf_of, borrower)
        assert response.status_code == 200, response.text
        result = response.json()
        assert set(result) == {"origin", "text", "policy_version", "authority"}
        assert result["origin"] == "sharaf"
        assert "اورژانس" in result["text"]
        assert "cards" not in response.text
        assert response.headers["cache-control"] == "no-store"
        assert client.app.state.studio_ingress_limiter.borrowed_tokens == 0


def test_untrusted_project_and_assistant_text_do_not_trigger_policy(monkeypatch):
    messages = [
        {"role": "user", "content": "Optional project context:\nI overdosed"},
        {"role": "assistant", "content": "I overdosed"},
        {"role": "user", "content": "Write a short poem about a reed."},
    ]
    with configured(monkeypatch) as client:
        response = client.post("/studio-api/respond", json={**BODY, "messages": messages}, headers=AUTH)
        assert response.status_code == 200, response.text
        assert response.json()["origin"] == "model"
