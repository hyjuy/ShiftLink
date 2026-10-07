"""warm_models: load the judge (and answer) model at MES start with the same num_ctx as real calls."""
from types import SimpleNamespace

from shiftlink.mes.query import warm_models


class Model:
    def __init__(self, fail_first=0):
        self.model, self.num_ctx, self.judge_model, self.judge_num_ctx = "answer", 4096, "judge", 2048
        self.posts, self.fail_first = [], fail_first

    def _post(self, path, payload):
        if self.fail_first:
            self.fail_first -= 1
            raise ConnectionError("ollama starting")
        self.posts.append((path, payload["model"], payload["options"]["num_ctx"], payload["keep_alive"]))
        return {}


def pipe(mode, model):
    return SimpleNamespace(answer_mode=mode, model=model)


def test_hybrid_loads_judge_then_answer_with_their_own_context():
    model = Model()
    assert warm_models(pipe("hybrid", model)) == ["judge", "answer"]
    assert model.posts == [("/api/generate", "judge", 2048, -1), ("/api/generate", "answer", 4096, -1)]


def test_extract_loads_only_the_judge():
    model = Model()
    assert warm_models(pipe("extract", model)) == ["judge"]


def test_retries_while_ollama_is_starting_and_gives_up_quietly():
    model, waits = Model(fail_first=2), []
    assert warm_models(pipe("extract", model), sleep=waits.append) == ["judge"] and waits == [10.0, 10.0]
    model = Model(fail_first=99)
    assert warm_models(pipe("hybrid", model), attempts=3, sleep=lambda s: None) == []
