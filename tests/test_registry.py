from insectome.schemas.dataset import load_registry


def test_registry_loads_and_ranks():
    reg = load_registry()
    assert reg.version == 1
    assert len(reg.datasets) >= 5
    top = reg.ranked()[0]
    assert top.dataset_id == "cremi_sample_a"
    assert top.raw_data_available is True


def test_processable_excludes_inaccessible():
    reg = load_registry()
    ids = {d.dataset_id for d in reg.processable()}
    assert "cremi_sample_a" in ids
    assert "aedes_antennal_lobe_bao2025" in ids
    assert "heinze_cx_earwig_2026" not in ids
