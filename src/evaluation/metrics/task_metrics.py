def success_rate(values: list[bool]) -> float:
    return sum(values) / len(values) if values else 0.0
