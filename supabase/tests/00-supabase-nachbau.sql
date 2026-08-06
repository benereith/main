-- Minimaler Supabase-Nachbau, damit schema.sql unverändert laufen kann.
create schema if not exists auth;
create table if not exists auth.users (
  id uuid primary key default gen_random_uuid(),
  email text
);
create or replace function auth.uid() returns uuid language sql stable as
$$ select nullif(current_setting('test.uid', true), '')::uuid $$;
create or replace function auth.jwt() returns jsonb language sql stable as
$$ select jsonb_build_object('email', current_setting('test.email', true)) $$;
