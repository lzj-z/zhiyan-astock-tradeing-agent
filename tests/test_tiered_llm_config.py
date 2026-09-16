"""Quick/deep tiers may use different providers and output limits."""

from tradingagents.default_config import DEFAULT_CONFIG


def test_default_dual_llm_configuration_uses_each_provider_limit():
    assert DEFAULT_CONFIG["quick_think_provider"] == "qwen"
    assert DEFAULT_CONFIG["quick_think_llm"] == "qwen3.8-flash"
    assert DEFAULT_CONFIG["quick_think_max_tokens"] == 131072
    assert DEFAULT_CONFIG["deep_think_provider"] == "deepseek"
    assert DEFAULT_CONFIG["deep_think_llm"] == "deepseek-flash"
    assert DEFAULT_CONFIG["deep_think_max_tokens"] == 393216


def test_graph_builds_each_tier_with_its_own_provider_and_limit(monkeypatch, tmp_path):
    from tradingagents.graph import trading_graph as tg

    created = []

    class FakeClient:
        def __init__(self, spec):
            self.spec = spec

        def get_llm(self):
            return self.spec

    class FakeWorkflow:
        def compile(self):
            return object()

    class FakeGraphSetup:
        def __init__(self, *args, **kwargs):
            pass

        def setup_graph(self, selected_analysts):
            return FakeWorkflow()

    monkeypatch.setattr(tg, "set_config", lambda config: None)
    monkeypatch.setattr(tg, "TradingMemoryLog", lambda config: object())
    monkeypatch.setattr(tg, "GraphSetup", FakeGraphSetup)
    monkeypatch.setattr(tg, "ConditionalLogic", lambda **kwargs: object())
    monkeypatch.setattr(tg, "Propagator", lambda: object())
    monkeypatch.setattr(tg, "Reflector", lambda llm: object())
    monkeypatch.setattr(tg, "SignalProcessor", lambda llm: object())
    monkeypatch.setattr(tg.TradingAgentsGraph, "_create_tool_nodes", lambda self: {})

    def fake_create_llm_client(provider, model, base_url=None, **kwargs):
        spec = {"provider": provider, "model": model, "max_tokens": kwargs.get("max_tokens")}
        created.append(spec)
        return FakeClient(spec)

    monkeypatch.setattr(tg, "create_llm_client", fake_create_llm_client)

    tg.TradingAgentsGraph(
        selected_analysts=[],
        config={
            "data_cache_dir": str(tmp_path / "cache"),
            "results_dir": str(tmp_path / "results"),
        },
    )

    assert created[:2] == [
        {"provider": "deepseek", "model": "deepseek-flash", "max_tokens": 393216},
        {"provider": "qwen", "model": "qwen3.8-flash", "max_tokens": 131072},
    ]
