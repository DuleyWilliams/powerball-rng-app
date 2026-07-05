from analytics_engine.gaps import white_ball_gap_analysis, powerball_gap_analysis

DRAWS = [
    [1, 2, 3, 4, 5, 6],
    [7, 8, 9, 10, 11, 12],
]


def test_white_ball_gap_analysis_values():
    gaps = {item["Number"]: item["Drawings Since Last Seen"] for item in white_ball_gap_analysis(DRAWS)}

    assert gaps[1] == 0
    assert gaps[5] == 0
    assert gaps[7] == 1
    assert gaps[11] == 1
    assert gaps[6] == "Never Seen"
    assert gaps[69] == "Never Seen"


def test_white_ball_gap_analysis_orders_worst_gaps_first():
    gaps = white_ball_gap_analysis(DRAWS)
    assert gaps[0]["Drawings Since Last Seen"] == "Never Seen"


def test_powerball_gap_analysis_values():
    gaps = {item["Powerball"]: item["Drawings Since Last Seen"] for item in powerball_gap_analysis(DRAWS)}

    assert gaps[6] == 0
    assert gaps[12] == 1
    assert gaps[1] == "Never Seen"
    assert gaps[26] == "Never Seen"
