"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { supabaseKonfiguriert } from "@/lib/supabase/konfiguriert";
import VorschauHinweis from "@/components/VorschauHinweis";

function LoginFormular() {
  const router = useRouter();
  const params = useSearchParams();
  const weiter = params.get("weiter") || "/rsvp";

  const [email, setEmail] = useState("");
  const [passwort, setPasswort] = useState("");
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [resetInfo, setResetInfo] = useState<string | null>(null);

  const absenden = async (e: React.FormEvent) => {
    e.preventDefault();
    setFehler(null);
    setLaedt(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password: passwort,
    });
    setLaedt(false);

    if (error) {
      setFehler(
        error.message.includes("Email not confirmed")
          ? "Bitte bestätige zuerst den Link in unserer E-Mail."
          : "E-Mail-Adresse oder Passwort stimmen nicht.",
      );
      return;
    }

    router.push(weiter);
    router.refresh();
  };

  const passwortVergessen = async () => {
    if (!email.trim()) {
      return setFehler("Trag bitte oben deine E-Mail-Adresse ein.");
    }
    const supabase = createClient();
    const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/auth/callback?weiter=/rsvp`,
    });
    if (error) return setFehler(error.message);
    setFehler(null);
    setResetInfo(
      "Wir haben dir eine Mail zum Zurücksetzen des Passworts geschickt.",
    );
  };

  return (
    <div className="w-full max-w-md">
      <div className="text-center">
        <p className="kicker">Willkommen zurück</p>
        <h1 className="ueberschrift mt-3">Anmelden</h1>
      </div>

      <form onSubmit={absenden} className="karte mt-8 space-y-4">
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
            Passwort
          </label>
          <input
            id="passwort"
            type="password"
            className="feld"
            required
            autoComplete="current-password"
            value={passwort}
            onChange={(e) => setPasswort(e.target.value)}
          />
        </div>

        {fehler && (
          <p className="rounded-lg bg-altrosa/20 p-3 text-sm text-tinte">
            {fehler}
          </p>
        )}
        {resetInfo && (
          <p className="rounded-lg bg-salbei/20 p-3 text-sm text-tinte">
            {resetInfo}
          </p>
        )}

        <button type="submit" disabled={laedt} className="btn btn-primar w-full">
          {laedt ? "Einen Moment …" : "Anmelden"}
        </button>

        <button
          type="button"
          onClick={passwortVergessen}
          className="w-full text-center text-sm text-grau underline underline-offset-4"
        >
          Passwort vergessen?
        </button>

        <p className="border-t border-sand pt-4 text-center text-sm text-grau">
          Noch keinen Zugang?{" "}
          <Link href="/registrieren" className="underline underline-offset-4">
            Jetzt anlegen
          </Link>
        </p>
      </form>
    </div>
  );
}

export default function Login() {
  if (!supabaseKonfiguriert) {
    return <VorschauHinweis was="Der Login ist" />;
  }

  return (
    <div className="container-seite flex min-h-[85vh] items-center justify-center py-16">
      <Suspense fallback={null}>
        <LoginFormular />
      </Suspense>
    </div>
  );
}
