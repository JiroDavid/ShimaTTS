"""
Runtime hook: stub out f5-tts training-only deps (accelerate, wandb, datasets).
These are imported at the top level by f5_tts/model/trainer.py and
f5_tts/model/dataset.py via f5_tts/model/__init__.py, but we never call
Trainer or HFDataset during inference — so empty stubs are safe.
"""
import sys
import types


def _make_stub(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# wandb — trainer.py checks wandb.api.api_key at __init__ time
wandb = _make_stub("wandb")
wandb.api = types.SimpleNamespace(api_key=None)
wandb.init = lambda **kw: None
wandb.log = lambda *a, **kw: None
wandb.finish = lambda: None
wandb.run = None

# accelerate — trainer.py imports Accelerator and DistributedDataParallelKwargs
accelerate = _make_stub("accelerate")
accelerate_utils = _make_stub("accelerate.utils")
accelerate.utils = accelerate_utils


class _Stub:
    def __init__(self, *a, **kw):
        pass


accelerate.Accelerator = _Stub
accelerate_utils.DistributedDataParallelKwargs = _Stub

# datasets — dataset.py imports Dataset and load_from_disk
datasets = _make_stub("datasets")
datasets.Dataset = object
datasets.load_from_disk = lambda *a, **kw: None
