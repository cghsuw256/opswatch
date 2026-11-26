"""Deterministic example event counts for the educational dashboard."""

import math
import random
from datetime import timedelta

from django.utils import timezone


def alert_evolution(servers):
    # These are examples, not events derived from resource percentages.
    profiles = (2, 4, 1, 9, 5, 3, 12, 6, 2, 7, 14, 4)
    values = {key: [0] * 12 for key in ("info", "warn", "critical")}
    for server in servers:
        if not server.seed_metrics:
            continue
        seed = sum((index + 1) * ord(char) for index, char in enumerate(server.hostname))
        rng = random.Random(seed)
        for index, activity in enumerate(profiles):
            values["info"][index] += activity + rng.randrange(5)
            values["warn"][index] += rng.randrange(activity // 2 + 2)
            values["critical"][index] += rng.randrange(4) if index in (3, 6, 10) else 0

    scale = max(4, math.ceil(max(max(row) for row in values.values()) / 4) * 4)
    now = timezone.localtime().replace(minute=0, second=0, microsecond=0)
    hours = [(now - timedelta(hours=11 - index)).strftime("%H:%M") for index in range(12)]
    series = []
    for key, label in (("info", "정보"), ("warn", "주의"), ("critical", "위험")):
        markers = [
            {
                "x": round(15 + index * 690 / 11, 1),
                "y": round(150 - value / scale * 140, 1),
                "value": value,
                "label": hours[index],
            }
            for index, value in enumerate(values[key])
        ]
        series.append(
            {
                "key": key,
                "label": label,
                "points": " ".join(f"{point['x']},{point['y']}" for point in markers),
                "total": sum(values[key]),
                "markers": markers,
            }
        )

    totals = [sum(row[index] for row in values.values()) for index in range(12)]
    peak_index = totals.index(max(totals))
    return {
        "series": series,
        "ticks": [{"y": 150 - index * 35, "value": scale * index // 4} for index in range(5)],
        "peak_count": totals[peak_index],
        "peak_label": hours[peak_index],
        "total": sum(totals),
    }
