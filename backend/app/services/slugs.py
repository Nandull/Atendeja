import re
import unicodedata


def slugify(text: str, max_length: int = 50) -> str:
    """'Clínica Bella Estética' -> 'clinica-bella-estetica'."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    slug = slug[:max_length].strip("-")
    return slug or "estabelecimento"


# O link público é atendeja.com.br/<slug>. Estes nomes são páginas do próprio
# sistema e não podem virar link de estabelecimento.
RESERVED_SLUGS = frozenset(
    {
        "a", "admin", "agenda", "api", "app", "ajuda", "assets", "bloqueios", "cadastro",
        "clientes", "configuracoes", "contato", "docs", "entrar", "equipe", "login",
        "planos", "precos", "profissionais", "public", "sair", "servicos", "suporte",
        "static", "termos", "privacidade", "www",
    }
)  # fmt: skip


def is_reserved(slug: str) -> bool:
    return slug in RESERVED_SLUGS


def slug_candidates(base: str, attempts: int = 20):
    """Gera 'base', 'base-2', 'base-3'... para contornar slugs já usados."""
    if not is_reserved(base):
        yield base
    for n in range(2, attempts + 2):
        yield f"{base}-{n}"
