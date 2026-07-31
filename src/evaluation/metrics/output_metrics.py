def completion_rate(present: int, required: int) -> float:
    return present / required if required else 1.0
