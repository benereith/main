\set ON_ERROR_STOP on
\pset pager off

-- ============ Testdaten: Gästeliste ============
insert into public.gaeste (vorname, nachname, email, gruppe) values
  ('Lisa',   'Müller',    'lisa.mueller@web.de', 'Familie Müller'),
  ('Tom',    'Müller',    null,                  'Familie Müller'),
  ('Jan',    'Schneider', 'jan@beispiel.de',     null),
  ('Anna',   'Schmidt',   null,                  'Kollegen'),
  ('Anna',   'Schmidt',   null,                  'Uni'),        -- doppelter Name!
  ('Sören',  'Strauß',    null,                  null);

-- Nutzer anlegen
insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'lisa.mueller@web.de'),
  ('22222222-2222-2222-2222-222222222222', 'tom.mueller@gmx.de'),
  ('33333333-3333-3333-3333-333333333333', 'anna.s@web.de'),
  ('44444444-4444-4444-4444-444444444444', 'soeren@web.de'),
  ('55555555-5555-5555-5555-555555555555', 'fremd@web.de'),
  ('66666666-6666-6666-6666-666666666666', 'anna2@web.de');

\echo '--- TEST 1: Zuordnung per E-Mail (Lisa) ---'
insert into public.rsvps (user_id, vorname, nachname, email, teilnahme)
values ('11111111-1111-1111-1111-111111111111','Lisa','Müller','lisa.mueller@web.de','ja');
select case when zuordnung_art = 'email' and gast_id = (select id from gaeste where vorname='Lisa')
       then 'OK   per E-Mail zugeordnet' else 'FEHL ' || coalesce(zuordnung_art,'null') end
from rsvps where user_id = '11111111-1111-1111-1111-111111111111';

\echo '--- TEST 2: Zuordnung per Name, andere Mailadresse (Tom) ---'
insert into public.rsvps (user_id, vorname, nachname, email, teilnahme)
values ('22222222-2222-2222-2222-222222222222','Tom','Müller','tom.mueller@gmx.de','ja');
select case when zuordnung_art = 'name' and gast_id = (select id from gaeste where vorname='Tom')
       then 'OK   per Name zugeordnet' else 'FEHL ' || coalesce(zuordnung_art,'null') end
from rsvps where user_id = '22222222-2222-2222-2222-222222222222';

\echo '--- TEST 3: Mehrdeutiger Name bleibt offen (Anna Schmidt x2) ---'
insert into public.rsvps (user_id, vorname, nachname, email, teilnahme)
values ('33333333-3333-3333-3333-333333333333','Anna','Schmidt','anna.s@web.de','ja');
select case when gast_id is null and zuordnung_art is null
       then 'OK   bleibt offen' else 'FEHL zugeordnet obwohl mehrdeutig' end
from rsvps where user_id = '33333333-3333-3333-3333-333333333333';

\echo '--- TEST 4: Umlaute und ss (Soeren Strauss -> Sören Strauß) ---'
insert into public.rsvps (user_id, vorname, nachname, email, teilnahme)
values ('44444444-4444-4444-4444-444444444444','SOREN','strauss','soeren@web.de','ja');
select case when gast_id = (select id from gaeste where vorname='Sören')
       then 'OK   Umlaut/ss normalisiert' else 'FEHL ' || coalesce(zuordnung_art,'null') end
from rsvps where user_id = '44444444-4444-4444-4444-444444444444';

\echo '--- TEST 5: Gar nicht auf der Liste bleibt offen ---'
insert into public.rsvps (user_id, vorname, nachname, email, teilnahme)
values ('55555555-5555-5555-5555-555555555555','Peter','Unbekannt','fremd@web.de','ja');
select case when gast_id is null then 'OK   bleibt offen' else 'FEHL zugeordnet' end
from rsvps where user_id = '55555555-5555-5555-5555-555555555555';

\echo '--- TEST 6: Manuelle Zuordnung wird als manuell markiert ---'
update public.rsvps
   set gast_id = (select id from gaeste where vorname='Anna' and gruppe='Uni')
 where user_id = '33333333-3333-3333-3333-333333333333';
select case when zuordnung_art = 'manuell' then 'OK   als manuell markiert'
            else 'FEHL ' || coalesce(zuordnung_art,'null') end
from rsvps where user_id = '33333333-3333-3333-3333-333333333333';

\echo '--- TEST 7: Manuelle Zuordnung ueberlebt spaetere Aenderungen ---'
update public.rsvps set essen = 'vegan'
 where user_id = '33333333-3333-3333-3333-333333333333';
select case when gast_id is not null and zuordnung_art = 'manuell'
       then 'OK   Zuordnung bleibt erhalten' else 'FEHL Zuordnung verloren' end
from rsvps where user_id = '33333333-3333-3333-3333-333333333333';

\echo '--- TEST 8: Bereits vergebener Eintrag wird nicht doppelt vergeben ---'
insert into public.rsvps (user_id, vorname, nachname, email, teilnahme)
values ('66666666-6666-6666-6666-666666666666','Anna','Schmidt','anna2@web.de','ja');
-- Erwartet: die erste Anna wurde von Hand der Uni-Anna zugeordnet, damit ist
-- nur noch die Kollegen-Anna frei -> eindeutiger Treffer, Zuordnung erlaubt.
-- Wichtig ist nur, dass NICHT derselbe Eintrag zweimal vergeben wird.
select case when gast_id = (select id from gaeste where vorname='Anna' and gruppe='Kollegen')
            then 'OK   freier Eintrag vergeben, nicht doppelt'
            when gast_id is null then 'OK   bleibt offen'
            else 'FEHL doppelt vergeben' end
from rsvps where user_id = '66666666-6666-6666-6666-666666666666';
select case when count(*) = count(distinct gast_id) then 'OK   keine doppelten Zuordnungen'
            else 'FEHL doppelte Zuordnung' end
from rsvps where gast_id is not null;

\echo '--- TEST 9: Nachtraegliche Pruefung nach Ergaenzung der Liste ---'
insert into public.gaeste (vorname, nachname) values ('Peter','Unbekannt');
begin;
set local test.email = 'benedictreith@gmail.com';
select case when public.zuordnung_neu_pruefen() = 1
       then 'OK   1 Anmeldung nachtraeglich zugeordnet'
       else 'FEHL falsche Anzahl' end;
commit;

\echo '--- TEST 9b: Nicht-Admin darf die Pruefung nicht ausloesen ---'
begin;
set local test.email = 'gast@web.de';
savepoint s1;
do $$ begin
  perform public.zuordnung_neu_pruefen();
  raise notice 'FEHL Gast durfte pruefen';
exception when others then
  raise notice 'OK   Gast wurde abgewiesen';
end $$;
rollback;
select case when gast_id is not null then 'OK   Peter jetzt zugeordnet' else 'FEHL' end
from rsvps where user_id = '55555555-5555-5555-5555-555555555555';

\echo '--- TEST 10: Loeschen eines Gastes loest die Zuordnung, loescht keine Anmeldung ---'
delete from public.gaeste where vorname = 'Lisa';
select case when count(*) = 1 and max(coalesce(gast_id::text,'-')) = '-'
       then 'OK   Anmeldung bleibt, Zuordnung geloest' else 'FEHL' end
from rsvps where user_id = '11111111-1111-1111-1111-111111111111';

\echo '--- TEST 11: is_admin() ---'
begin;
set local test.email = 'benedictreith@gmail.com';
select case when public.is_admin() then 'OK   Admin erkannt' else 'FEHL' end;
commit;
begin;
set local test.email = 'gast@web.de';
select case when not public.is_admin() then 'OK   Gast ist kein Admin' else 'FEHL' end;
commit;
