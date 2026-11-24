-- Executado uma vez, na primeira subida do container do Postgres.
-- A API usa um usuário comum (sem SUPERUSER e sem BYPASSRLS): é o que faz o
-- Row-Level Security valer. Superusuário ignora RLS.
CREATE ROLE atendeja LOGIN PASSWORD 'atendeja' NOSUPERUSER NOBYPASSRLS NOCREATEROLE;
CREATE DATABASE atendeja OWNER atendeja;
CREATE DATABASE atendeja_test OWNER atendeja;
