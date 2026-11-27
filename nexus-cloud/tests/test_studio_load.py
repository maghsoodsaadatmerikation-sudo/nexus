"""Overlapping synthetic requests: bounded model load, recovery and cancellation."""
import os

import anyio
import httpx
import pytest

import main
import studio_model


@pytest.mark.parametrize("cancel", [False, True])
def test_saturated_model_gateway_recovers_without_replay_or_budget_refund(monkeypatch, cancel):
    for name in os.environ:
        if name.startswith("NEXUS_MODEL_"):
            monkeypatch.delenv(name)
    token = "synthetic-load-studio-token-0123456789"
    monkeypatch.setenv("NEXUS_STUDIO_TOKEN", token)
    monkeypatch.setenv("NEXUS_MODEL_URL", "https://provider.example/v1/chat/completions")
    monkeypatch.setenv("NEXUS_MODEL_ID", "synthetic-load-model")
    monkeypatch.setenv("NEXUS_MODEL_MAX_REQUESTS_PER_PROCESS", "10")
    body = {"consent": True,
            "configuration_id": studio_model.configuration_id(studio_model.read_model_settings()),
            "messages": [{"role": "user", "content": "Synthetic load question"}]}

    async def run():
        started = anyio.Event()
        release = anyio.Event()
        calls = []
        responses = []

        async def upstream(request):
            calls.append(request)
            if len(calls) == 4:
                started.set()
            await release.wait()
            return httpx.Response(200, json={"choices": [{
                "message": {"role": "assistant", "content": "Synthetic load answer"},
                "finish_reason": "stop",
            }]})

        async with main.lifespan(main.app):
            async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as provider:
                main.app.state.client = provider
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                             base_url="http://studio.test",
                                             headers={"authorization": "Bearer " + token}) as client:
                    async def call():
                        responses.append(await client.post("/studio-api/respond", json=body))

                    with anyio.fail_after(10):
                        async with anyio.create_task_group() as tasks:
                            for _ in range(4):
                                tasks.start_soon(call)
                            await started.wait()
                            for path in ("/studio-api/respond", "/studio-api/respond-stream"):
                                busy = await client.post(path, json=body)
                                assert busy.status_code == 429
                                assert busy.headers["retry-after"] == "5"
                            assert len(calls) == 4
                            assert main.app.state.model_budget.snapshot()["attempted"] == 4
                            assert (await client.get("/healthz")).status_code == 200
                            if cancel:
                                tasks.cancel_scope.cancel()
                            else:
                                release.set()
                    assert main.app.state.model_limiter.borrowed_tokens == 0
                    assert main.app.state.model_budget.snapshot()["attempted"] == 4
                    if not cancel:
                        assert len(responses) == 4 and all(r.status_code == 200 for r in responses)
                    release.set()
                    recovered = await client.post("/studio-api/respond", json=body)
                    assert recovered.status_code == 200 and len(calls) == 5
                    assert main.app.state.model_budget.snapshot()["attempted"] == 5
                    assert main.app.state.model_limiter.borrowed_tokens == 0

    anyio.run(run)
