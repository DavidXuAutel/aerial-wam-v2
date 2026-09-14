from experiments.aerial.deploy.c922_controls import v4l2_device_path
from experiments.aerial.deploy.hj_camera_controls import (
    get_preset,
    list_presets,
)


def test_v4l2_device_path_hj():
    assert v4l2_device_path("0") == "/dev/video0"


def test_outdoor_bench_preset():
    p = get_preset("outdoor_bench")
    assert p.auto_exposure == 1
    assert p.exposure_time_absolute == 6
    assert p.brightness == -10
    assert p.gain == 0
    assert p.hue == -30
    assert p.backlight_compensation == 0


def test_list_presets_includes_defaults():
    names = list_presets()
    assert "outdoor_bench" in names
    assert "outdoor_bright" in names
    assert "outdoor_dim" in names
