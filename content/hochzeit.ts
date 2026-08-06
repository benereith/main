/* ============================================================================
 *  ZENTRALE INHALTS-DATEI
 *  ----------------------------------------------------------------------------
 *  Hier änderst du ALLE Texte, Zeiten, Adressen und Bilder der Webseite.
 *  Du brauchst dafür keine Programmierkenntnisse: Ändere nur den Text
 *  zwischen den "Anführungszeichen". Kommas und geschweifte Klammern
 *  bitte stehen lassen.
 *
 *  Nach dem Speichern (bzw. nach "git push") baut Vercel die Seite
 *  automatisch neu — ca. 1 Minute später ist die Änderung online.
 * ========================================================================== */

export const hochzeit = {
  /* ----------------------------------------------------------------------
   * 1. GRUNDDATEN
   * -------------------------------------------------------------------- */
  brautpaar: {
    sie: "Anna",
    er: "Benedict",
    nachname: "Reith",
  },

  // Datum der Trauung im Format JAHR-MONAT-TAG und Uhrzeit (für den Countdown)
  datumISO: "2027-08-07T13:00:00+02:00",
  datumLang: "Samstag, 7. August 2027",

  ort: "Kloster Haydau, Morschen",

  // Bis wann sollen sich die Gäste zurückmelden?
  rsvpDeadline: "30. April 2027",
  rsvpDeadlineISO: "2027-04-30",

  // Kontakt für Rückfragen der Gäste
  kontakt: {
    email: "benedictreith@gmail.com",
    telefon: "+49 151 5611 9129",
  },

  /* ----------------------------------------------------------------------
   * 2. BEGRÜSSUNG (Startseite)
   * -------------------------------------------------------------------- */
  hero: {
    kicker: "Wir heiraten",
    text: "Wir freuen uns riesig, diesen Tag mit euch zu feiern — im Kloster Haydau, mit allem was dazugehört: Trauung, gutem Essen, Musik und einer langen Nacht.",
    // Großes Hintergrundbild. Datei in /public ablegen, z.B. /public/hero.jpg
    // Solange kein Bild da ist, wird ein dezenter Farbverlauf angezeigt.
    bild: "",
  },

  /* ----------------------------------------------------------------------
   * 3. ABLAUF
   *    Beliebig viele Tage, beliebig viele Programmpunkte.
   * -------------------------------------------------------------------- */
  ablauf: [
    {
      tag: "Freitag, 6. August 2027",
      untertitel: "Anreise & Get-together",
      punkte: [
        {
          zeit: "ab 15:00",
          titel: "Check-in im Hotel",
          text: "Die Zimmer im Kloster Haydau stehen ab 15:00 Uhr bereit.",
        },
        {
          zeit: "ab 19:00",
          titel: "Gemeinsames Abendessen",
          text: "Lockeres Get-together in der Hotelbar für alle, die schon da sind. Kein Dresscode, einfach kommen.",
        },
      ],
    },
    {
      tag: "Samstag, 7. August 2027",
      untertitel: "Der große Tag",
      punkte: [
        {
          zeit: "06:30 – 11:00",
          titel: "Frühstücksbuffet",
          text: "Im Hotelrestaurant, für alle Übernachtungsgäste inklusive.",
        },
        {
          zeit: "ab 12:30",
          titel: "Ankommen an der Klosterkirche",
          text: "Bitte seid rechtzeitig da — die Kirche liegt direkt auf dem Gelände.",
        },
        {
          zeit: "13:00",
          titel: "Kirchliche Trauung",
          text: "In der Klosterkirche Haydau.",
        },
        {
          zeit: "ca. 14:00",
          titel: "Sektempfang",
          text: "Anschließend Empfang mit Getränken und Fingerfood.",
        },
        {
          zeit: "ca. 15:00",
          titel: "Check-in für Tagesgäste",
          text: "Ab 15:00 Uhr könnt ihr eure Hotelzimmer beziehen.",
        },
        {
          zeit: "ab 18:00",
          titel: "Abendessen in der Orangerie",
          text: "Festliches Menü im Saal. Bitte gebt uns bei der Anmeldung eure Essenswünsche und Allergien an.",
        },
        {
          zeit: "ca. 21:00",
          titel: "Eröffnungstanz & Party",
          text: "Danach gehört die Tanzfläche euch.",
        },
        {
          zeit: "00:00",
          titel: "Mitternachtssnack",
          text: "Currywurst — und eine vegetarische Alternative.",
        },
      ],
    },
    {
      tag: "Sonntag, 8. August 2027",
      untertitel: "Ausklang",
      punkte: [
        {
          zeit: "06:30 – 11:00",
          titel: "Frühstück",
          text: "Im Hotelrestaurant.",
        },
        {
          zeit: "bis 11:00",
          titel: "Check-out",
          text: "Late Check-out ist auf Anfrage an der Rezeption möglich.",
        },
      ],
    },
  ],

  /* ----------------------------------------------------------------------
   * 4. LOCATION
   * -------------------------------------------------------------------- */
  location: {
    name: "Hotel Kloster Haydau",
    adresse: "In der Haydau 2, 34326 Morschen",
    telefon: "+49 5664 93910-960",
    website: "https://www.hotel-kloster-haydau.de",
    beschreibung:
      "Ein barockes Klosterensemble an der Fulda: Trauung in der Klosterkirche, Empfang im Innenhof und Feier in der Orangerie — alles fußläufig auf einem Gelände, das Hotel inklusive.",
    // Für die eingebettete Karte: Google-Maps-Koordinaten
    kartenQuery: "Hotel+Kloster+Haydau,+In+der+Haydau+2,+34326+Morschen",
    highlights: [
      {
        titel: "Klosterkirche",
        text: "Die Trauung findet in der historischen Klosterkirche direkt auf dem Gelände statt.",
      },
      {
        titel: "Orangerie",
        text: "Der festliche Saal für Abendessen, Tanz und Party.",
      },
      {
        titel: "Innenhof & Rondell",
        text: "Sektempfang unter freiem Himmel — bei gutem Wetter der schönste Fleck.",
      },
      {
        titel: "Spa & Fitness",
        text: "Für Übernachtungsgäste frei nutzbar. Perfekt für den Sonntag danach.",
      },
    ],
    // Bilder der Location: Dateien in /public/location/ ablegen
    bilder: [] as { datei: string; alt: string }[],
  },

  /* ----------------------------------------------------------------------
   * 5. ANFAHRT
   * -------------------------------------------------------------------- */
  anfahrt: [
    {
      art: "Mit dem Auto",
      text: "Über die A7, Abfahrt Malsfeld (Nr. 82) oder Abfahrt Homberg/Efze, dann Richtung Morschen. Von Kassel ca. 45 Minuten, von Fulda ca. 60 Minuten, von Frankfurt ca. 2 Stunden.",
      hinweis: "Parken ist auf den hoteleigenen Parkplätzen kostenfrei.",
    },
    {
      art: "Mit der Bahn",
      text: "ICE bis Kassel-Wilhelmshöhe oder Fulda, weiter mit dem Regionalzug bis Melsungen oder Rotenburg an der Fulda. Von dort sind es ca. 15 Minuten mit dem Taxi.",
      hinweis: "Sagt uns Bescheid, wenn ihr eine Mitfahrgelegenheit vom Bahnhof braucht — wir organisieren gerne einen Shuttle.",
    },
    {
      art: "Mit dem Flugzeug",
      text: "Nächster Flughafen ist Frankfurt am Main (ca. 2 Stunden mit dem Auto) oder Kassel-Calden (ca. 1 Stunde).",
      hinweis: "",
    },
  ],

  /* ----------------------------------------------------------------------
   * 6. ÜBERNACHTUNG
   *    Preise laut Angebot vom 18.04.2026 (Sonderrate für unsere Hochzeit).
   * -------------------------------------------------------------------- */
  uebernachtung: {
    text: "Wir haben im Kloster Haydau ein Zimmerkontingent für euch reserviert. Bitte bucht direkt beim Hotel und nennt dabei unser Stichwort — dann bekommt ihr die Sonderrate.",
    stichwort: "Hochzeit Reith, Buchungsnummer 22.484/73.494",
    hotelEmail: "reservierung@hotel-kloster-haydau.de",
    hotelTelefon: "+49 5664 93910-960",
    // WICHTIG: Das Kontingent verfällt schrittweise. Bitte rechtzeitig buchen!
    kontingentHinweis:
      "Das Kontingent wird 8 Wochen vor der Hochzeit teilweise und 4 Wochen vorher komplett aufgelöst. Bucht also am besten früh.",
    zimmer: [
      { kategorie: "Comfort Doppelzimmer", preis: "134 € / Nacht" },
      { kategorie: "Comfort Einzelzimmer", preis: "118 € / Nacht" },
      { kategorie: "Superior Doppelzimmer", preis: "155 € / Nacht" },
      { kategorie: "Junior Suite (Doppel)", preis: "165 € / Nacht" },
      { kategorie: "Standard DZ (Poststation)", preis: "114 € / Nacht" },
    ],
    inklusive: [
      "Frühstücksbuffet",
      "Nutzung von Spa & Fitness",
      "Kostenfreies Parken",
      "Minibar (im Haupthaus)",
    ],
  },

  /* ----------------------------------------------------------------------
   * 7. DRESSCODE
   *    Beispielbilder: Dateien in /public/dresscode/ ablegen
   *    und hier unter "datei" eintragen, z.B. "/dresscode/damen-1.jpg".
   *    Leere Einträge zeigen ein Platzhalter-Feld mit der Farbe.
   * -------------------------------------------------------------------- */
  dresscode: {
    titel: "Festlich – Cocktail / Anzug",
    text: "Es darf gern schick werden: für die Herren Anzug (Krawatte optional), für die Damen Cocktailkleid oder langes Kleid. Wir feiern im Sommer in einem Kloster — denkt an bequeme Schuhe für Kopfsteinpflaster und eine leichte Jacke für den Abend im Innenhof.",
    bitteNicht: [
      "Weiß und Creme sind für die Braut reserviert",
      "Keine Jeans oder Sneaker",
      "Keine Stilettos — das Kopfsteinpflaster gewinnt immer",
    ],
    // Farbpalette als Inspiration. Farbwerte sind Hex-Codes.
    farben: [
      { name: "Salbeigrün", hex: "#9CAF88" },
      { name: "Altrosa", hex: "#D3A9A0" },
      { name: "Sand", hex: "#D9C7A7" },
      { name: "Tiefblau", hex: "#3E5871" },
      { name: "Terrakotta", hex: "#B5654A" },
    ],
    beispiele: [
      { datei: "", alt: "Langes Kleid in Salbeigrün", label: "Damen: langes Kleid" },
      { datei: "", alt: "Cocktailkleid in Altrosa", label: "Damen: Cocktailkleid" },
      { datei: "", alt: "Anzug in Dunkelblau", label: "Herren: dunkler Anzug" },
      { datei: "", alt: "Anzug in Beige mit Fliege", label: "Herren: heller Sommeranzug" },
    ],
  },

  /* ----------------------------------------------------------------------
   * 8. GESCHENKE
   * -------------------------------------------------------------------- */
  geschenke: {
    text: "Das größte Geschenk ist, dass ihr dabei seid. Wer uns darüber hinaus etwas mitgeben möchte: Wir sparen auf unsere Hochzeitsreise und freuen uns über einen Beitrag dazu.",
    // Optional: Link zu einer Wunschliste. Leer lassen = wird nicht angezeigt.
    wunschlisteUrl: "",
  },

  /* ----------------------------------------------------------------------
   * 9. FAQ
   * -------------------------------------------------------------------- */
  faq: [
    {
      frage: "Kann ich meine Kinder mitbringen?",
      antwort:
        "Ja, sehr gerne! Gebt sie bitte bei der Anmeldung mit an, damit wir Kindermenüs und Sitzplätze einplanen können. Ein Kinderbetreuungsraum ist in Planung.",
    },
    {
      frage: "Bis wann muss ich mich anmelden?",
      antwort:
        "Bitte bis zum 30. April 2027. Danach müssen wir dem Hotel die endgültigen Zahlen melden.",
    },
    {
      frage: "Ich habe eine Lebensmittelallergie oder esse vegetarisch/vegan.",
      antwort:
        "Kein Problem — trag das einfach im Anmeldeformular ein. Die Küche stellt das entsprechend um.",
    },
    {
      frage: "Gibt es einen Shuttle?",
      antwort:
        "Wenn genügend Gäste vom Bahnhof abgeholt werden müssen, organisieren wir einen Shuttle. Kreuzt das im Formular an.",
    },
    {
      frage: "Kann ich eine Rede oder ein Spiel machen?",
      antwort:
        "Sehr gern! Meldet euch bitte vorher bei unseren Trauzeugen, damit wir den Abend planen können und nicht fünf Reden hintereinander kommen.",
    },
    {
      frage: "Darf ich fotografieren?",
      antwort:
        "Während der Trauung bitten wir euch, die Handys wegzulassen — dafür haben wir einen Fotografen. Danach: immer her damit, wir freuen uns über eure Bilder.",
    },
    {
      frage: "Kann ich mein Haustier mitbringen?",
      antwort:
        "Im Hotel sind Hunde gegen einen Aufpreis von 30 € pro Nacht erlaubt. Bitte meldet das direkt beim Hotel an.",
    },
  ],

  /* ----------------------------------------------------------------------
   * 10. FOTOS (nach der Hochzeit)
   *     Solange "freigeschaltet: false" steht, sehen die Gäste nur einen
   *     Hinweis. Nach der Hochzeit auf "true" stellen.
   * -------------------------------------------------------------------- */
  fotos: {
    freigeschaltet: false,
    hinweisVorher:
      "Hier gibt es nach der Hochzeit die Bilder unseres Fotografen. Wir schalten die Galerie frei, sobald wir sie bekommen haben — ihr bekommt eine Mail von uns.",
    // Variante A: Link zur Galerie des Fotografen (am einfachsten)
    galerieUrl: "",
    galeriePasswort: "",
    // Variante B: Eigene Bilder in /public/fotos/ ablegen und hier eintragen
    bilder: [] as { datei: string; alt: string }[],
  },

  /* ----------------------------------------------------------------------
   * 11. ADMIN-ZUGANG
   *     Nur diese E-Mail-Adressen sehen den Admin-Bereich mit den
   *     Anmeldungen. Zusätzlich muss die Adresse in Supabase als
   *     "is_admin" markiert sein (siehe README).
   * -------------------------------------------------------------------- */
  adminEmails: ["benedictreith@gmail.com"],
};

export type Hochzeit = typeof hochzeit;
