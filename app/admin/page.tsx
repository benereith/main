import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { hochzeit } from "@/content/hochzeit";
import AdminTabelle, { type RsvpZeile } from "@/components/AdminTabelle";

export const dynamic = "force-dynamic";

export default async function AdminSeite() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login?weiter=/admin");

  const istAdmin = hochzeit.adminEmails
    .map((e) => e.toLowerCase())
    .includes((user.email ?? "").toLowerCase());

  if (!istAdmin) {
    return (
      <div className="container-seite flex min-h-[70vh] items-center justify-center">
        <div className="karte max-w-md text-center">
          <h1 className="font-display text-2xl">Kein Zugriff</h1>
          <p className="mt-3 text-grau">
            Dieser Bereich ist nur für das Brautpaar.
          </p>
          <Link href="/" className="btn btn-rand mt-6">
            Zur Startseite
          </Link>
        </div>
      </div>
    );
  }

  const [{ data, error }, { data: gaesteliste }] = await Promise.all([
    supabase.from("rsvps").select("*").order("created_at", { ascending: false }),
    supabase.from("gaeste").select("id, vorname, nachname"),
  ]);

  const zeilen = (data ?? []) as RsvpZeile[];
  const eingeladen = gaesteliste?.length ?? 0;
  const nichtZugeordnet = zeilen.filter((r) => !r.gast_id).length;
  const ohneAntwort = Math.max(
    0,
    eingeladen - zeilen.filter((r) => r.gast_id).length,
  );

  const gastNamen = new Map(
    (gaesteliste ?? []).map((g) => [g.id, `${g.vorname} ${g.nachname}`]),
  );

  // ---- Auswertung ----
  const zusagen = zeilen.filter((r) => r.teilnahme === "ja");
  const absagen = zeilen.filter((r) => r.teilnahme === "nein");

  const personen = zusagen.reduce(
    (s, r) => s + 1 + (r.begleitung ? 1 : 0) + (r.kinder_anzahl ?? 0),
    0,
  );
  const kinder = zusagen.reduce((s, r) => s + (r.kinder_anzahl ?? 0), 0);

  const zaehle = (fn: (r: RsvpZeile) => boolean) =>
    zusagen.filter(fn).reduce(
      (s, r) => s + 1 + (r.begleitung ? 1 : 0) + (r.kinder_anzahl ?? 0),
      0,
    );

  const imHotel = zaehle((r) => r.uebernachtung === "hotel");
  const woanders = zaehle((r) => r.uebernachtung === "woanders");
  const keineUebernachtung = zaehle((r) => r.uebernachtung === "keine");

  const freitag = zaehle((r) => r.dabei_freitag);
  const samstag = zaehle((r) => r.dabei_samstag);
  const sonntag = zaehle((r) => r.dabei_sonntag);

  const vegetarisch = zusagen.filter((r) => r.essen === "vegetarisch").length;
  const vegan = zusagen.filter((r) => r.essen === "vegan").length;
  const mitAllergien = zusagen.filter((r) => r.allergien?.trim()).length;
  const shuttle = zusagen.filter((r) => r.shuttle).length;

  const kacheln = [
    { label: "Zusagen (Haushalte)", wert: zusagen.length, ton: "gruen" },
    { label: "Absagen", wert: absagen.length, ton: "rosa" },
    { label: "Personen gesamt", wert: personen, ton: "gold" },
    { label: "davon Kinder", wert: kinder, ton: "grau" },
  ] as const;

  return (
    <div className="container-seite py-14">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="kicker">Nur für euch beide</p>
          <h1 className="ueberschrift mt-2">Übersicht</h1>
          <p className="mt-2 text-grau">
            {zeilen.length} Rückmeldungen · Deadline {hochzeit.rsvpDeadline}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/admin/gaeste" className="btn btn-primar !py-2 !text-sm">
            Gästeliste
          </Link>
          <Link href="/" className="btn btn-rand !py-2 !text-sm">
            Zur Webseite
          </Link>
        </div>
      </header>

      {eingeladen > 0 && (
        <div className="mt-8 flex flex-wrap items-center justify-between gap-4 rounded-xl bg-sand/50 p-5">
          <div>
            <p className="text-sm text-grau">Stand der Einladungen</p>
            <p className="mt-1 font-display text-2xl">
              {eingeladen - ohneAntwort} von {eingeladen} haben geantwortet
            </p>
            {ohneAntwort > 0 && (
              <p className="mt-1 text-sm text-grau">
                {ohneAntwort} Eingeladene fehlen noch.
              </p>
            )}
          </div>
          <div className="h-2 min-w-48 flex-1 overflow-hidden rounded-full bg-white">
            <div
              className="h-full rounded-full bg-salbei-dunkel transition-all"
              style={{
                width: `${Math.round(((eingeladen - ohneAntwort) / eingeladen) * 100)}%`,
              }}
            />
          </div>
          <Link href="/admin/gaeste" className="btn btn-rand !py-2 !text-sm">
            Wer fehlt noch?
          </Link>
        </div>
      )}

      {nichtZugeordnet > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-gold/15 p-4">
          <p className="text-sm">
            <strong>{nichtZugeordnet}</strong> Anmeldung(en) hängen an keinem
            Eintrag der Gästeliste.
          </p>
          <Link href="/admin/gaeste" className="btn btn-rand !py-1.5 !text-sm">
            Von Hand zuordnen
          </Link>
        </div>
      )}

      {error && (
        <p className="mt-8 rounded-lg bg-altrosa/20 p-4 text-sm">
          Die Daten konnten nicht geladen werden: {error.message}
          <br />
          Prüfe, ob das Schema aus <code>supabase/schema.sql</code> eingespielt
          und deine E-Mail in der Tabelle <code>admins</code> eingetragen ist.
        </p>
      )}

      {/* Kennzahlen */}
      <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kacheln.map((k) => (
          <div key={k.label} className="karte">
            <p className="text-sm text-grau">{k.label}</p>
            <p
              className={`mt-1 font-display text-4xl ${
                k.ton === "gruen"
                  ? "text-salbei-dunkel"
                  : k.ton === "rosa"
                    ? "text-altrosa"
                    : k.ton === "gold"
                      ? "text-gold"
                      : ""
              }`}
            >
              {k.wert}
            </p>
          </div>
        ))}
      </div>

      {/* Detailauswertung */}
      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="karte">
          <h2 className="font-display text-xl">Übernachtung</h2>
          <p className="mt-1 text-sm text-grau">Personen, nicht Zimmer.</p>
          <ul className="mt-4 divide-y divide-sand">
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Im Kloster Haydau</span>
              <strong>{imHotel}</strong>
            </li>
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Woanders</span>
              <strong>{woanders}</strong>
            </li>
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Übernachtet nicht</span>
              <strong>{keineUebernachtung}</strong>
            </li>
          </ul>
        </div>

        <div className="karte">
          <h2 className="font-display text-xl">Pro Tag</h2>
          <p className="mt-1 text-sm text-grau">Erwartete Personen.</p>
          <ul className="mt-4 divide-y divide-sand">
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Freitag (Get-together)</span>
              <strong>{freitag}</strong>
            </li>
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Samstag (Hochzeit)</span>
              <strong>{samstag}</strong>
            </li>
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Sonntag (Frühstück)</span>
              <strong>{sonntag}</strong>
            </li>
          </ul>
        </div>

        <div className="karte">
          <h2 className="font-display text-xl">Küche & Logistik</h2>
          <p className="mt-1 text-sm text-grau">Für die Absprache mit dem Hotel.</p>
          <ul className="mt-4 divide-y divide-sand">
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Vegetarisch</span>
              <strong>{vegetarisch}</strong>
            </li>
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Vegan</span>
              <strong>{vegan}</strong>
            </li>
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Mit Allergien</span>
              <strong>{mitAllergien}</strong>
            </li>
            <li className="flex justify-between py-2.5">
              <span className="text-grau">Shuttle gewünscht</span>
              <strong>{shuttle}</strong>
            </li>
          </ul>
        </div>
      </div>

      {/* Gästeliste */}
      <div className="mt-10">
        <AdminTabelle zeilen={zeilen} gastNamen={Object.fromEntries(gastNamen)} />
      </div>
    </div>
  );
}
