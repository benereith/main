# 01 – Zielarchitektur

## 1. Ausgangslage

Drei getrennte Power-BI-Artefakte verfolgen heute dasselbe Ziel – das Tracking des
Net New ITY:

| Report | Semantikmodell | Datenquellen | Kernaufgabe |
|---|---|---|---|
| **Net New ITY** | `Net New ITY` | Fabric-Lakehouse (`Sales_Pipeline_ITY`, `Retention_ITY_CRM`), SAP-Warehouse `Reporting`, Dataflow `sap_master_data_unit` | Ist/Budget/Forecast-Tracking, Rolls & ITY, Snapshot-Historie |
| **Net New Budget FY2627** | `Net New Budget FY2627` | SAP-Warehouse `Reporting`, SharePoint-XLSX (`2026_04_29_Planung_unknown_ITY_Effekt.xlsx`, `Adjustment 4F.xlsx`), Lakehouse `exports_md` | Budgetierung des unknown ITY inkl. Szenarien (Anlauf 80 %, Verschiebung +1) |
| **CRM Call** | `Net New Budget (2)` | Dataverse **live** (`opportunity`, `cgplc_cgcontract`), SharePoint-Mapping-XLSX | Hypothetische Ableitung des unknown ITY direkt aus dem CRM |

### Diagnose

1. **Dreifache Berechnungslogik.** Der Perioden-Fanout (ITY-Verteilung über Monate)
   existiert dreimal in unterschiedlichen Ausprägungen: als `List.Generate` in
   `fct_opp`/`fct_retention` (CRM Call), als Excel-Zwischendatei (Budget FY2627) und
   als vorberechnete Lakehouse-Tabelle (Net New ITY). Ergebnisse driften auseinander.
2. **Power Query als Rechenmaschine.** `List.Generate` über alle Monate mit
   anschließendem `ExpandListColumn` läuft im Mashup-Engine-Speicher – bei jedem
   Refresh, ohne Faltung, ohne Wiederverwendbarkeit.
3. **Szenarien sind hart codiert.** Der 80-%-Anlauf und die +1-Monats-Verschiebung
   stecken als Spalten (`Betrag_Szenario_Anlauf`, `Verschiebung +1`) in Power Query.
   Jede Änderung an Faktor oder Dauer erfordert ein Modell-Deployment. Das ist die
   Ursache des "manuellen Shiftens".
4. **Auto-Date/Time.** 12–19 `LocalDateTable_*` je Modell. Reines Speicher- und
   Refresh-Gift ohne Nutzen, da eine saubere `DIM_DATE` existiert.
5. **Excel im Pfad.** SharePoint-XLSX als Produktivquelle (`CRM Data`,
   `dim_opp_mapping`, `Adj 4F`) – nicht versionierbar, nicht nachvollziehbar.
6. **Nur 21 CRM-Felder.** `fct_opp` selektiert 21 von >100 verfügbaren
   Opportunity-Attributen; Sales-Stage-Historie, Verlustgründe, Wettbewerber,
   Mobilisierungsdaten fehlen komplett.
7. **Keine Bewegungsanalyse.** Snapshots existieren nur im Report "Net New ITY"
   (`Timestamp`-Spalte), werden aber nicht für Delta-Analysen genutzt. Die Frage
   "Was hat sich seit dem letzten Call im CRM verändert?" ist heute nicht
   beantwortbar.

## 2. Zielbild

```
┌───────────────────────────────────────────────────────────────────────────┐
│ QUELLEN                                                                   │
│  Dataverse (cpgplc.crm.dynamics.com)   SAP-DWH "Reporting"   Dataflow Gen1│
│  opportunity, cgplc_cgcontract,        V_SAP_EXPORTS_        sap_master_  │
│  account, systemuser, territory, …     cleansed              data_unit    │
└──────────────┬──────────────────────────┬────────────────────┬────────────┘
               │  df_crm_ingest           │  df_sap_ingest     │
               │  (Gen2, täglich)         │  (Gen2, täglich)   │
               ▼                          ▼                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ BRONZE   lakehouse_group_controlling / Files+Tables                       │
│  bronze_crm_opportunity   bronze_crm_contract   bronze_crm_account        │
│  bronze_crm_territory     bronze_map_unit_assignment                      │
│  → historisiert: append-only, snapshot_date je Ladelauf (nb_05_snapshot)  │
│                                                                           │
│  bronze_sap_revenue       bronze_sap_unit                                 │
│  → NICHT historisiert: Ersetzen je Lauf, Ist-Stand statt Bewegung         │
└──────────────┬────────────────────────────────────────────────────────────┘
               │ Notebook nb_10_silver (PySpark)
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ SILVER  – typisiert, bereinigt, dedupliziert, fachlich gefiltert          │
│  silver_opportunity   silver_contract   silver_revenue   silver_unit      │
│  → GEGENWART: genau EINE Zeile je Vorgang (nur_letzter_snapshot)          │
│  → Veränderung liegt getrennt in silver_*_history                         │
│  → Business Rules der Group Guidance (Feb 2025) angewandt                 │
└──────────────┬────────────────────────────────────────────────────────────┘
               │ Notebook nb_20_gold (PySpark)
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ GOLD    – Star Schema, direkt konsumierbar                                │
│  FAKTEN                          DIMENSIONEN                              │
│  gold_fct_net_new_ity   ◄────►   gold_dim_date       (Fiskalkalender)     │
│  gold_fct_revenue                gold_dim_unit       (SAP-Betrieb)        │
│  gold_fct_crm_movement           gold_dim_opportunity                     │
│                                  gold_dim_contract                        │
│                                  gold_dim_status     (Won/Pipeline/…)     │
│                                  gold_dim_hfm_struktur (MAP-Konten)       │
│                                  gold_dim_snapshot                        │
│  QUALITÄT                                                                 │
│  gold_dq_checks  (Regelverstöße je Ladelauf)                              │
└──────────────┬────────────────────────────────────────────────────────────┘
               │ Import-Modus (klein) – 1 Semantikmodell
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ SEMANTIKMODELL  "Net New ITY Cockpit"                                     │
│  · keine Auto-Date-Tabellen · keine Berechnungsspalten in PQ              │
│  · Szenario-Parameter als disconnected Tables (Shift, Anlauf, Schwelle)   │
│  · alle Measures dokumentiert (description + HFM-Konto)                   │
└──────────────┬────────────────────────────────────────────────────────────┘
               ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ BERICHT  "Net New ITY Cockpit"  – 10 Seiten, Storytelling-with-Data       │
└───────────────────────────────────────────────────────────────────────────┘
```

### Die Schichtgrenze zwischen Bronze und Silver

Die wichtigste Regel des Modells, weil ihre Verletzung nicht auffällt:

| Schicht | Enthält | Zeilen je Vorgang |
|---|---|---|
| `bronze_crm_*` | **Historie**, append-only – ein vollständiger Tagesstand je Ladelauf | *n* (Zahl der Ladeläufe) |
| `silver_*` | **Gegenwart** | genau 1 |
| `silver_*_history` | **Veränderung**, aus den Silver-Ständen aufgebaut | 1 je echter Änderung |

`nb_10_silver` muss deshalb jede Bronze-Lesestelle durch
`nur_letzter_snapshot()` klammern (Funktion in `nb_00_config`). Ohne diesen
Filter liest Silver die volle Historie und **jede Summe vervielfacht sich mit
der Zahl der bisherigen Ladeläufe** – am zweiten Tag also exakt das Doppelte.

Das ist genau einmal passiert und war von außen nicht erkennbar: Gold schreibt
ein einheitliches `snapshot_date = RUN_DATE`, die doppelten Zeilen sind im
Ergebnis nicht von echten Daten zu unterscheiden. Regel `DQ-SIL-001`
(`docs/08_datenqualitaet.md`) prüft den Grain seitdem und bricht die Pipeline
ab, bevor das Semantikmodell aktualisiert wird.

`bronze_sap_*` ist von der Regel ausgenommen: diese Tabellen werden je Lauf
ersetzt statt historisiert und tragen deshalb kein `snapshot_date`.
`nur_letzter_snapshot()` gibt sie unverändert zurück.

### Die zweite historisierte Schicht: Gold

`gold_fct_net_new_ity` wird ebenfalls **ergänzt statt ersetzt** – ein
vollständiger Tagesstand je Ladelauf. Das ist bewusst eine Ausnahme von der
üblichen Rollenteilung, in der Gold nur die Gegenwart trägt, und sie hat einen
Grund, den keine andere Schicht erfüllen kann:

> Die Bronze-Historie enthält die CRM-**Rohstände**. Was der Bericht daraus
> rechnet – gewichtet, über die Perioden verteilt, um den Vorjahresanteil
> bereinigt – entsteht erst in Gold. Wer wissen will, wie die *Pipeline* vor
> zwei Wochen aussah, kann das aus Bronze nicht rekonstruieren, ohne den
> gesamten Fanout nachzurechnen.

Damit gilt für diese eine Gold-Tabelle dieselbe Leseregel wie für Bronze: **nie
ohne Stichtagsfilter summieren.** Abgesichert ist das in den Notebooks über
`nur_letzter_snapshot()` und im Semantikmodell über `[Net New ITY (brutto)]`,
das immer genau einen Stichtag setzt. Aufbewahrt werden die letzten 90 Tage
vollständig und ältere Stände als Monatsletzte; Begründung und Betrieb:
`docs/06_deployment.md`, Abschnitt „Die Gold-Historie".

## 3. Auslagerungsentscheidungen

Leitregel: **Alles, was nicht vom Filterkontext des Nutzers abhängt, gehört in die
Gold-Schicht. Alles, was der Nutzer im Bericht variieren können muss, bleibt DAX.**

| Logik | Heute | Ziel | Begründung |
|---|---|---|---|
| CRM-Extraktion + Filter (`statecodename`, `salesstage`) | Power Query, live gegen Dataverse | **Dataflow Gen2 → Bronze** | Entkoppelt Report-Refresh von CRM-Verfügbarkeit; ein Extrakt für alle Consumer |
| ITY-Monatszahl `Calc_ITY_Months` | M-Formel je Zeile | **Gold, SQL** | Deterministisch, kontextfrei |
| Perioden-Fanout (`List.Generate` + `ExpandListColumn`) | M, unfaltbar | **Gold, `GENERATE_SERIES` / explode** | Größter Performance-Hebel; wird von Spark parallelisiert |
| ITY-/ARO-Monatswert | M | **Gold** | kontextfrei |
| Gewichtung × Win-% / (1 − Retention-%) | M | **Gold** (Basis) **+ DAX** (Override) | Basis fix, Override als Szenario |
| Status-Buckets (Won / Expected Win / Pipeline …) | M `if`-Kaskade | **Gold + `gold_dim_status`** | Als Dimension referenzierbar, sortierbar, farblich gebunden |
| CoC-Mapping auf HFM-Konten | M-Funktion `fn_MapCoCh`, 3× dupliziert | **Gold, eine Funktion** | Single Source of Truth |
| YTD-Kumulation SAP | SQL-Window (bereits) | **Gold beibehalten** | war schon richtig |
| Budgetannahmen unknown ITY (Excel) | M im Semantikmodell (`CRM Data`): Periodenraster, YTD, Werkableitung | **Dataflow → Bronze → Gold** | Bericht hing an der Erreichbarkeit einer SharePoint-Datei; kein Stichtag; derselbe Fanout existierte im Lakehouse bereits |
| Fiskalkalender | M, 3× dupliziert | **Gold `gold_dim_date`** | einmalig |
| Snapshot-Historisierung | teilweise | **Silver SCD2** | ermöglicht Bewegungsanalyse |
| **Anlauf-Faktor / -Dauer** | M-Spalte (0,8 / 3 Monate) | **DAX + What-if-Parameter** | Nutzer muss variieren können |
| **Verschiebung ± Monate** | M-Spalte `Verschiebung +1` | **DAX + What-if-Parameter** | Nutzer muss variieren können |
| **Win-%-Schwelle für "Expected Win"** | M-Konstante 0,80 | **DAX + What-if-Parameter** | Sensitivitätsanalyse |
| Zeitintelligenz (YTD/MTD/SPLY) | DAX | **DAX** | kontextabhängig |
| Bridge-/Waterfall-Zerlegung | – | **DAX** | kontextabhängig |

### Was bewusst *nicht* ausgelagert wird

* **Szenariologik.** Würde man die Szenarien materialisieren, bräuchte man je
  Kombination aus Shift (−3…+6), Anlauffaktor (50–100 %) und Anlaufdauer (0–6) eine
  eigene Faktenversion – das sind >400 Varianten des Fakts. Die DAX-Variante
  iteriert stattdessen über die **niedrigkardinale** Spalte `period_index` (1–13)
  bzw. `fy_period` (1–12) und ist damit praktisch gratis.
* **Ist/Plan-Vergleiche.** Hängen vom gewählten Werttyp/Version ab.

## 4. Refresh-Topologie

| Objekt | Frequenz | Auslöser | Laufzeit-Ziel |
|---|---|---|---|
| `df_crm_*` (Dataflow Gen2) | täglich 05:00 | Zeitplan | < 10 min |
| `nb_10_silver` | täglich 05:30 | Pipeline nach Dataflow | < 5 min |
| `nb_20_gold` | täglich 05:45 | Pipeline nach Silver | < 5 min |
| `nb_30_quality` | täglich 06:00 | Pipeline nach Gold | < 2 min |
| Semantikmodell | täglich 06:15 | Pipeline nach Quality | < 3 min |

Die Fabric-Data-Pipeline `pl_net_new_ity_daily` orchestriert die Kette und bricht
bei DQ-Fehlern der Schweregrad-Stufe `ERROR` ab, bevor das Semantikmodell aktualisiert
wird (siehe `docs/08_datenqualitaet.md`).

## 5. Migrationspfad

Die drei Altreports bleiben zunächst parallel bestehen. Der Abgleich erfolgt über
die Seite **"Abstimmung & Datenqualität"** des neuen Berichts, die die Kennzahlen
des Neubaus gegen die Altwerte stellt. Details und das vollständige
Measure-Mapping alt → neu: `docs/07_migration_mapping.md`.
