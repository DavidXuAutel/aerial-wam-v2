from experiments.aerial.deploy.c922_controls import (
    get_preset,
    list_presets,
    v4l2_device_path,
)


def test_v4l2_device_path():
    assert v4l2_device_path("2") == "/dev/video2"
    assert v4l2_device_path("/dev/video2") == "/dev/video2"


def test_outdoor_bench_preset():
    p = get_preset("outdoor_bench")
    assert p.focus_automatic_continuous == 0
    assert p.exposure_time_absolute == 20
    assert p.brightness == 110


def test_list_presets_includes_defaults():
    names = list_presets()
    assert "outdoor_bench" in names
    assert "outdoor_dim" in names
