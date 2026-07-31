def gate_passed(*, expected: bool, triggered: bool, waiting: bool) -> bool:
    return (expected and triggered and waiting) or (not expected and not triggered and not waiting)
