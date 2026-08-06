# Hochzeitswebseite Anna & Benedict

Webseite zur Hochzeit am 7. August 2027 im Hotel Kloster Haydau, Morschen.

**Was drin ist:** Ablauf, Location, Anfahrt mit Karte, Übernachtung, Dresscode
mit Beispielbildern, Fotogalerie (nach der Hochzeit), FAQ, Geschenke — sowie ein
Gäste-Login mit Bestätigungsmail, ein Anmeldeformular und ein Admin-Bereich, in
dem ihr seht, wer zu- und abgesagt hat und wer wo übernachtet. Eure vollständige
Gästeliste könnt ihr importieren — Anmeldungen werden automatisch dem passenden
Eintrag zugeordnet, Unklares ordnet ihr per Klick von Hand zu.

---

## Inhalt

1. [Wo hoste ich das? (Kurzantwort)](#1-wo-hoste-ich-das)
2. [Einrichtung in 20 Minuten](#2-einrichtung-in-20-minuten)
3. [Inhalte ändern](#3-inhalte-ändern)
4. [Bilder einfügen](#4-bilder-einfügen)
5. [Fotos nach der Hochzeit freischalten](#5-fotos-nach-der-hochzeit-freischalten)
6. [Admin-Bereich](#6-admin-bereich)
7. [Gästeliste](#7-gästeliste)
8. [Lokal entwickeln](#8-lokal-entwickeln)
9. [Kosten](#9-kosten)

---

## 1. Wo hoste ich das?

**Empfehlung: Vercel + Supabase. Beides kostenlos, beides ohne Server-Wartung.**

| Baustein | Dienst | Wofür | Kosten |
|---|---|---|---|
| Webseite | **Vercel** | Hosting, HTTPS, weltweit schnell | 0 € (Hobby-Tarif) |
| Login + Datenbank + Bestätigungsmails | **Supabase** | Gäste-Accounts, Anmeldungen | 0 € (Free-Tarif) |
| Domain | z.B. **Namecheap**, **INWX**, **Strato** | z.B. `anna-und-benedict.de` | ca. 10 €/Jahr |

Warum diese Kombination:

- **Bestätigungsmails sind schon eingebaut.** Supabase verschickt die
  "Bitte E-Mail bestätigen"-Mail selbst — du musst keinen Mailserver einrichten.
- **Kein Server, den jemand pflegen muss.** Kein Update, kein Backup-Skript.
  Für 75 Gäste liegt ihr weit unter allen Free-Tarif-Grenzen.
- **Änderungen gehen automatisch live.** Du änderst eine Textdatei auf GitHub,
  eine Minute später ist es online.

Alternativen, die ich *nicht* empfehle: WordPress (Wartung, Sicherheitsupdates,
teurer), reine Baukästen wie Wix (Admin-Auswertung so nicht baubar), eigener
Server (viel Arbeit für ein Wochenende).

---

## 2. Einrichtung in 20 Minuten

### Schritt 1: Supabase-Projekt anlegen

1. Auf [supabase.com](https://supabase.com) mit GitHub anmelden → **New project**
2. Name z.B. `hochzeit`, Region **Frankfurt (eu-central-1)**, Passwort vergeben
3. Warten, bis das Projekt bereit ist (ca. 2 Minuten)

### Schritt 2: Datenbank einrichten

1. Links im Menü auf **SQL Editor** → **New query**
2. Den kompletten Inhalt der Datei [`supabase/schema.sql`](supabase/schema.sql)
   hineinkopieren
3. **Run** drücken

Damit sind die Tabellen, die Zugriffsrechte und dein Admin-Zugang angelegt.

### Schritt 3: Mail-Einstellungen prüfen

Unter **Authentication → Sign In / Providers → Email**:

- **Confirm email** muss **an** sein (das ist die Bestätigungsmail)
- Unter **Authentication → URL Configuration**:
  - *Site URL*: später die echte Adresse, z.B. `https://anna-und-benedict.de`
  - *Redirect URLs*: `https://anna-und-benedict.de/auth/callback` eintragen
    (und für lokales Testen zusätzlich `http://localhost:3000/auth/callback`)

> **Wichtig:** Der eingebaute Mailversand von Supabase ist auf wenige Mails pro
> Stunde begrenzt. Für 75 Gäste, die sich über Wochen verteilt anmelden, reicht
> das. Wenn sich alle am selben Abend anmelden, kann es klemmen. Sicherer ist es,
> unter **Project Settings → Authentication → SMTP Settings** einen eigenen
> Absender zu hinterlegen — z.B. [Resend](https://resend.com) (kostenlos bis
> 3.000 Mails/Monat) oder Brevo. Dauert 10 Minuten und die Mails landen
> seltener im Spam.

Die Texte der Mails kannst du unter **Authentication → Emails** auf Deutsch
umschreiben.

### Schritt 4: Bei Vercel veröffentlichen

1. Auf [vercel.com](https://vercel.com) mit GitHub anmelden
2. **Add New → Project** → dieses Repository auswählen → **Import**
3. Unter **Environment Variables** zwei Werte eintragen (findest du in Supabase
   unter **Project Settings → API**):

   | Name | Wert |
   |---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | `https://xxxx.supabase.co` |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | der lange `eyJ...`-Schlüssel („anon public") |

4. **Deploy** drücken

Nach ein bis zwei Minuten ist die Seite unter einer `*.vercel.app`-Adresse
erreichbar.

### Schritt 5: Eigene Domain (optional)

Domain bei einem Anbieter kaufen, dann in Vercel unter **Settings → Domains**
eintragen. Vercel zeigt dir genau, welche DNS-Einträge du setzen musst. Danach
nicht vergessen, die *Site URL* in Supabase (Schritt 3) auf die neue Adresse zu
ändern.

---

## 3. Inhalte ändern

**Alle Texte stehen in einer einzigen Datei:
[`content/hochzeit.ts`](content/hochzeit.ts)**

Du kannst sie direkt auf GitHub im Browser bearbeiten (Stift-Symbol oben rechts
in der Datei) — dann baut Vercel die Seite automatisch neu.

Die Datei ist in nummerierte Abschnitte gegliedert:

| Abschnitt | Was du dort änderst |
|---|---|
| 1. Grunddaten | Namen, Datum, Deadline, Kontakt |
| 2. Begrüßung | Text auf der Startseite, Hintergrundbild |
| 3. Ablauf | Tage und Programmpunkte |
| 4. Location | Beschreibung, Highlights, Adresse |
| 5. Anfahrt | Auto, Bahn, Flugzeug |
| 6. Übernachtung | Zimmerpreise, Buchungsstichwort |
| 7. Dresscode | Text, Farben, Beispielbilder |
| 8. Geschenke | Text, Wunschlisten-Link |
| 9. FAQ | Fragen und Antworten |
| 10. Fotos | Galerie nach der Hochzeit |
| 11. Admin | Wer den Admin-Bereich sehen darf |

**Regeln beim Bearbeiten:** Ändere nur den Text zwischen den `"`
Anführungszeichen. Kommas, geschweifte Klammern `{}` und eckige Klammern `[]`
bitte stehen lassen. Neue Einträge (z.B. eine weitere FAQ-Frage) legst du an,
indem du einen bestehenden Block kopierst und den Text austauschst.

**Farben und Schrift** änderst du in [`app/globals.css`](app/globals.css) ganz
oben im Block `@theme`.

---

## 4. Bilder einfügen

Bilder gehören in den Ordner `public/`. Dann trägst du den Pfad in
`content/hochzeit.ts` ein — **ohne** das `public`:

| Datei liegt unter | Du trägst ein |
|---|---|
| `public/hero.jpg` | `"/hero.jpg"` |
| `public/dresscode/damen-1.jpg` | `"/dresscode/damen-1.jpg"` |
| `public/location/orangerie.jpg` | `"/location/orangerie.jpg"` |

Beispiel Dresscode:

```ts
beispiele: [
  { datei: "/dresscode/damen-1.jpg", alt: "Langes Kleid in Salbeigrün", label: "Damen: langes Kleid" },
  ...
],
```

Solange kein Bild eingetragen ist, zeigt die Seite ein dezentes Platzhalterfeld —
sie sieht also auch ohne Bilder fertig aus.

> Tipp: Bilder vorher auf ca. 1600 px Breite verkleinern (z.B. mit
> [squoosh.app](https://squoosh.app)), sonst lädt die Seite auf dem Handy langsam.

---

## 5. Fotos nach der Hochzeit freischalten

In `content/hochzeit.ts`, Abschnitt 10:

```ts
fotos: {
  freigeschaltet: true,                          // von false auf true
  galerieUrl: "https://fotograf.de/anna-benedict",  // Link vom Fotografen
  galeriePasswort: "haydau2027",                 // falls es eins gibt
  bilder: [],
},
```

Wenn du die Bilder lieber selbst hosten willst, leg sie in `public/fotos/` ab und
trage sie unter `bilder` ein:

```ts
bilder: [
  { datei: "/fotos/001.jpg", alt: "Trauung in der Klosterkirche" },
  { datei: "/fotos/002.jpg", alt: "Sektempfang im Innenhof" },
],
```

---

## 6. Admin-Bereich

Erreichbar unter `/admin`, sichtbar nur für die E-Mail-Adressen, die an **zwei**
Stellen eingetragen sind:

1. `content/hochzeit.ts` → `adminEmails` (steuert die Anzeige)
2. Supabase-Tabelle `admins` → über den SQL Editor (steuert den Datenzugriff)

```sql
insert into public.admins (email) values ('anna@beispiel.de');
```

Beide Stellen sind nötig: die erste blendet den Menüpunkt ein, die zweite gibt
die Daten in der Datenbank frei. Auch wenn jemand die erste umgeht, kommt er
ohne die zweite an keine Gästedaten.

**Was du dort siehst:**

- Stand der Einladungen: wie viele der Eingeladenen schon geantwortet haben
- Zusagen, Absagen, Personen gesamt, Kinder
- Wer im Kloster Haydau schläft, wer woanders, wer gar nicht
- Erwartete Personen pro Tag (Freitag / Samstag / Sonntag)
- Vegetarier, Veganer, Allergien, Shuttle-Bedarf
- Alle Rückmeldungen mit Suche, Filtern und **CSV-Export** — den kannst du in
  Excel öffnen und dem Hotel schicken
- Einen Hinweis, wenn eine Anmeldung zu keinem Eintrag der Gästeliste passt

**Datenschutz:** Gäste sehen ausschließlich ihre eigene Anmeldung, niemals die
der anderen. Das ist direkt in der Datenbank per Row Level Security abgesichert,
nicht nur in der Oberfläche.

---

## 7. Gästeliste

Unter **`/admin/gaeste`** pflegst du die Liste aller Eingeladenen. Damit siehst
du nicht nur, wer geantwortet hat, sondern vor allem: **wer noch nicht.**

### Liste importieren

Reiter **„Liste importieren"**. Du kannst direkt aus Excel oder Google Sheets
kopieren und ins Textfeld einfügen — Semikolon, Tab und Komma werden alle
erkannt.

```
Vorname;Nachname;E-Mail;Gruppe;Seite;Notiz
Lisa;Müller;lisa.mueller@web.de;Familie Müller;Braut;
Tom;Müller;;Familie Müller;Braut;Sohn von Lisa
Jan;Schneider;jan@beispiel.de;;Bräutigam;Trauzeuge
```

Nur **Vorname** und **Nachname** sind Pflicht. Eine Kopfzeile darf drin bleiben.
Bevor du auf „Importieren" drückst, zeigt dir die Vorschau rechts, was neu
angelegt wird und was übersprungen wird — **bereits vorhandene Namen werden
nicht doppelt angelegt.** Du kannst den Import also gefahrlos wiederholen, wenn
die Liste wächst.

Einzelne Gäste kannst du auch direkt in der Oberfläche hinzufügen, bearbeiten
und löschen.

### Wie die Zuordnung funktioniert

Meldet sich jemand auf der Webseite an, sucht das System automatisch den
passenden Eintrag — in dieser Reihenfolge:

1. **Über die E-Mail-Adresse.** Passt die Adresse aus der Anmeldung zu einer
   Adresse auf der Gästeliste, ist die Sache klar.
2. **Über Vor- und Nachname.** Groß-/Kleinschreibung, Umlaute und „ß" spielen
   dabei keine Rolle: „SOREN strauss" findet „Sören Strauß".
3. **Bleibt es unklar** — kein Treffer oder mehrere gleiche Namen —, passiert
   nichts Automatisches. Die Anmeldung landet im Reiter **„Noch zuzuordnen"**.

Ein Eintrag der Gästeliste wird nie zweimal vergeben. Und eine von Hand
gesetzte Zuordnung wird nie automatisch überschrieben.

### Von Hand zuordnen

Reiter **„Noch zuzuordnen"**: Zu jeder offenen Anmeldung wählst du den
passenden Eintrag aus. Gäste mit gleichem Nachnamen stehen in der Auswahl ganz
oben. Steht jemand gar nicht auf der Liste (kurzfristige Einladung), legst du
den Eintrag zuerst unter „Gästeliste" an.

Hast du die Gästeliste nachträglich ergänzt, drück oben rechts auf
**„Zuordnung neu prüfen"** — dann werden alle offenen Anmeldungen noch einmal
gegen die aktualisierte Liste geprüft.

### Nachfassen

Im Reiter „Gästeliste" auf **„Ohne Antwort"** filtern und dann auf
**„Nachfassen"** drücken: Dein Mailprogramm öffnet sich mit allen Adressen im
BCC, die noch nicht geantwortet haben. (Nur für Gäste, bei denen eine
E-Mail-Adresse hinterlegt ist.)

### Muss jemand auf der Liste stehen, um sich anzumelden?

Nein. Jeder mit dem Link kann sich anmelden — die Gästeliste ist eine
Auswertungshilfe, keine Zugangssperre. Das ist Absicht: sonst käme ein Gast
nicht durch, nur weil er eine andere Mailadresse benutzt als erwartet. Wer
nicht auf der Liste steht, fällt dir im Admin-Bereich sofort auf.

---

## 8. Lokal anschauen

### Ohne alles — nur mal draufgucken

Du brauchst dafür **kein** Supabase und **kein** Vercel. Einmal
[Node.js](https://nodejs.org) installieren (die LTS-Version), dann im
Projektordner:

```bash
npm install
npm run dev
```

Die Seite läuft dann auf **http://localhost:3000**.

Ohne Zugangsdaten startet sie im **Vorschau-Modus**: Alle Inhalte — Startseite,
Ablauf, Location, Anfahrt, Übernachtung, Dresscode, Fotos, Geschenke, FAQ —
funktionieren ganz normal. Nur Login, Anmeldeformular und Admin-Bereich zeigen
statt eines Fehlers einen Hinweis. Oben läuft ein schmaler Balken mit, der dich
daran erinnert.

Genau so kannst du in Ruhe `content/hochzeit.ts` durchgehen, Texte umschreiben
und Bilder einsetzen. Während `npm run dev` läuft, aktualisiert sich der Browser
bei jedem Speichern automatisch.

Beenden: `Strg + C` im Terminal.

### Mit Datenbank, um Anmeldung und Admin zu testen

Sobald du das Supabase-Projekt hast (Schritt 1 bis 3 oben):

```bash
cp .env.example .env.local      # danach die beiden Werte eintragen
npm run dev
```

Vergiss nicht, in Supabase unter **Authentication → URL Configuration** die
Adresse `http://localhost:3000/auth/callback` als Redirect-URL zu ergänzen,
sonst funktionieren die Bestätigungslinks lokal nicht.

> Tipp: Leg dir dort ruhig ein zweites Supabase-Projekt als Spielwiese an. Dann
> kannst du Testgäste anlegen und wieder löschen, ohne dass es die echten Daten
> berührt.

---

## 9. Kosten

| Posten | Kosten |
|---|---|
| Vercel Hobby | 0 € |
| Supabase Free | 0 € |
| Resend (optional, für Mails) | 0 € bis 3.000 Mails/Monat |
| Domain | ca. 10 €/Jahr |

**Gesamt: rund 10 € im Jahr.**

Supabase pausiert Free-Projekte nach einer Woche ohne Zugriffe. Das Projekt
wacht beim nächsten Aufruf automatisch wieder auf (dauert ein paar Sekunden).
Wenn euch das im Monat vor der Hochzeit stört, könnt ihr für 25 $/Monat auf den
Pro-Tarif wechseln und danach wieder zurück.

---

## Technik

Next.js 15 (App Router) · React 19 · Tailwind CSS 4 · Supabase (Auth + Postgres)
