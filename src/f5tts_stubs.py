"""
Stub out f5-tts training-only deps (accelerate, wandb, datasets) when they are
not installed. f5_tts/model/__init__.py imports them transitively via
trainer.py/dataset.py, but inference never calls Trainer or HFDataset, so
empty stubs are safe. Must be imported before f5_tts.
"""
import importlib.machinery
import importlib.util
import sys
import types


def _missing(name: str) -> bool:
    if name in sys.modules:
        return False
    try:
        return importlib.util.find_spec(name) is None
    except (ImportError, ValueError):
        return True


def _make_stub(name):
    mod = types.ModuleType(name)
    # transformers probes optional deps with importlib.util.find_spec, which
    # raises ValueError for an in-sys.modules module whose __spec__ is None
    mod.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    sys.modules[name] = mod
    return mod


class _Stub:
    def __init__(self, *a, **kw):
        pass


def install() -> None:
    if _missing("wandb"):
        wandb = _make_stub("wandb")
        wandb.api = types.SimpleNamespace(api_key=None)
        wandb.init = lambda **kw: None
        wandb.log = lambda *a, **kw: None
        wandb.finish = lambda: None
        wandb.run = None

    if _missing("accelerate"):
        accelerate = _make_stub("accelerate")
        accelerate_utils = _make_stub("accelerate.utils")
        accelerate.utils = accelerate_utils
        accelerate.Accelerator = _Stub
        accelerate_utils.DistributedDataParallelKwargs = _Stub

    if _missing("datasets"):
        datasets = _make_stub("datasets")
        datasets.Dataset = object
        datasets.load_from_disk = lambda *a, **kw: None
