"""Raqam validatori: LLM javobidagi har bir raqam kirish faktlarida bo'lishi shart (10-bo'lim, 3-band)."""
import json
import re

NUM_RE = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?")
SMALL_INT_OK = set(range(0, 11))  # sanoq so'zlari, "2–3 kun" kabi kichik butun sonlar


def extract_numbers(text: str) -> list[float]:
    out = []
    for m in NUM_RE.findall(text or ""):
        try:
            out.append(float(m.replace(",", ".")))
        except ValueError:
            continue
    return out


def allowed_numbers(payload) -> set[float]:
    """Kirish JSON'idagi barcha sonlar (shu jumladan matn ichidagilar)."""
    found: set[float] = set()

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            found.add(float(x))
        elif isinstance(x, str):
            found.update(extract_numbers(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(payload)
    return found


def is_allowed(n: float, allowed: set[float]) -> bool:
    if n.is_integer() and int(n) in SMALL_INT_OK:
        return True
    for a in allowed:
        if abs(n - a) <= max(0.05 * abs(a), 0.051) or abs(n - round(a)) < 1e-9 or abs(abs(n) - abs(a)) < 1e-9:
            return True
    return False


def unknown_numbers(text: str, allowed: set[float]) -> list[float]:
    return [n for n in extract_numbers(text) if not is_allowed(n, allowed)]


def validate_texts(texts: list[str], payload) -> list[float]:
    allowed = allowed_numbers(json.loads(json.dumps(payload, default=str)))
    bad: list[float] = []
    for t in texts:
        bad.extend(unknown_numbers(t, allowed))
    return bad
