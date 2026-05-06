def deduplicate(items):
    seen = set()
    result = []
    for item in items:
        if item in seen:
            result.append(item)
        seen.add(item)
    return result
