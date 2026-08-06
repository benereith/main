import Link from "next/link";
import { hochzeit } from "@/content/hochzeit";
import Abschnitt from "@/components/Abschnitt";
import Countdown from "@/components/Countdown";
import Faq from "@/components/Faq";

export default function Startseite() {
  const h = hochzeit;

  return (
    <>
      {/* ================= HERO ================= */}
      <section className="relative flex min-h-[88vh] items-center justify-center overflow-hidden">
        {h.hero.bild ? (
          <img
            src={h.hero.bild}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 bg-gradient-to-br from-sand via-creme to-salbei/25" />
        )}
        <div className="absolute inset-0 bg-creme/55" />

        <div className="container-seite relative text-center einblenden">
          <p className="kicker">{h.hero.kicker}</p>
          <h1 className="mt-5 font-display text-[clamp(3rem,11vw,6.5rem)] leading-[1.05]">
            {h.brautpaar.sie}
            <span className="mx-3 text-gold">&</span>
            {h.brautpaar.er}
          </h1>
          <p className="mt-5 text-lg text-grau">
            {h.datumLang} · {h.ort}
          </p>

          <p className="mx-auto mt-7 max-w-xl leading-relaxed text-grau">
            {h.hero.text}
          </p>

          <div className="mt-10">
            <Countdown zielISO={h.datumISO} />
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link href="/registrieren" className="btn btn-primar">
              Jetzt zu- oder absagen
            </Link>
            <Link href="#ablauf" className="btn btn-rand">
              Zum Ablauf
            </Link>
          </div>

          <p className="mt-5 text-sm text-grau">
            Bitte gebt uns bis zum <strong>{h.rsvpDeadline}</strong> Bescheid.
          </p>
        </div>
      </section>

      {/* ================= ABLAUF ================= */}
      <Abschnitt
        id="ablauf"
        kicker="Programm"
        titel="Der Ablauf"
        einleitung="Damit ihr wisst, wann was passiert. Kleine Verschiebungen sind erlaubt — das ist eine Hochzeit, kein Bahnfahrplan."
        hell
      >
        <div className="mx-auto max-w-3xl space-y-14">
          {h.ablauf.map((tag) => (
            <div key={tag.tag}>
              <div className="mb-8 text-center">
                <h3 className="font-display text-2xl">{tag.tag}</h3>
                <p className="mt-1 text-sm tracking-wide text-gold uppercase">
                  {tag.untertitel}
                </p>
              </div>

              <ol className="relative space-y-7 border-l border-sand pl-8 sm:pl-10">
                {tag.punkte.map((p) => (
                  <li key={p.titel} className="relative">
                    <span
                      className="absolute top-2 -left-[41px] h-2.5 w-2.5 rounded-full bg-salbei ring-4 ring-creme sm:-left-[49px]"
                      aria-hidden
                    />
                    <p className="text-sm font-semibold tracking-wide text-gold">
                      {p.zeit}
                    </p>
                    <h4 className="mt-0.5 font-display text-xl">{p.titel}</h4>
                    <p className="mt-1 leading-relaxed text-grau">{p.text}</p>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </Abschnitt>

      {/* ================= LOCATION ================= */}
      <Abschnitt
        id="location"
        kicker="Wo wir feiern"
        titel={h.location.name}
        einleitung={h.location.beschreibung}
      >
        <div className="grid gap-5 sm:grid-cols-2">
          {h.location.highlights.map((hl) => (
            <div key={hl.titel} className="karte">
              <h3 className="font-display text-xl">{hl.titel}</h3>
              <p className="mt-2 leading-relaxed text-grau">{hl.text}</p>
            </div>
          ))}
        </div>

        {h.location.bilder.length > 0 && (
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {h.location.bilder.map((b) => (
              <img
                key={b.datei}
                src={b.datei}
                alt={b.alt}
                className="aspect-4/3 w-full rounded-xl object-cover"
              />
            ))}
          </div>
        )}

        <div className="mt-8 karte text-center">
          <p className="font-medium">{h.location.name}</p>
          <p className="mt-1 text-grau">{h.location.adresse}</p>
          <div className="mt-4 flex flex-wrap justify-center gap-3">
            <a
              href={h.location.website}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-rand !py-2 !text-sm"
            >
              Website des Hotels
            </a>
            <a
              href={`https://www.google.com/maps/dir/?api=1&destination=${h.location.kartenQuery}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-rand !py-2 !text-sm"
            >
              Route planen
            </a>
          </div>
        </div>
      </Abschnitt>

      {/* ================= ANFAHRT ================= */}
      <Abschnitt
        id="anfahrt"
        kicker="Hinkommen"
        titel="Anfahrt"
        einleitung="Morschen liegt zwischen Kassel und Bad Hersfeld, direkt an der A7."
        hell
      >
        <div className="grid gap-5 lg:grid-cols-3">
          {h.anfahrt.map((a) => (
            <div key={a.art} className="karte">
              <h3 className="font-display text-xl">{a.art}</h3>
              <p className="mt-2 leading-relaxed text-grau">{a.text}</p>
              {a.hinweis && (
                <p className="mt-3 border-l-2 border-salbei pl-3 text-sm text-grau">
                  {a.hinweis}
                </p>
              )}
            </div>
          ))}
        </div>

        <div className="mt-8 overflow-hidden rounded-2xl border border-sand">
          <iframe
            title="Karte zum Kloster Haydau"
            src={`https://www.google.com/maps?q=${h.location.kartenQuery}&output=embed`}
            className="h-[380px] w-full"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
          />
        </div>
      </Abschnitt>

      {/* ================= ÜBERNACHTUNG ================= */}
      <Abschnitt
        id="uebernachtung"
        kicker="Schlafen"
        titel="Übernachtung"
        einleitung={h.uebernachtung.text}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="karte">
            <h3 className="font-display text-xl">So bucht ihr</h3>
            <ol className="mt-4 space-y-3 text-grau">
              <li className="flex gap-3">
                <span className="shrink-0 font-semibold text-gold">1.</span>
                <span>
                  Direkt beim Hotel anfragen — per Mail an{" "}
                  <a
                    href={`mailto:${h.uebernachtung.hotelEmail}`}
                    className="underline underline-offset-4"
                  >
                    {h.uebernachtung.hotelEmail}
                  </a>{" "}
                  oder telefonisch unter {h.uebernachtung.hotelTelefon}.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="shrink-0 font-semibold text-gold">2.</span>
                <span>
                  Stichwort nennen:{" "}
                  <strong className="text-tinte">
                    {h.uebernachtung.stichwort}
                  </strong>
                </span>
              </li>
              <li className="flex gap-3">
                <span className="shrink-0 font-semibold text-gold">3.</span>
                <span>
                  Bei uns im Formular eintragen, dass ihr im Hotel schlaft —
                  dann behalten wir den Überblick.
                </span>
              </li>
            </ol>
            <p className="mt-5 rounded-lg bg-altrosa/15 p-3 text-sm text-grau">
              {h.uebernachtung.kontingentHinweis}
            </p>
          </div>

          <div className="karte">
            <h3 className="font-display text-xl">Zimmer & Preise</h3>
            <p className="mt-1 text-sm text-grau">
              Sonderrate für unsere Hochzeit, pro Zimmer und Nacht.
            </p>
            <ul className="mt-4 divide-y divide-sand">
              {h.uebernachtung.zimmer.map((z) => (
                <li
                  key={z.kategorie}
                  className="flex items-center justify-between gap-4 py-2.5"
                >
                  <span className="text-grau">{z.kategorie}</span>
                  <span className="shrink-0 font-medium">{z.preis}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-grau">
              Inklusive: {h.uebernachtung.inklusive.join(" · ")}
            </p>
          </div>
        </div>
      </Abschnitt>

      {/* ================= DRESSCODE ================= */}
      <Abschnitt
        id="dresscode"
        kicker="Was anziehen"
        titel={h.dresscode.titel}
        einleitung={h.dresscode.text}
        hell
      >
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {h.dresscode.beispiele.map((b) => (
            <figure key={b.label} className="overflow-hidden rounded-xl bg-white">
              {b.datei ? (
                <img
                  src={b.datei}
                  alt={b.alt}
                  className="aspect-3/4 w-full object-cover"
                />
              ) : (
                <div className="flex aspect-3/4 w-full items-center justify-center bg-gradient-to-br from-sand to-salbei/25 p-4 text-center">
                  <span className="text-sm text-grau">
                    Beispielbild folgt
                    <br />
                    <span className="text-xs">({b.alt})</span>
                  </span>
                </div>
              )}
              <figcaption className="px-3 py-3 text-center text-sm text-grau">
                {b.label}
              </figcaption>
            </figure>
          ))}
        </div>

        <div className="mt-10 grid gap-6 lg:grid-cols-2">
          <div className="karte">
            <h3 className="font-display text-xl">Farbinspiration</h3>
            <p className="mt-1 text-sm text-grau">
              Kein Muss — aber wenn ihr Lust habt, passt ihr euch damit schön ins
              Bild ein.
            </p>
            <div className="mt-5 flex flex-wrap gap-5">
              {h.dresscode.farben.map((f) => (
                <div key={f.name} className="text-center">
                  <div
                    className="mx-auto h-14 w-14 rounded-full ring-1 ring-black/5"
                    style={{ backgroundColor: f.hex }}
                  />
                  <p className="mt-2 text-xs text-grau">{f.name}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="karte">
            <h3 className="font-display text-xl">Bitte lieber nicht</h3>
            <ul className="mt-4 space-y-2.5">
              {h.dresscode.bitteNicht.map((n) => (
                <li key={n} className="flex gap-3 text-grau">
                  <span className="text-altrosa" aria-hidden>
                    ✕
                  </span>
                  <span>{n}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Abschnitt>

      {/* ================= FOTOS ================= */}
      <Abschnitt
        id="fotos"
        kicker="Erinnerungen"
        titel="Fotos"
        einleitung={
          h.fotos.freigeschaltet ? undefined : h.fotos.hinweisVorher
        }
      >
        {!h.fotos.freigeschaltet ? (
          <div className="mx-auto max-w-md karte text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-sand text-gold">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                <path
                  d="M3 8.5A2.5 2.5 0 015.5 6h1.7l1-2h7.6l1 2h1.7A2.5 2.5 0 0121 8.5v9A2.5 2.5 0 0118.5 20h-13A2.5 2.5 0 013 17.5v-9z"
                  stroke="currentColor"
                  strokeWidth="1.4"
                />
                <circle
                  cx="12"
                  cy="13"
                  r="3.5"
                  stroke="currentColor"
                  strokeWidth="1.4"
                />
              </svg>
            </div>
            <p className="text-grau">Die Galerie öffnet nach dem 7. August 2027.</p>
          </div>
        ) : (
          <>
            {h.fotos.galerieUrl && (
              <div className="mx-auto mb-8 max-w-md karte text-center">
                <p className="text-grau">
                  Alle Bilder unseres Fotografen findet ihr hier:
                </p>
                <a
                  href={h.fotos.galerieUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primar mt-4"
                >
                  Zur Fotogalerie
                </a>
                {h.fotos.galeriePasswort && (
                  <p className="mt-3 text-sm text-grau">
                    Passwort:{" "}
                    <strong className="text-tinte">
                      {h.fotos.galeriePasswort}
                    </strong>
                  </p>
                )}
              </div>
            )}

            {h.fotos.bilder.length > 0 && (
              <div className="columns-1 gap-4 sm:columns-2 lg:columns-3 [&>*]:mb-4">
                {h.fotos.bilder.map((b) => (
                  <img
                    key={b.datei}
                    src={b.datei}
                    alt={b.alt}
                    loading="lazy"
                    className="w-full rounded-xl"
                  />
                ))}
              </div>
            )}
          </>
        )}
      </Abschnitt>

      {/* ================= GESCHENKE ================= */}
      <Abschnitt id="geschenke" kicker="Falls ihr fragt" titel="Geschenke" hell>
        <div className="mx-auto max-w-xl karte text-center">
          <p className="leading-relaxed text-grau">{h.geschenke.text}</p>
          {h.geschenke.wunschlisteUrl && (
            <a
              href={h.geschenke.wunschlisteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-rand mt-5"
            >
              Zur Wunschliste
            </a>
          )}
        </div>
      </Abschnitt>

      {/* ================= FAQ ================= */}
      <Abschnitt id="faq" kicker="Gute Fragen" titel="Häufige Fragen">
        <Faq eintraege={h.faq} />
      </Abschnitt>

      {/* ================= CTA ================= */}
      <section className="abschnitt bg-salbei-dunkel text-creme">
        <div className="container-seite text-center">
          <p className="kicker !text-creme/70">Wir brauchen eure Antwort</p>
          <h2 className="ueberschrift mt-3">Seid ihr dabei?</h2>
          <p className="mx-auto mt-4 max-w-lg text-creme/85">
            Legt euch mit eurer E-Mail-Adresse einen Zugang an, bestätigt die
            Mail und füllt das Formular aus. Ihr könnt eure Angaben jederzeit
            wieder ändern.
          </p>
          <Link
            href="/registrieren"
            className="btn mt-8 bg-creme text-tinte hover:bg-white"
          >
            Zum Anmeldeformular
          </Link>
          <p className="mt-4 text-sm text-creme/70">
            Rückmeldung bitte bis {h.rsvpDeadline}
          </p>
        </div>
      </section>
    </>
  );
}
