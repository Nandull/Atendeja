import re
import unicodedata


def normalize_search(text: str) -> str:
    """'José da Silva ' -> 'jose da silva' (para busca sem acento)."""
    no_accents = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", no_accents).strip().lower()


def normalize_phone(raw: str) -> str:
    """Aceita '(21) 99999-0000', '+55 21 99999-0000' etc. Devolve '21999990000'.

    Levanta ValueError se não for um telefone brasileiro com DDD.
    """
    digits = re.sub(r"\D", "", raw)
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    if len(digits) not in (10, 11) or digits[0] == "0":
        raise ValueError("telefone deve ter DDD + número (10 ou 11 dígitos)")
    return digits
