def mock_series(hostname, base, salt):
    seed = sum(ord(char) for char in hostname) + salt * 17
    points = []
    for index in range(12):
        wobble = ((seed * (index + 3)) % 17) - 8
        points.append(max(4, min(96, int(base) + wobble // 2)))
    points[-1] = int(base)
    return points


def spark_points(values, width=220, height=52):
    step = width / (len(values) - 1)
    coords = []
    for index, value in enumerate(values):
        x = round(index * step, 1)
        y = round(height - (value / 100) * (height - 6) - 3, 1)
        coords.append(f"{x},{y}")
    return " ".join(coords)


def decorate_servers(servers):
    for index, server in enumerate(servers):
        server.cpu_points = spark_points(mock_series(server.hostname, server.cpu_percent, 1))
        server.mem_points = spark_points(mock_series(server.hostname, server.memory_percent, 2))
        server.cpu_dash = round(server.cpu_percent * 1.759, 1)
        server.mem_dash = round(server.memory_percent * 1.759, 1)
        server.bar_x = 28 + index * 108
        server.cpu_h = round(server.cpu_percent * 0.7, 1)
        server.mem_h = round(server.memory_percent * 0.7, 1)
        server.cpu_y = round(92 - server.cpu_h, 1)
        server.mem_y = round(92 - server.mem_h, 1)
    return servers


def alert_evolution(servers, width=720, height=140):
    if not servers:
        return ""
    buckets = [0] * 12
    for server in servers:
        series = mock_series(server.hostname, max(12, min(90, server.cpu_percent + 18)), 4)
        for index, value in enumerate(series):
            buckets[index] += value
    peak = max(buckets) or 1
    scaled = [max(6, round(value / peak * 100)) for value in buckets]
    return spark_points(scaled, width=width, height=height)
