export default function Abschnitt({
  id,
  kicker,
  titel,
  einleitung,
  hell = false,
  children,
}: {
  id: string;
  kicker?: string;
  titel: string;
  einleitung?: string;
  hell?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className={`abschnitt ${hell ? "bg-sand/35" : ""} scroll-mt-20`}
    >
      <div className="container-seite">
        <header className="mx-auto max-w-2xl text-center">
          {kicker && <p className="kicker">{kicker}</p>}
          <h2 className="ueberschrift mt-3">{titel}</h2>
          {einleitung && (
            <p className="mt-4 leading-relaxed text-grau">{einleitung}</p>
          )}
        </header>
        <div className="mt-12">{children}</div>
      </div>
    </section>
  );
}
