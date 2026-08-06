"use client";

import Link from "next/link";
import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { supabaseKonfiguriert } from "@/lib/supabase/konfiguriert";
import VorschauHinweis from "@/components/VorschauHinweis";
import { hochzeit } from "@/content/hochzeit";

export default function Registrieren() {
  const [vorname, setVorname] = useState("");
  const [nachname, setNachname] = useState("");
  const [email, setEmail] = useState("");
  const [passwort, setPasswort] = useState("");
  const [passwort2, setPasswort2] = useState("");
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [fertig, setFertig] = useState(false);

  if (!supabaseKonfiguriert) {
    return <VorschauHinweis was="Die Gäste-Anmeldung ist" />;
  }

  const absenden = async (e: React.FormEvent) => {
    e.preventDefault();
    setFehler(null);

    if (passwort !== passwort2) {
      return setFehler("Die beiden Passwörter stimmen nicht überein.");
    }
    if (passwort.length < 8) {
      return setFehler("Das Passwort muss mindestens 8 Zeichen lang sein.");
    }

    setLaedt(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signUp({
      email: email.trim(),
      password: passwort,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?weiter=/rsvp`,
        data: { vorname: vorname.trim(), nachname: nachname.trim() },
      },
    });
    setLaedt(false);

    if (error) {
      setFehler(
        error.message.includes("already registered")
          ? "Für diese E-Mail gibt es schon einen Zugang. Bitte melde dich an."
          : `Das hat nicht geklappt: ${error.message}`,
      );
      return;
    }
    setFertig(true);
  };

  if (fertig) {
    return (
      <div className="container-seite flex min-h-[75vh] items-center justify-center py-16">
        <div className="w-full max-w-md karte text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-salbei/25 text-salbei-dunkel">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
              <path
                d="M4 7l8 5 8-5M4 6h16v12H4z"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h1 className="font-display text-3xl">Schau in dein Postfach</h1>
          <p className="mt-4 leading-relaxed text-grau">
            Wir haben eine Bestätigungsmail an{" "}
            <strong className="text-tinte">{email}</strong> geschickt. Klick auf
            den Link darin — danach kannst du das Anmeldeformular ausfüllen.
          </p>
          <p className="mt-4 text-sm text-grau">
            Nichts angekommen? Schau bitte im Spam-Ordner nach oder schreib uns
            an{" "}
            <a
              href={`mailto:${hochzeit.kontakt.email}`}
              className="underline underline-offset-4"
            >
              {hochzeit.kontakt.email}
            </a>
            .
          </p>
          <Link href="/" className="btn btn-rand mt-7">
            Zurück zur Startseite
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container-seite flex min-h-[85vh] items-center justify-center py-16">
      <div className="w-full max-w-md">
        <div className="text-center">
          <p className="kicker">Schritt 1 von 2</p>
          <h1 className="ueberschrift mt-3">Zugang anlegen</h1>
          <p className="mt-3 leading-relaxed text-grau">
            Damit nur eingeladene Gäste zusagen und ihr eure Angaben später
            ändern könnt, legt ihr euch kurz einen Zugang an.
          </p>
        </div>

        <form onSubmit={absenden} className="karte mt-8 space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label" htmlFor="vorname">
                Vorname
              </label>
              <input
                id="vorname"
                className="feld"
                required
                autoComplete="given-name"
                value={vorname}
                onChange={(e) => setVorname(e.target.value)}
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
                autoComplete="family-name"
                value={nachname}
                onChange={(e) => setNachname(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="label" htmlFor="email">
              E-Mail-Adresse
            </label>
            <input
              id="email"
              type="email"
              className="feld"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label className="label" htmlFor="passwort">
              Passwort (mindestens 8 Zeichen)
            </label>
            <input
              id="passwort"
              type="password"
              className="feld"
              required
              minLength={8}
              autoComplete="new-password"
              value={passwort}
              onChange={(e) => setPasswort(e.target.value)}
            />
          </div>

          <div>
            <label className="label" htmlFor="passwort2">
              Passwort wiederholen
            </label>
            <input
              id="passwort2"
              type="password"
              className="feld"
              required
              autoComplete="new-password"
              value={passwort2}
              onChange={(e) => setPasswort2(e.target.value)}
            />
          </div>

          {fehler && (
            <p className="rounded-lg bg-altrosa/20 p-3 text-sm text-tinte">
              {fehler}
            </p>
          )}

          <button
            type="submit"
            disabled={laedt}
            className="btn btn-primar w-full"
          >
            {laedt ? "Einen Moment …" : "Zugang anlegen"}
          </button>

          <p className="text-center text-sm text-grau">
            Schon registriert?{" "}
            <Link href="/login" className="underline underline-offset-4">
              Hier anmelden
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
