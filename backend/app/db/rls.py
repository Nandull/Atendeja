"""SQL reutilizável de Row-Level Security para as migrações.

Toda tabela nova que tenha `tenant_id` deve chamar `enable_tenant_rls`
na sua migração. É isso que garante o isolamento entre estabelecimentos
dentro do próprio banco.
"""

CREATE_HELPERS = """
CREATE OR REPLACE FUNCTION app_current_tenant() RETURNS uuid
LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION app_current_user() RETURNS uuid
LANGUAGE sql STABLE AS
$$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;
"""

DROP_HELPERS = """
DROP FUNCTION IF EXISTS app_current_user();
DROP FUNCTION IF EXISTS app_current_tenant();
"""


def enable_tenant_rls(table: str, column: str = "tenant_id") -> str:
    """Liga o RLS e cria a política padrão: só linhas do tenant atual.

    FORCE faz a regra valer inclusive para o dono da tabela (o usuário da API).
    """
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
    USING ({column} = app_current_tenant())
    WITH CHECK ({column} = app_current_tenant());
"""
