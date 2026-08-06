"use client";

import Link from "next/link";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { hochzeit } from "@/content/hochzeit";

type Rsvp = {
  vorname: string;
  nachname: string;
  email: string;
  telefon: string;
  teilnahme: "ja" | "nein";
  begleitung: boolean;
  begleitung_name: string;
  kinder_anzahl: number;
  kinder_namen: string;
  dabei_freitag: boolean;
  dabei_samstag: boolean;
  dabei_sonntag: boolean;
  uebernachtung: "hotel" | "woanders" | "keine";
  uebernachtung_details: string;
  naechte: string;
  essen: "alles" | "vegetarisch" | "vegan";
  allergien: string;
  shuttle: boolean;
  lied_wunsch: string;
  nachricht: string;
};

export default function RsvpFormular({
  userId,
  email,
  vornameVorgabe,
  nachnameVorgabe,
  vorhanden,
}: {
  userId: string;
  email: string;
  vornameVorgabe: string;
  nachnameVorgabe: string;
  vorhanden: Partial<Rsvp> | null;
}) {
  const [f, setF] = useState<Rsvp>({
    vorname: vorhanden?.vorname ?? vornameVorgabe,
    nachname: vorhanden?.nachname ?? nachnameVorgabe,
    email: vorhanden?.email ?? email,
    telefon: vorhanden?.telefon ?? "",
    teilnahme: vorhanden?.teilnahme ?? "ja",
    begleitung: vorhanden?.begleitung ?? false,
    begleitung_name: vorhanden?.begleitung_name ?? "",
    kinder_anzahl: vorhanden?.kinder_anzahl ?? 0,
    kinder_namen: vorhanden?.kinder_namen ?? "",
    dabei_freitag: vorhanden?.dabei_freitag ?? false,
    dabei_samstag: vorhanden?.dabei_samstag ?? true,
    dabei_sonntag: vorhanden?.dabei_sonntag ?? false,
    uebernachtung: vorhanden?.uebernachtung ?? "keine",
    uebernachtung_details: vorhanden?.uebernachtung_details ?? "",
    naechte: vorhanden?.naechte ?? "",
    essen: vorhanden?.essen ?? "alles",
    allergien: vorhanden?.allergien ?? "",
    shuttle: vorhanden?.shuttle ?? false,
    lied_wunsch: vorhanden?.lied_wunsch ?? "",
    nachricht: vorhanden?.nachricht ?? "",
  });

  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [gespeichert, setGespeichert] = useState(false);

  const setze = <K extends keyof Rsvp>(k: K, v: Rsvp[K]) =>
    setF((alt) => ({ ...alt, [k]: v }));

  const absenden = async (e: React.FormEvent) => {
    e.preventDefault();
    setFehler(null);
    setLaedt(true);

    const supabase = createClient();
    const { error } = await supabase.from("rsvps").upsert(
      {
        user_id: userId,
        ...f,
        // Bei einer Absage sind die Detailangaben irrelevant
        ...(f.teilnahme === "nein"
          ? {
              begleitung: false,
              kinder_anzahl: 0,
              dabei_freitag: false,
              dabei_samstag: false,
              dabei_sonntag: false,
              uebernachtung: "keine" as const,
              shuttle: false,
            }
          : {}),
      },
      { onConflict: "user_id" },
    );

    setLaedt(false);
    if (error) return setFehler(`Speichern fehlgeschlagen: ${error.message}`);

    setGespeichert(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const zusage = f.teilnahme === "ja";

  return (
    <>
      <div className="text-center">
        <p className="kicker">Schritt 2 von 2</p>
        <h1 className="ueberschrift mt-3">
          {vorhanden ? "Deine Anmeldung" : "Anmeldung"}
        </h1>
        <p className="mt-3 leading-relaxed text-grau">
          {vorhanden
            ? "Du kannst deine Angaben jederzeit ändern — bis zum " +
              hochzeit.rsvpDeadline +
              "."
            : "Sag uns kurz, ob du dabei bist. Alle Angaben lassen sich später noch ändern."}
        </p>
      </div>

      {gespeichert && (
        <div className="mt-8 rounded-xl bg-salbei/20 p-5 text-center">
          <p className="font-medium">Gespeichert — danke!</p>
          <p className="mt-1 text-sm text-grau">
            {zusage
              ? "Wir freuen uns auf dich. Du kannst diese Seite jederzeit wieder aufrufen und etwas ändern."
              : "Schade, dass es nicht klappt. Danke, dass du Bescheid gegeben hast."}
          </p>
          <Link href="/" className="btn btn-rand mt-4 !py-2 !text-sm">
            Zurück zur Startseite
          </Link>
        </div>
      )}

      <form onSubmit={absenden} className="mt-8 space-y-6">
        {/* ---------- Zu- oder Absage ---------- */}
        <fieldset className="karte">
          <legend className="font-display text-xl">Bist du dabei?</legend>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {(
              [
                { wert: "ja", titel: "Ja, ich komme!", text: "Wir freuen uns." },
                {
                  wert: "nein",
                  titel: "Leider nein",
                  text: "Schade — danke für die Rückmeldung.",
                },
              ] as const
            ).map((o) => (
              <label
                key={o.wert}
                className={`cursor-pointer rounded-xl border-2 p-4 transition-colors ${
                  f.teilnahme === o.wert
                    ? "border-salbei-dunkel bg-salbei/10"
                    : "border-sand hover:border-salbei"
                }`}
              >
                <input
                  type="radio"
                  name="teilnahme"
                  className="sr-only"
                  checked={f.teilnahme === o.wert}
                  onChange={() => setze("teilnahme", o.wert)}
                />
                <span className="block font-medium">{o.titel}</span>
                <span className="mt-0.5 block text-sm text-grau">{o.text}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {/* ---------- Kontaktdaten ---------- */}
        <fieldset className="karte">
          <legend className="font-display text-xl">Deine Daten</legend>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="vorname">
                Vorname
              </label>
              <input
                id="vorname"
                className="feld"
                required
                value={f.vorname}
                onChange={(e) => setze("vorname", e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="nachname">
                Nachname
              </label>
              <input
                id="nachname"
                className="feld"
                required
                value={f.nachname}
                onChange={(e) => setze("nachname", e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="email">
                E-Mail
              </label>
              <input
                id="email"
                type="email"
                className="feld"
                required
                value={f.email}
                onChange={(e) => setze("email", e.target.value)}
              />
            </div>
            <div>
              <label className="label" htmlFor="telefon">
                Telefon (optional)
              </label>
              <input
                id="telefon"
                type="tel"
                className="feld"
                value={f.telefon}
                onChange={(e) => setze("telefon", e.target.value)}
              />
            </div>
          </div>
        </fieldset>

        {zusage && (
          <>
            {/* ---------- Begleitung ---------- */}
            <fieldset className="karte">
              <legend className="font-display text-xl">
                Kommst du allein?
              </legend>

              <label className="mt-4 flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-[var(--color-salbei-dunkel)]"
                  checked={f.begleitung}
                  onChange={(e) => setze("begleitung", e.target.checked)}
                />
                <span>
                  <span className="font-medium">
                    Ich bringe eine Begleitung mit
                  </span>
                  <span className="block text-sm text-grau">
                    Partner:in oder Plus-eins
                  </span>
                </span>
              </label>

              {f.begleitung && (
                <div className="mt-4">
                  <label className="label" htmlFor="begleitung_name">
                    Name der Begleitung
                  </label>
                  <input
                    id="begleitung_name"
                    className="feld"
                    required
                    value={f.begleitung_name}
                    onChange={(e) => setze("begleitung_name", e.target.value)}
                  />
                </div>
              )}

              <div className="mt-5 grid gap-4 sm:grid-cols-[10rem_1fr]">
                <div>
                  <label className="label" htmlFor="kinder_anzahl">
                    Kinder dabei?
                  </label>
                  <input
                    id="kinder_anzahl"
                    type="number"
                    min={0}
                    max={10}
                    className="feld"
                    value={f.kinder_anzahl}
                    onChange={(e) =>
                      setze("kinder_anzahl", Number(e.target.value) || 0)
                    }
                  />
                </div>
                {f.kinder_anzahl > 0 && (
                  <div>
                    <label className="label" htmlFor="kinder_namen">
                      Namen und Alter der Kinder
                    </label>
                    <input
                      id="kinder_namen"
                      className="feld"
                      placeholder="z.B. Mia (4), Jonas (7)"
                      value={f.kinder_namen}
                      onChange={(e) => setze("kinder_namen", e.target.value)}
                    />
                  </div>
                )}
              </div>
            </fieldset>

            {/* ---------- Tage ---------- */}
            <fieldset className="karte">
              <legend className="font-display text-xl">
                An welchen Tagen bist du dabei?
              </legend>
              <p className="mt-1 text-sm text-grau">
                Es gibt am Freitag ein Get-together und am Sonntag ein
                gemeinsames Frühstück.
              </p>
              <div className="mt-4 space-y-3">
                {(
                  [
                    ["dabei_freitag", "Freitag, 6. August — Get-together"],
                    ["dabei_samstag", "Samstag, 7. August — Hochzeit"],
                    ["dabei_sonntag", "Sonntag, 8. August — Frühstück"],
                  ] as const
                ).map(([key, text]) => (
                  <label key={key} className="flex cursor-pointer items-center gap-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-[var(--color-salbei-dunkel)]"
                      checked={f[key]}
                      onChange={(e) => setze(key, e.target.checked)}
                    />
                    <span>{text}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            {/* ---------- Übernachtung ---------- */}
            <fieldset className="karte">
              <legend className="font-display text-xl">Übernachtung</legend>
              <p className="mt-1 text-sm text-grau">
                Wichtig für uns, damit wir das Zimmerkontingent im Hotel richtig
                planen können.
              </p>

              <div className="mt-4 space-y-3">
                {(
                  [
                    {
                      wert: "hotel",
                      titel: "Im Kloster Haydau",
                      text: "Ich buche (oder habe gebucht) über unser Kontingent.",
                    },
                    {
                      wert: "woanders",
                      titel: "Woanders",
                      text: "Eigene Unterkunft, Ferienwohnung, bei Freunden …",
                    },
                    {
                      wert: "keine",
                      titel: "Gar nicht",
                      text: "Ich reise am selben Tag wieder ab.",
                    },
                  ] as const
                ).map((o) => (
                  <label
                    key={o.wert}
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border-2 p-4 transition-colors ${
                      f.uebernachtung === o.wert
                        ? "border-salbei-dunkel bg-salbei/10"
                        : "border-sand hover:border-salbei"
                    }`}
                  >
                    <input
                      type="radio"
                      name="uebernachtung"
                      className="mt-1 h-4 w-4 accent-[var(--color-salbei-dunkel)]"
                      checked={f.uebernachtung === o.wert}
                      onChange={() => setze("uebernachtung", o.wert)}
                    />
                    <span>
                      <span className="block font-medium">{o.titel}</span>
                      <span className="block text-sm text-grau">{o.text}</span>
                    </span>
                  </label>
                ))}
              </div>

              {f.uebernachtung !== "keine" && (
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="label" htmlFor="naechte">
                      Welche Nächte?
                    </label>
                    <input
                      id="naechte"
                      className="feld"
                      placeholder="z.B. Fr–So"
                      value={f.naechte}
                      onChange={(e) => setze("naechte", e.target.value)}
                    />
                  </div>
                  {f.uebernachtung === "woanders" && (
                    <div>
                      <label className="label" htmlFor="uebernachtung_details">
                        Wo genau? (optional)
                      </label>
                      <input
                        id="uebernachtung_details"
                        className="feld"
                        placeholder="Name der Unterkunft"
                        value={f.uebernachtung_details}
                        onChange={(e) =>
                          setze("uebernachtung_details", e.target.value)
                        }
                      />
                    </div>
                  )}
                </div>
              )}

              {f.uebernachtung === "hotel" && (
                <p className="mt-4 rounded-lg bg-altrosa/15 p-3 text-sm text-grau">
                  Denk daran, das Zimmer selbst beim Hotel zu buchen —
                  Stichwort <strong>{hochzeit.uebernachtung.stichwort}</strong>.
                  Alle Infos findest du{" "}
                  <Link
                    href="/#uebernachtung"
                    className="underline underline-offset-4"
                  >
                    hier
                  </Link>
                  .
                </p>
              )}
            </fieldset>

            {/* ---------- Essen ---------- */}
            <fieldset className="karte">
              <legend className="font-display text-xl">Essen</legend>
              <div className="mt-4">
                <label className="label" htmlFor="essen">
                  Was isst du?
                </label>
                <select
                  id="essen"
                  className="feld"
                  value={f.essen}
                  onChange={(e) =>
                    setze("essen", e.target.value as Rsvp["essen"])
                  }
                >
                  <option value="alles">Ich esse alles</option>
                  <option value="vegetarisch">Vegetarisch</option>
                  <option value="vegan">Vegan</option>
                </select>
              </div>
              <div className="mt-4">
                <label className="label" htmlFor="allergien">
                  Allergien oder Unverträglichkeiten
                </label>
                <input
                  id="allergien"
                  className="feld"
                  placeholder="z.B. Nüsse, Laktose, glutenfrei"
                  value={f.allergien}
                  onChange={(e) => setze("allergien", e.target.value)}
                />
              </div>
            </fieldset>

            {/* ---------- Sonstiges ---------- */}
            <fieldset className="karte">
              <legend className="font-display text-xl">Noch etwas</legend>

              <label className="mt-4 flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 h-4 w-4 accent-[var(--color-salbei-dunkel)]"
                  checked={f.shuttle}
                  onChange={(e) => setze("shuttle", e.target.checked)}
                />
                <span>
                  <span className="font-medium">
                    Ich brauche einen Shuttle vom Bahnhof
                  </span>
                  <span className="block text-sm text-grau">
                    Wir organisieren einen, wenn genug Bedarf da ist.
                  </span>
                </span>
              </label>

              <div className="mt-5">
                <label className="label" htmlFor="lied_wunsch">
                  Ein Lied, zu dem du tanzen willst
                </label>
                <input
                  id="lied_wunsch"
                  className="feld"
                  placeholder="Künstler – Titel"
                  value={f.lied_wunsch}
                  onChange={(e) => setze("lied_wunsch", e.target.value)}
                />
              </div>
            </fieldset>
          </>
        )}

        {/* ---------- Nachricht ---------- */}
        <fieldset className="karte">
          <legend className="font-display text-xl">Nachricht an uns</legend>
          <textarea
            className="feld mt-4 min-h-32 resize-y"
            placeholder={
              zusage
                ? "Wünsche, Fragen, Grüße …"
                : "Magst du uns kurz schreiben, warum es nicht klappt?"
            }
            value={f.nachricht}
            onChange={(e) => setze("nachricht", e.target.value)}
          />
        </fieldset>

        {fehler && (
          <p className="rounded-lg bg-altrosa/20 p-3 text-sm text-tinte">
            {fehler}
          </p>
        )}

        <button type="submit" disabled={laedt} className="btn btn-primar w-full">
          {laedt
            ? "Wird gespeichert …"
            : vorhanden
              ? "Änderungen speichern"
              : "Anmeldung abschicken"}
        </button>
      </form>
    </>
  );
}
