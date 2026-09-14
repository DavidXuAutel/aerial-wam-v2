from experiments.aerial.scripts.eval_phase3_handover_decouple import _convert_phase2_approach_rows


def test_convert_phase2_approach_rows():
    segments = [
        {"segment_name": "Approach_Route_01", "handover_id": "HO01", "scene": "outdoor_approach"},
    ]
    payload = {
        "subgoal_source": "toward_g",
        "cruise_speed_m_s": 10.0,
        "episodes": [
            {
                "arrived": True,
                "collided": False,
                "spawn_fail": False,
                "d_start_m": 30.0,
                "d_final_m": 2.5,
                "d_min_m": 2.5,
                "steps": 80,
                "goal_closure": 0.92,
                "intervention_rate": 0.1,
            }
        ],
    }
    rows = _convert_phase2_approach_rows(segments, payload)
    assert len(rows) == 1
    assert rows[0]["segment_name"] == "Approach_Route_01"
    assert rows[0]["arrived"] is True
    assert rows[0]["eval_protocol"] == "phase2_toward_g_planner_shield"
    assert rows[0]["ok"] is True
