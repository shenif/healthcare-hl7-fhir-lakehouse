# HL7 v2 ↔ FHIR R4 field map

How the same facts appear in each source. Silver notebooks parse these fields into one conformed shape.

## Patient

| Concept | HL7 v2 (PID segment) | FHIR R4 (Patient) | Notes |
| --- | --- | --- | --- |
| Hospital MRN | PID-3 repetition with `^^^LEGACYHIS^MR` | not present | Legacy 8-digit MRN; some lose leading zeros |
| Enterprise ID | PID-3 repetition with `^^^SYNTHEA^PI` (only ~60% of messages) | `Patient.id` | When present, an exact match key |
| Family / given name | PID-5.1 / PID-5.2 (PID-5.3 middle) | `name[0].family` / `name[0].given` | ~10% of HL7 names in UPPER CASE |
| Date of birth | PID-7 (`YYYYMMDD`) | `birthDate` (`YYYY-MM-DD`) | |
| Sex | PID-8 (`M`/`F`/`U`) | `gender` (`male`/`female`) | |
| Address | PID-11 (street^^city^state^zip^country) | `address[0]` | |
| SSN | PID-19 | `identifier` with type `SS` | Direct identifier: dropped in silver |

## Encounter / visit

| Concept | HL7 v2 | FHIR R4 (Encounter) | Notes |
| --- | --- | --- | --- |
| Event type | MSH-9.2 (`A01` admit, `A02` transfer, `A03` discharge, `A04` register) | n/a | One visit produces several messages |
| Message ID | MSH-10 | n/a | Re-sent duplicates share the same MSH-10 |
| Visit number | PV1-19 (`V#########`) | `Encounter.id` (different value) | Not shared across sources |
| Patient class | PV1-2 (`I`, `E`, `O`) | `class.code` (`IMP`, `EMER`, `AMB`) | |
| Unit / facility | PV1-3 (unit^^^facility code^^^^^facility name) | `serviceProvider.display`, `location` | |
| Admit time | PV1-44 | `period.start` | HL7 timestamps vary in format |
| Discharge time | PV1-45 (on A03) | `period.end` | ~2% of A03 messages missing it |

## Diagnosis

| Concept | HL7 v2 (DG1) | FHIR R4 (Condition) |
| --- | --- | --- |
| Code | DG1-3.1 (SNOMED CT) | `code.coding[0].code` |
| Description | DG1-3.2 | `code.coding[0].display` |
| Coding system | DG1-3.3 (`SCT`) | `code.coding[0].system` |
| Encounter link | same message as PV1 | `encounter.reference` |

## Reading the HL7 files

Each line in an `adt_YYYYMM.hl7` file is one message; segments inside it are separated by `\r`.
In Spark, read with `spark.read.option("lineSep", "\n").text(path)`. Without the `lineSep`
option Spark also splits on `\r` and breaks each message into separate segment rows.
