"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { hochzeit } from "@/content/hochzeit";

const links = [
  { href: "/#ablauf", text: "Ablauf" },
  { href: "/#location", text: "Location" },
  { href: "/#anfahrt", text: "Anfahrt" },
  { href: "/#uebernachtung", text: "Übernachtung" },
  { href: "/#dresscode", text: "Dresscode" },
  { href: "/#fotos", text: "Fotos" },
  { href: "/#faq", text: "FAQ" },
];

export default function Navigation() {
  const [offen, setOffen] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [istAdmin, setIstAdmin] = useState(false);

  useEffect(() => {
    const supabase = createClient();

    const pruefen = async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      setEmail(user?.email ?? null);
      setIstAdmin(
        !!user?.email &&
          hochzeit.adminEmails
            .map((e) => e.toLowerCase())
            .includes(user.email.toLowerCase()),
      );
    };

    pruefen();
    const { data } = supabase.auth.onAuthStateChange(() => pruefen());
    return () => data.subscription.unsubscribe();
  }, []);

  const abmelden = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/";
  };

  return (
    <header className="sticky top-0 z-50 border-b border-sand/70 bg-creme/85 backdrop-blur-md">
      <nav className="container-seite flex h-16 items-center justify-between gap-4">
        <Link
          href="/"
          className="font-display text-lg tracking-wide whitespace-nowrap"
        >
          {hochzeit.brautpaar.sie} <span className="text-gold">&</span>{" "}
          {hochzeit.brautpaar.er}
        </Link>

        {/* Desktop */}
        <div className="hidden items-center gap-6 lg:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="text-sm text-grau transition-colors hover:text-tinte"
            >
              {l.text}
            </Link>
          ))}
        </div>

        <div className="hidden items-center gap-3 lg:flex">
          {istAdmin && (
            <Link href="/admin" className="text-sm font-medium text-gold">
              Admin
            </Link>
          )}
          {email ? (
            <>
              <Link href="/rsvp" className="btn btn-primar !px-5 !py-2 !text-sm">
                Meine Anmeldung
              </Link>
              <button
                onClick={abmelden}
                className="text-sm text-grau hover:text-tinte"
              >
                Abmelden
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm text-grau hover:text-tinte">
                Anmelden
              </Link>
              <Link
                href="/registrieren"
                className="btn btn-primar !px-5 !py-2 !text-sm"
              >
                Zusagen
              </Link>
            </>
          )}
        </div>

        {/* Mobile */}
        <button
          onClick={() => setOffen(!offen)}
          className="lg:hidden"
          aria-label="Menü öffnen"
          aria-expanded={offen}
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
            <path
              d={offen ? "M6 6l12 12M18 6L6 18" : "M4 7h16M4 12h16M4 17h16"}
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </nav>

      {offen && (
        <div className="border-t border-sand bg-creme lg:hidden">
          <div className="container-seite flex flex-col gap-1 py-4">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOffen(false)}
                className="py-2 text-grau"
              >
                {l.text}
              </Link>
            ))}
            <div className="mt-3 flex flex-col gap-2 border-t border-sand pt-4">
              {istAdmin && (
                <Link
                  href="/admin"
                  onClick={() => setOffen(false)}
                  className="py-2 font-medium text-gold"
                >
                  Admin-Bereich
                </Link>
              )}
              {email ? (
                <>
                  <Link
                    href="/rsvp"
                    onClick={() => setOffen(false)}
                    className="btn btn-primar"
                  >
                    Meine Anmeldung
                  </Link>
                  <button onClick={abmelden} className="py-2 text-left text-grau">
                    Abmelden
                  </button>
                </>
              ) : (
                <>
                  <Link
                    href="/registrieren"
                    onClick={() => setOffen(false)}
                    className="btn btn-primar"
                  >
                    Zusagen
                  </Link>
                  <Link
                    href="/login"
                    onClick={() => setOffen(false)}
                    className="btn btn-rand"
                  >
                    Anmelden
                  </Link>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
