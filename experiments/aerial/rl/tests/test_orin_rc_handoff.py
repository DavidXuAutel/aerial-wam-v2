from experiments.aerial.rl.env.orin_rc_handoff import (
    OrinRcHandoff,
    OrinRcHandoffConfig,
    RcRecordGate,
    RcRecordGateConfig,
    release_rc_overrides,
)


def test_rising_edge_toggles() -> None:
    h = OrinRcHandoff(OrinRcHandoffConfig(debounce_s=0.0))
    assert not h.active
    assert not h.update_pwm(1051)
    assert not h.update_pwm(1051)
    assert h.update_pwm(1951)
    assert h.active
    assert not h.update_pwm(1051)
    assert h.update_pwm(1951)
    assert not h.active


def test_no_toggle_without_release_between_presses() -> None:
    h = OrinRcHandoff(OrinRcHandoffConfig(debounce_s=0.0))
    h.update_pwm(1051)
    h.update_pwm(1951)
    assert h.active
    assert not h.update_pwm(1951)


def test_release_rc_overrides_uses_no_override_pwm() -> None:
    calls: list[tuple[int, ...]] = []

    class _Mav:
        class _MavInner:
            @staticmethod
            def rc_channels_override_send(*args: int) -> None:
                calls.append(tuple(args[2:10]))

        mav = _MavInner()

    release_rc_overrides(_Mav(), 1, 1, repeats=1)
    assert calls == [(65535, 65535, 65535, 65535, 65535, 65535, 65535, 65535)]


def test_record_gate_ch8_start_ch9_stop() -> None:
    g = RcRecordGate(RcRecordGateConfig(debounce_s=0.0))
    rc = {"ch8": 1051, "ch9": 1051}
    assert g.update_rc_dict(rc) == "none"
    rc["ch8"] = 1951
    assert g.update_rc_dict(rc) == "start"
    assert g.active
    rc["ch8"] = 1051
    rc["ch9"] = 1951
    assert g.update_rc_dict(rc) == "stop"
    assert not g.active
