import importlib


def test_simulate_module_importable():
    mod = importlib.import_module("ecadec_pw.simulate")
    assert hasattr(mod, "main")
