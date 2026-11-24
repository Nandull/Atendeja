import re
import unicodedata


def slugify(text: str, max_length: int = 50) -> str:
    """'Clínica Bella Estética' -> 'clinica-bella-estetica'."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    slug = slug[:max_length].strip("-")
    return slug or "estabelecimento"


def slug_candidates(base: str, attempts: int = 20):
    """Gera 'base', 'base-2', 'base-3'... para contornar slugs já usados."""
    yield base
    for n in range(2, attempts + 2):
        yield f"{base}-{n}"
