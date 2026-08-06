-- ============================================================================
--  Datenbank-Schema für die Hochzeitswebseite
--  ----------------------------------------------------------------------------
--  So einspielen:
--    1. supabase.com -> dein Projekt -> "SQL Editor"
--    2. Diese Datei komplett hineinkopieren
--    3. "Run" drücken
--
--  Das Skript ist wiederholbar: Du kannst es gefahrlos erneut ausführen.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Tabelle: Anmeldungen (RSVP)
--    Pro Gast-Account genau ein Eintrag.
-- ---------------------------------------------------------------------------
create table if not exists public.rsvps (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null unique references auth.users(id) on delete cascade,

  -- Wer meldet sich an
  vorname           text not null,
  nachname          text not null,
  email             text not null,
  telefon           text,

  -- Zu- oder Absage
  teilnahme         text not null check (teilnahme in ('ja', 'nein')),

  -- Begleitung
  begleitung        boolean not null default false,
  begleitung_name   text,
  kinder_anzahl     integer not null default 0 check (kinder_anzahl >= 0),
  kinder_namen      text,

  -- An welchen Tagen ist der Gast dabei
  dabei_freitag     boolean not null default false,
  dabei_samstag     boolean not null default true,
  dabei_sonntag     boolean not null default false,

  -- Übernachtung: 'hotel' = im Kloster Haydau,
  --               'woanders' = eigene Unterkunft,
  --               'keine' = reist am selben Tag ab
  uebernachtung     text not null default 'keine'
                    check (uebernachtung in ('hotel', 'woanders', 'keine')),
  uebernachtung_details text,   -- z.B. Name der anderen Unterkunft
  naechte           text,       -- z.B. "Fr–So"

  -- Essen
  essen             text not null default 'alles'
                    check (essen in ('alles', 'vegetarisch', 'vegan')),
  allergien         text,

  -- Sonstiges
  shuttle           boolean not null default false,
  lied_wunsch       text,
  nachricht         text,

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- 2. Tabelle: Admins
--    Wer hier eingetragen ist, sieht den Admin-Bereich.
-- ---------------------------------------------------------------------------
create table if not exists public.admins (
  email      text primary key,
  created_at timestamptz not null default now()
);

-- >>> HIER deine E-Mail-Adresse(n) eintragen <<<
insert into public.admins (email) values
  ('benedictreith@gmail.com')
on conflict (email) do nothing;

-- ---------------------------------------------------------------------------
-- 3. Hilfsfunktion: Ist der eingeloggte Nutzer Admin?
-- ---------------------------------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.admins
    where lower(email) = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

-- ---------------------------------------------------------------------------
-- 4. updated_at automatisch pflegen
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists rsvps_updated_at on public.rsvps;
create trigger rsvps_updated_at
  before update on public.rsvps
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- 5. Row Level Security
--    Gäste sehen und ändern nur ihre eigene Anmeldung.
--    Admins sehen alle.
-- ---------------------------------------------------------------------------
alter table public.rsvps  enable row level security;
alter table public.admins enable row level security;

drop policy if exists "eigene anmeldung lesen"    on public.rsvps;
drop policy if exists "eigene anmeldung anlegen"  on public.rsvps;
drop policy if exists "eigene anmeldung aendern"  on public.rsvps;
drop policy if exists "admin liest alle"          on public.rsvps;

create policy "eigene anmeldung lesen"
  on public.rsvps for select
  using (auth.uid() = user_id);

create policy "eigene anmeldung anlegen"
  on public.rsvps for insert
  with check (auth.uid() = user_id);

create policy "eigene anmeldung aendern"
  on public.rsvps for update
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "admin liest alle"
  on public.rsvps for select
  using (public.is_admin());

-- Die admins-Tabelle darf niemand über die API lesen oder ändern.
-- Nur die Funktion is_admin() (security definer) greift darauf zu.
-- Es gibt daher bewusst keine Policy für public.admins.

-- ---------------------------------------------------------------------------
-- 6. Index für die Admin-Übersicht
-- ---------------------------------------------------------------------------
create index if not exists rsvps_teilnahme_idx     on public.rsvps (teilnahme);
create index if not exists rsvps_uebernachtung_idx on public.rsvps (uebernachtung);
