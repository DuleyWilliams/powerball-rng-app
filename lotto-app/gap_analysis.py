def white_ball_gap_analysis(draws):
    gaps = []

    for number in range(1, 70):
        last_seen = None

        for index, draw in enumerate(draws):
            white_balls = draw[:5]

            if number in white_balls:
                last_seen = index
                break

        gaps.append({
            "Number": number,
            "Drawings Since Last Seen": last_seen if last_seen is not None else "Never Seen"
        })

    return sorted(
        gaps,
        key=lambda item: item["Drawings Since Last Seen"]
        if isinstance(item["Drawings Since Last Seen"], int)
        else 9999,
        reverse=True
    )


def powerball_gap_analysis(draws):
    gaps = []

    for number in range(1, 27):
        last_seen = None

        for index, draw in enumerate(draws):
            powerball = draw[5]

            if number == powerball:
                last_seen = index
                break

        gaps.append({
            "Powerball": number,
            "Drawings Since Last Seen": last_seen if last_seen is not None else "Never Seen"
        })

    return sorted(
        gaps,
        key=lambda item: item["Drawings Since Last Seen"]
        if isinstance(item["Drawings Since Last Seen"], int)
        else 9999,
        reverse=True
    )