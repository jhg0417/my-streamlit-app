-- Run once in Supabase SQL Editor. The service_role key is SERVER-ONLY.
-- No anon/authenticated policies: public users may not access this table directly.
create table if not exists public.app_state (
    id text primary key,
    version integer not null default 1,
    data jsonb not null default '{}'::jsonb
);
alter table public.app_state enable row level security;
