import { hochzeit } from "@/content/hochzeit";

export default function Fusszeile() {
  return (
    <footer className="border-t border-sand bg-sand/40">
      <div className="container-seite py-12 text-center">
        <p className="font-display text-2xl">
          {hochzeit.brautpaar.sie} <span className="text-gold">&</span>{" "}
          {hochzeit.brautpaar.er}
        </p>
        <p className="mt-2 text-sm text-grau">
          {hochzeit.datumLang} · {hochzeit.ort}
        </p>
        <p className="mt-6 text-sm text-grau">
          Fragen? Schreibt uns an{" "}
          <a
            href={`mailto:${hochzeit.kontakt.email}`}
            className="underline underline-offset-4 hover:text-tinte"
          >
            {hochzeit.kontakt.email}
          </a>{" "}
          oder ruft an:{" "}
          <a
            href={`tel:${hochzeit.kontakt.telefon.replace(/\s/g, "")}`}
            className="underline underline-offset-4 hover:text-tinte"
          >
            {hochzeit.kontakt.telefon}
          </a>
        </p>
      </div>
    </footer>
  );
}
