import type { Metadata } from "next";
import "./globals.css";
import { hochzeit } from "@/content/hochzeit";
import Navigation from "@/components/Navigation";
import Fusszeile from "@/components/Fusszeile";
import { supabaseKonfiguriert } from "@/lib/supabase/konfiguriert";

const { sie, er } = hochzeit.brautpaar;

export const metadata: Metadata = {
  title: `${sie} & ${er} — ${hochzeit.datumLang}`,
  description: `Wir heiraten am ${hochzeit.datumLang} im ${hochzeit.location.name}. Alle Infos zu Ablauf, Anfahrt, Übernachtung und Anmeldung.`,
  robots: { index: false, follow: false }, // Seite soll nicht bei Google auftauchen
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin=""
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {!supabaseKonfiguriert && (
          <div className="bg-gold/20 px-4 py-2 text-center text-xs text-tinte">
            Vorschau-Modus — Inhalte sind live, Anmeldung und Admin-Bereich
            brauchen noch ein Supabase-Projekt (siehe README).
          </div>
        )}
        <Navigation />
        <main>{children}</main>
        <Fusszeile />
      </body>
    </html>
  );
}
