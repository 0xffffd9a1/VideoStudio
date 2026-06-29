def time_to_seconds(time_str) -> float:
    if isinstance(time_str, (int, float)):
        return float(time_str)
    time_str = str(time_str).strip()
    if ':' in time_str:
        parts = list(map(float, time_str.split(':')))
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        else:
            raise ValueError("Неверный формат времени. Ожидается ЧЧ:ММ:СС, ММ:СС или число.")
    else:
        return float(time_str)

def safe_filename(name: str) -> str:
    """Заменяет недопустимые символы в имени файла."""
    keepcharacters = (' ', '.', '_', '-')
    return "".join(c for c in name if c.isalnum() or c in keepcharacters).rstrip()