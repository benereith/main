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

-- Admins dürfen die Zuordnung zur Gästeliste nachträglich korrigieren.
create policy "admin aendert alle"
  on public.rsvps for update
  using (public.is_admin())
  with check (public.is_admin());

-- Die admins-Tabelle darf niemand über die API lesen oder ändern.
-- Nur die Funktion is_admin() (security definer) greift darauf zu.
-- Es gibt daher bewusst keine Policy für public.admins.

-- ---------------------------------------------------------------------------
-- 6. Index für die Admin-Übersicht
-- ---------------------------------------------------------------------------
create index if not exists rsvps_teilnahme_idx     on public.rsvps (teilnahme);
create index if not exists rsvps_uebernachtung_idx on public.rsvps (uebernachtung);


-- ###########################################################################
--  GÄSTELISTE
--  Die Liste aller eingeladenen Personen. Wer sich auf der Webseite anmeldet,
--  wird automatisch einem Eintrag zugeordnet — per E-Mail-Adresse oder,
--  wenn die nicht passt, per Vor- und Nachname. Bleibt es unklar (kein oder
--  mehrere Treffer), ordnet ihr im Admin-Bereich von Hand zu.
-- ###########################################################################

-- ---------------------------------------------------------------------------
-- 7. Tabelle: eingeladene Gäste
-- ---------------------------------------------------------------------------
create table if not exists public.gaeste (
  id          uuid primary key default gen_random_uuid(),
  vorname     text not null,
  nachname    text not null,
  -- Erwartete E-Mail-Adresse, falls bekannt. Macht die Zuordnung eindeutig.
  email       text,
  -- Haushalt / Familie, z.B. "Familie Müller" — nur zur Gruppierung.
  gruppe      text,
  -- Freie Einordnung, z.B. "Braut", "Bräutigam", "Freunde", "Kollegen"
  seite       text,
  notiz       text,
  created_at  timestamptz not null default now()
);

create index if not exists gaeste_nachname_idx on public.gaeste (nachname);
create index if not exists gaeste_gruppe_idx   on public.gaeste (gruppe);

-- ---------------------------------------------------------------------------
-- 8. Verbindung Anmeldung -> Gästeliste
-- ---------------------------------------------------------------------------
alter table public.rsvps
  add column if not exists gast_id uuid
    references public.gaeste(id) on delete set null;

-- Wie kam die Zuordnung zustande? 'email', 'name' oder 'manuell'.
alter table public.rsvps
  add column if not exists zuordnung_art text;

-- Ein Eintrag der Gästeliste gehört zu höchstens einer Anmeldung.
-- (NULL-Werte sind davon nicht betroffen, mehrere offene Anmeldungen sind ok.)
create unique index if not exists rsvps_gast_id_idx
  on public.rsvps (gast_id) where gast_id is not null;

-- ---------------------------------------------------------------------------
-- 9. Namen vergleichbar machen
--    "Müller" und "MUELLER" sollen als gleich gelten, "Dr. Anna " und "anna"
--    ebenfalls. Umlaute werden auf den Grundbuchstaben zurückgeführt.
-- ---------------------------------------------------------------------------
create or replace function public.norm(t text)
returns text
language sql
immutable
as $$
  select btrim(
    regexp_replace(
      lower(
        translate(
          replace(coalesce(t, ''), 'ß', 'ss'),
          'ÄÖÜäöüÀÁÂÃÈÉÊËÌÍÎÏÒÓÔÕÙÚÛÝàáâãèéêëìíîïòóôõùúûý',
          'AOUaouAAAAEEEEIIIIOOOOUUUYaaaaeeeeiiiioooouuuy'
        )
      ),
      '\s+', ' ', 'g'
    )
  );
$$;

-- ---------------------------------------------------------------------------
-- 10. Automatische Zuordnung beim Speichern einer Anmeldung
--     Reihenfolge: 1. E-Mail-Adresse  2. Vor- und Nachname
--     Nur eindeutige Treffer werden übernommen. Alles andere bleibt offen
--     und taucht im Admin-Bereich unter "Noch zuzuordnen" auf.
-- ---------------------------------------------------------------------------
create or replace function public.gast_zuordnen()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  treffer uuid[];
begin
  -- Von Hand gesetzte Zuordnung nie überschreiben.
  if new.gast_id is not null then
    if tg_op = 'INSERT' or new.gast_id is distinct from old.gast_id then
      new.zuordnung_art := 'manuell';
    end if;
    return new;
  end if;

  -- Wurde eine Zuordnung bewusst entfernt, nicht sofort neu raten.
  if tg_op = 'UPDATE' and old.gast_id is not null then
    new.zuordnung_art := null;
    return new;
  end if;

  -- 1) Über die E-Mail-Adresse
  select array_agg(g.id) into treffer
  from public.gaeste g
  where g.email is not null
    and lower(btrim(g.email)) = lower(btrim(coalesce(new.email, '')))
    and not exists (
      select 1 from public.rsvps r
      where r.gast_id = g.id and r.user_id <> new.user_id
    );

  if array_length(treffer, 1) = 1 then
    new.gast_id := treffer[1];
    new.zuordnung_art := 'email';
    return new;
  end if;

  -- 2) Über Vor- und Nachname
  select array_agg(g.id) into treffer
  from public.gaeste g
  where public.norm(g.vorname)  = public.norm(new.vorname)
    and public.norm(g.nachname) = public.norm(new.nachname)
    and not exists (
      select 1 from public.rsvps r
      where r.gast_id = g.id and r.user_id <> new.user_id
    );

  if array_length(treffer, 1) = 1 then
    new.gast_id := treffer[1];
    new.zuordnung_art := 'name';
    return new;
  end if;

  -- 3) Kein eindeutiger Treffer -> offen lassen, ihr ordnet von Hand zu.
  new.zuordnung_art := null;
  return new;
end;
$$;

drop trigger if exists rsvps_gast_zuordnen on public.rsvps;
create trigger rsvps_gast_zuordnen
  before insert or update on public.rsvps
  for each row execute function public.gast_zuordnen();

-- ---------------------------------------------------------------------------
-- 11. Nachträgliche Zuordnung, wenn die Gästeliste später ergänzt wird
--     Ruft ihr im Admin-Bereich über den Knopf "Zuordnung neu prüfen" auf.
-- ---------------------------------------------------------------------------
create or replace function public.zuordnung_neu_pruefen()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  offen   record;
  neu     integer := 0;
begin
  if not public.is_admin() then
    raise exception 'Nur Admins dürfen die Zuordnung neu prüfen.';
  end if;

  -- Bewusst Zeile für Zeile: so sieht der Trigger bei jedem Schritt die
  -- bereits vergebenen Einträge und vergibt keinen doppelt.
  for offen in select id from public.rsvps where gast_id is null loop
    update public.rsvps set updated_at = updated_at where id = offen.id;
    if found then
      select neu + (case when gast_id is null then 0 else 1 end)
        into neu
        from public.rsvps where id = offen.id;
    end if;
  end loop;

  return neu;
end;
$$;

-- ---------------------------------------------------------------------------
-- 12. Zugriffsrechte für die Gästeliste
--     Nur Admins. Gäste bekommen die Liste nie zu sehen — die automatische
--     Zuordnung läuft über den Trigger oben, der eigene Rechte mitbringt.
-- ---------------------------------------------------------------------------
alter table public.gaeste enable row level security;

drop policy if exists "admin liest gaeste"    on public.gaeste;
drop policy if exists "admin pflegt gaeste"   on public.gaeste;
drop policy if exists "admin aendert gaeste"  on public.gaeste;
drop policy if exists "admin loescht gaeste"  on public.gaeste;

create policy "admin liest gaeste"
  on public.gaeste for select using (public.is_admin());

create policy "admin pflegt gaeste"
  on public.gaeste for insert with check (public.is_admin());

create policy "admin aendert gaeste"
  on public.gaeste for update using (public.is_admin()) with check (public.is_admin());

create policy "admin loescht gaeste"
  on public.gaeste for delete using (public.is_admin());
