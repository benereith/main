# 07 – Migration: alt nach neu

Welche Kennzahl und welche Seite der drei Altberichte wo im neuen Bericht
wiederzufinden ist. Grundlage für den Parallelbetrieb und die Abnahme.

---

## 1. Ausgangsumfang

| Bericht | Seiten | Tabellen | Kennzahlen | Auto-Datumstabellen |
|---|---:|---:|---:|---:|
| Net New ITY | 23 | 32 | ~70 | 12 |
| Net New Budget FY2627 | 18 | 16 | 30 | 5 |
| CRM Call (Net New Budget 2) | 10 | 39 | 9 | 15 |
| **Summe** | **51** | **87** | **~109** | **32** |

| Neubau | Seiten | Tabellen | Kennzahlen | Auto-Datumstabellen |
|---|---:|---:|---:|---:|
| Net New ITY Cockpit | 9 | 16 | 51 | 0 |

Der Rückgang bei den Kennzahlen entsteht nicht durch Weglassen, sondern durch
Entdopplung: `ACT_Value`, `ACT_REV_YTD`, `ACT_Periodic`, `ACT_dynamisch`,
`ACT_Base` waren fünf Varianten derselben Frage. Im Neubau erledigt das die
Kombination aus `[Umsatz Ist]` und dem Filterkontext.

---

## 2. Kennzahlen-Mapping

### 2.1 CRM-Pipeline (New Business)

| Alt | Modell | Neu | Anmerkung |
|---|---|---|---|
| `Sales_ITY` | Net New ITY | `[New Business ITY]` | Vorzeichen jetzt einheitlich positiv |
| `Sales_ITY_Act` | Net New ITY | `[New Business ITY]` | Der Filter auf den letzten Snapshot entfällt: die Gold-Tabelle enthält nur den aktuellen Stand, die Historie liegt in `FCT CRM-Bewegung` |
| `Sales_ITY_Hist` | Net New ITY | `[New Business ITY]` + Stichtagsfilter | |
| `CRM_Won_ITY` | Net New ITY | `[ITY Won]` | |
| `CRM_Exp_Won_ITY` | Net New ITY | `[ITY Expected Win]` | |
| `CRM_In_Pipeline` | Net New ITY | `[ITY Pipeline]` | |
| `CRM_Wins_ITY` | Net New ITY | `[ITY Won] + [ITY Expected Win]` | |
| `CRM_Pipeline_all` | Net New ITY | `[New Business ITY]` | Summe aller Status = das Ganze |
| `Unweighted ITY` | Net New ITY | `[Net New ITY]` mit Bewertungsbasis "Vollwert" | Statt eigener Kennzahl jetzt eine Einstellung |
| `Unweighted ITY_Act` | Net New ITY | dito | |
| `Win%` | Net New ITY | `[Ø Win-% (volumengewichtet)]` | **Fachliche Änderung:** vorher ungewichteter Mittelwert. Der behandelte eine 5-Mio-Opportunity mit 30 % wie eine 50-Tsd-Opportunity mit 90 % |
| `Win%_Act` | Net New ITY | dito | |
| `Anzahl_Opps`, `Anzahl_Opps_Act` | Net New ITY | `[Anzahl Opportunities]` | |
| `Opening Date`, `Closing Date` | Net New ITY | `DIM Opportunity[Mobilisierung]`, `[Entscheidungsdatum]` | Als Spalten statt als Kennzahl – ein Attribut ist keine Kennzahl |
| `LT_Win%`, `LT_Opening_Date` | Net New ITY | `FCT CRM-Bewegung[Wahrscheinlichkeit alt/neu]` | Der Snapshot-Vergleich ist jetzt eine eigene Faktentabelle |
| `crm_ity`, `ity_effect` | CRM Call | `[New Business ITY]` | |
| `ity_effect_25/26`, `ity_effect_26/27` | CRM Call | `[New Business ITY]` + Filter auf `DIM Datum[GJ Bezeichnung]` | Zwei Kennzahlen für zwei Jahre ersetzt durch einen Filter |
| `crm_ity_sply`, `crm_ity_delta` | CRM Call | `[Net New ITY Vorjahr]`, `[Net New ITY Δ Vorjahr]` | |

### 2.2 CRM-Retention (Lost Business)

| Alt | Modell | Neu | Anmerkung |
|---|---|---|---|
| `Retention_ITY` | Net New ITY | `[Lost Business ITY]` | Das `*-1` entfällt – Vorzeichen kommt aus dem Lakehouse |
| `Retention_ITY_Act` | Net New ITY | `[Lost Business ITY]` | |
| `Retention_ITY_Hist` | Net New ITY | `[Lost Business ITY]` + Stichtagsfilter | |
| `CRM_Lost_ITY` | Net New ITY | `[ITY Lost]` | |
| `CRM_Exp_Lost_ITY` | Net New ITY | `[ITY Expected Loss]` | |
| `CRM_At_Risk_ITY` | Net New ITY | `[ITY At Risk]` | |
| `CRM_Losses_ITY` | Net New ITY | `[ITY Lost] + [ITY Expected Loss]` | |
| `CRM_Retention_all` | Net New ITY | `[Lost Business ITY]` | |
| `R_Unweighted ITY`, `R_Unweighted ITY_ACT` | Net New ITY | `[Net New ITY]` mit Bewertungsbasis "Vollwert" | |
| `Retention%`, `Retention_%` | Net New ITY | `DIM Vertrag[Retention %]` | Zwei identische Kennzahlen zusammengeführt |
| `Retention_Status` | Net New ITY | `DIM Status[Status]` | |
| `Contract_End_Date`, `LT_Contract End Date` | Net New ITY | `DIM Vertrag[Vertragsende (bereinigt)]` | |
| `Anzahl_Ret`, `Anzahl_Ret_Act` | Net New ITY | `[Anzahl Risikoverträge]` | |
| `Lost ITY` | CRM Call | `[Lost Business ITY]` | |
| `ARO_LY`, `LY_REV`, `REV_LY` | Net New ITY | `[Organischer Umsatz Vorjahr]`, `DIM Vertrag[Vorjahres-ARO]` | Drei Kennzahlen mit fest verdrahtetem Jahr 2024 – im Neubau relativ zum gewählten Geschäftsjahr |

### 2.3 SAP-Umsätze

| Alt | Modell | Neu | Anmerkung |
|---|---|---|---|
| `ACT_Value`, `ACT_REV_YTD`, `ACT_Base` | Net New ITY | `[Umsatz Ist]` | Die YTD-Variante entsteht aus dem Filterkontext, nicht aus einer eigenen Kennzahl |
| `ACT_Periodic`, `ACT_REV_Periodic` | Net New ITY | `[Umsatz Ist]` | Der Fakt liegt bereits periodisch vor; die Kumulation kommt aus `[Wert kumuliert]` |
| `ACT_dynamisch` | Net New ITY | `[Umsatz Ist]` + Datenschnitt | Die Feldparametertabelle `Zeitansicht` wird nicht mehr gebraucht |
| `BUD_Value`, `BUD_REV_YTD`, `BUD_Periodic`, `BUD_REV_Periodic`, `BUD_dynamisch` | Net New ITY | `[Umsatz Budget]` | Fünf Varianten zu einer |
| `RGF_Value`, `RGF_Periodic`, `FC_REV_YTD`, `FC_REV_Periodic`, `FC_dynamisch`, `RF_Value`, `RF_Periodic`, `R03_Value`, `R03_Periodic`, `35_Value`, `35_Periodic`, `90_Value`, `90_Periodic` | Net New ITY / CRM Call | `[Umsatz Forecast]` bzw. Filter auf `FCT Umsatz[Werttyp Version]` | Dreizehn Kennzahlen, die sich nur in der SAP-Version unterscheiden – jetzt eine Kennzahl und ein Datenschnitt |
| `Adj_FC_Value`, `Hybrid_Gesamtwert_RGF`, `Hybrid_Gesamtwert_RF` | Net New ITY | `[Umsatz Ist]` / `[Umsatz Forecast]` + `DIM Datum[Ist Vergangenheit]` | Die Ist/Plan-Umschaltung hängt jetzt an einer Spalte statt an `SELECTEDVALUE('Abgeschlossene Periode')` |
| `SAP_Value`, `SAP_Periodic` | Budget FY2627 | `[Umsatz Ist]` | |
| `Baseline_ITY` (Konstante 666.509.100) | Budget FY2627 | `[Organischer Umsatz Vorjahr]` | **Fachliche Änderung:** die hart codierte Zahl wird jetzt berechnet |
| `SAP_ITY%`, `ITY%_CRM`, `CRM_*_ITY%` | Budget FY2627 | `[New Business %]`, `[Net New Business %]` | |

### 2.4 Net-New-Hierarchie

| Alt | Modell | Neu |
|---|---|---|
| `New Roll Budget`, `New Roll Forecast/Actuals`, `New Roll Delta` | Net New ITY | `[Umsatz Budget]` / `[Umsatz Forecast]` + Filter `DIM HFM-Struktur[Kennzahl]` |
| `Lost Roll Budget`, `Lost Roll Forecast/Actuals`, `Lost Roll Delta` | Net New ITY | dito |
| `Net New Roll Budget`, `Net New Roll Forecast/Actuals`, `Net New Roll Delta` | Net New ITY | dito |
| `New Business ITY BUD`, `Lost Business ITY BUD` | Net New ITY | `[Umsatz Budget]` + Filter auf die Hierarchie |
| `KPI Value` (SWITCH über 21 Kennzahlen) | Net New ITY | entfällt | Die Scorecard entsteht aus der Matrix über `DIM HFM-Struktur`. Ein SWITCH über 21 Kennzahlen ist nicht wartbar |
| `New_Roll_Bud_Exp_LY/CY/No_Exp` | Net New ITY | `[Umsatz Budget]` + `DIM Betrieb[Vertragsbeginn]` | |

### 2.5 Szenarien (Budget FY2627)

| Alt | Neu | Anmerkung |
|---|---|---|
| `CRM_Monat_Original` | `[Net New ITY]` | |
| `CRM_Monat_Anlauf` (Faktor 0,8 fest, 3 Monate fest) | `[Net New ITY (Szenario)]` mit Anlaufreglern | **Kernverbesserung.** Faktor und Dauer sind jetzt einstellbar |
| `CRM_Monat_Verschiebung` (+1 fest) | `[Net New ITY (Szenario)]` mit Verschiebungsregler | **Kernverbesserung.** −3 bis +6 Monate ohne Modelländerung |
| `CRM_Monat_Kombi` | `[Net New ITY (Szenario)]` | Beide Effekte zusammen sind der Regelfall, nicht eine vierte Kennzahl |
| `Delta_80%`, `Delta_Verschiebung`, `Delta_Kombi` | `[Δ Szenario zu Basis]` | |
| `Target_Value`, `Delta_Target`, `Puffer_Budget_geplant`, `zu_pufferndes_delta` | `[Δ CRM zu Budget]`, `[Zielerreichung]` | |
| `SAP/CRM-Delta` | `[Δ CRM zu Budget]` | |

### 2.6 Ohne Entsprechung

| Alt | Grund |
|---|---|
| `RECH_adj_BUD_Value`, `Act_test`, `41_test`, `delta_original`, `CRM_Monat_Original_Check` | Rechercheartefakte, ausgeblendet, keine produktive Nutzung |
| `Split_Bud_Rolls_New`, `Split_Bud_Rolls_Lost` | Identischer DAX-Ausdruck in beiden Kennzahlen |
| `Net New Roll`, `Roll Periodic` | Identischer DAX-Ausdruck |
| `BUD_Losses_CRM` | `TREATAS` über Werk – im Neubau eine reguläre Beziehung |
| `Ist_Neu`, `Eröffnungsperiode` | Zwischenergebnisse des Power-Query-Szenarios; im Fakt als `Periodenindex` enthalten |
| `UP`, `Net New Marge` | Betrifft die Ergebnisrechnung, nicht Net New ITY. Bei Bedarf über `cgplc_bgpercent` neu aufzubauen |

---

## 3. Seiten-Mapping

| Altbericht · Seite | Neu |
|---|---|
| Net New ITY · KPI Overview, Scorecard | Cockpit |
| Net New ITY · Net New ITY Actual Period / YTD | Cockpit (Filterkontext) |
| Net New ITY · Budget vs Forecast FY, Budget vs RF | Abstimmung & Datenqualität |
| Net New ITY · Split nach Management, Split Rolls | Cockpit (Matrix) |
| Net New ITY · CRM Sales Pipeline ITY | New Business |
| Net New ITY · CRM Retention Pipeline ITY | Lost Business |
| Net New ITY · Growth View Sales / Retention | CRM-Bewegung |
| Net New ITY · Top 15 Rolls (4 Seiten) | New Business (sortierte Tabelle mit Filter statt vier Seiten) |
| Net New ITY · New Business Revenues, New Business Export | New Business |
| Net New ITY · Drilltrough | Detail (Drillthrough) |
| Net New ITY · Recherche, Duplikat von Recherche, Seite 1, Seite 2 | entfällt |
| Budget FY2627 · Budget_Arbeit, Net New Budget | Cockpit |
| Budget FY2627 · Net New ITY Szenario Analyse | Szenarien |
| Budget FY2627 · Sektoraufteilung | Net-New-Brücke |
| Budget FY2627 · SAP/CRM-Check, Ist Neu | Abstimmung & Datenqualität |
| Budget FY2627 · Budget Export, Drilltrough | Detail (Drillthrough) |
| Budget FY2627 · 9 Duplikat-/Seite-N-Seiten | entfällt |
| CRM Call · New Business, New Business w/o secured | New Business (Schwellenregler statt eigener Seite) |
| CRM Call · Lost Business, Lost Business w/o secured | Lost Business |
| CRM Call · Export NB, Export LB, Duplikat | New/Lost Business (Tabellen mit Export) |
| CRM Call · Abgleich, Recherche, Seite 1 | Abstimmung & Datenqualität |

---

## 4. Bewusste fachliche Abweichungen

Diese Punkte sind **keine** Übersetzungsfehler, sondern Entscheidungen. Sie
gehören in die Abnahme, weil sie zu abweichenden Zahlen führen können.

| # | Alt | Neu | Begründung |
|---|---|---|---|
| 1 | `Win%` als ungewichteter Mittelwert | volumengewichtet | Der ungewichtete Mittelwert ist als Steuerungsgröße irreführend |
| 2 | `Baseline_ITY` = 666.509.100 (Konstante) | `[Organischer Umsatz Vorjahr]` berechnet | Eine Konstante veraltet still |
| 3 | Vorzeichen an fünf Stellen unterschiedlich gedreht | einmal im Lakehouse | Vorher war dasselbe Vorzeichen je nach Kennzahl unterschiedlich |
| 4 | Zeilen ohne Mobilisierungsdatum stillschweigend gefiltert | in `gold_dq_checks` protokolliert | Der fehlende Betrag war vorher nicht erklärbar |
| 5 | Anlauf 80 % über 3 Monate fest | einstellbar, Vorbelegung 100 % / 0 Monate | **Wichtig für die Abnahme:** Der Vorgabewert entspricht *keinem* Anlaufeffekt. Um die Altzahl zu reproduzieren, sind 80 % und 3 Monate einzustellen |
| 6 | Verschiebung +1 fest | einstellbar, Vorbelegung 0 | Analog: für die Altzahl auf +1 stellen |
| 7 | `dim_opp_*` beidseitig filternd | einseitig | Beidseitige Filter machten Ergebnisse von der Reihenfolge der Filter abhängig |
| 8 | ITY-Werte ohne Plausibilisierung gegen ARO | Regel DQ-OPP-003 (ERROR) | ITY über ARO ist fachlich unmöglich und deutet auf Pflegefehler |

---

## 5. Vorgehen bei der Abnahme

1. **Parallelbetrieb.** Alt- und Neubericht nebeneinander laufen lassen.
2. **Kalibrierung.** Auf der Szenarienseite Anlauf auf 80 % / 3 Monate und
   Verschiebung auf +1 stellen. Damit entsprechen die Annahmen dem Altmodell.
3. **Abgleich je Periode.** Seite *Abstimmung & Datenqualität*, Matrix
   `[Net New ITY (Szenario)]` gegen die Altwerte je Geschäftsperiode.
4. **Abweichungen einordnen.** Jede Differenz muss sich auf eine Zeile aus
   Abschnitt 4 oder auf einen Eintrag in `gold_dq_checks` zurückführen lassen.
   Bleibt eine Differenz unerklärt, ist sie ein Fehler und kein Rundungseffekt.
5. **Freigabe.** Erst danach die Altberichte stilllegen.
