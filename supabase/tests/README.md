# Tests für die automatische Zuordnung

Diese Tests prüfen die Logik aus `../schema.sql`: Wird eine Anmeldung dem
richtigen Eintrag der Gästeliste zugeordnet? Bleibt Unklares offen? Überlebt
eine von Hand gesetzte Zuordnung spätere Änderungen?

**Du brauchst das im Alltag nicht.** Es ist nur relevant, wenn jemand die
Zuordnungsregeln in `schema.sql` ändert.

## Ausführen

Mit einem lokalen PostgreSQL (16 oder neuer):

```bash
createdb hochzeit_test
psql -d hochzeit_test -f supabase/tests/00-supabase-nachbau.sql
psql -d hochzeit_test -f supabase/schema.sql
psql -d hochzeit_test -tA -f supabase/tests/01-zuordnung.sql
```

Jede Zeile der Ausgabe beginnt mit `OK` oder `FEHL`. `00-supabase-nachbau.sql`
stellt nur die Teile von Supabase nach, die das Schema braucht
(`auth.users`, `auth.uid()`, `auth.jwt()`).

## Was geprüft wird

| Fall | Erwartung |
|---|---|
| Anmeldung mit bekannter E-Mail | Zuordnung per E-Mail |
| Anmeldung mit anderer E-Mail, bekanntem Namen | Zuordnung per Name |
| Name kommt zweimal auf der Liste vor | bleibt offen, manuell zuordnen |
| „SOREN strauss" vs. „Sören Strauß" | wird trotzdem erkannt |
| Person steht gar nicht auf der Liste | bleibt offen |
| Von Hand gesetzte Zuordnung | wird als `manuell` markiert |
| Gast ändert später seine Anmeldung | Zuordnung bleibt bestehen |
| Zwei Anmeldungen, ein Listeneintrag | derselbe Eintrag wird nie doppelt vergeben |
| Liste nachträglich ergänzt | „Zuordnung neu prüfen" findet den Treffer |
| Nicht-Admin ruft die Prüfung auf | wird abgewiesen |
| Eintrag aus der Liste gelöscht | Anmeldung bleibt, nur die Zuordnung löst sich |
