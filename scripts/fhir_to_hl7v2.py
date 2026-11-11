"""
Generate a synthetic HL7 v2.5.1 ADT feed from Synthea FHIR R4 bundles.

Scenario: legacy hospital systems send ADT messages; the regional EHR exports FHIR.
This script turns the hospital encounters in the FHIR bundles into the ADT feed
those legacy systems would have sent, so both sources describe the same patients.

Output: one file per month (adt_YYYYMM.hl7). Each LINE is one HL7 message; inside
a message, segments are separated by carriage returns (\r), as in a stripped MLLP batch.

Deliberate data-quality issues (seeded, so every run is identical):
  - ~3% of messages are re-sent duplicates (same MSH-10 control ID)
  - ~10% of names arrive in UPPER CASE
  - ~5% of MRNs lose their leading zeros
  - ~40% of messages carry no enterprise (Synthea) ID, so patients must be matched on demographics
  - timestamps vary: with seconds, without seconds, or with a UTC offset
  - ~2% of discharges (A03) are missing the discharge time (PV1-45)
  - ~8% of messages have no diagnosis (DG1) segment

Also writes hl7_ground_truth.csv (MRN ↔ Synthea patient ID, visit number ↔ FHIR
encounter ID) for validating the matching logic. Keep it OUT of the landing folder.

Usage:  python fhir_to_hl7v2.py <synthea_fhir_folder> <output_folder> [--since 2015]
"""
import csv
import glob
import hashlib
import json
import os
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

SEED = 20261110
SINCE_YEAR = 2015


def h(text, n):
    """Deterministic n-digit number from a string."""
    return int(hashlib.sha256(text.encode()).hexdigest(), 16) % (10 ** n)


def mrn_for(patient_id):
    return f"{h('mrn' + patient_id, 8):08d}"


def visit_for(encounter_id):
    return f"V{h('visit' + encounter_id, 9):09d}"


def facility_code(name):
    letters = re.sub(r"[^A-Z ]", "", name.upper()).split()
    code = "".join(w[0] for w in letters if w not in {"OF", "THE", "INC", "AND"})[:6]
    return f"{code or 'FAC'}{h(name, 3):03d}"


def ts(dt_iso, rng):
    """FHIR datetime -> HL7 TS, in one of three formats (deliberately inconsistent)."""
    dt = datetime.fromisoformat(dt_iso)
    style = rng.random()
    if style < 0.70:
        return dt.strftime("%Y%m%d%H%M%S")
    if style < 0.85:
        return dt.strftime("%Y%m%d%H%M")
    return dt.strftime("%Y%m%d%H%M%S") + "+0000"


def esc(value):
    """Escape HL7 delimiters inside a field value."""
    if value is None:
        return ""
    return (str(value).replace("\\", "\\E\\").replace("|", "\\F\\")
            .replace("^", "\\S\\").replace("&", "\\T\\").replace("~", "\\R\\"))


def load_bundle(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(src, out, since=SINCE_YEAR):
    rng = random.Random(SEED)
    os.makedirs(out, exist_ok=True)
    files = [p for p in glob.glob(os.path.join(src, "*.json"))
             if not os.path.basename(p).startswith(("hospitalInformation", "practitionerInformation"))]

    by_month = defaultdict(list)
    truth = []
    ctrl = 0

    for path in sorted(files):
        bundle = load_bundle(path)
        resources = [e["resource"] for e in bundle.get("entry", [])]
        patient = next(r for r in resources if r["resourceType"] == "Patient")
        pid_fhir = patient["id"]
        mrn = mrn_for(pid_fhir)

        name = patient["name"][0]
        family = name.get("family", "")
        given = name.get("given", [""])
        ssn = next((i["value"] for i in patient.get("identifier", [])
                    if i.get("type", {}).get("coding", [{}])[0].get("code") == "SS"), "")
        addr = (patient.get("address") or [{}])[0]
        sex = {"male": "M", "female": "F"}.get(patient.get("gender"), "U")
        dob = patient.get("birthDate", "").replace("-", "")

        conditions = defaultdict(list)
        for r in resources:
            if r["resourceType"] == "Condition" and "encounter" in r:
                conditions[r["encounter"]["reference"].split(":")[-1]].append(r["code"]["coding"][0])

        for enc in (r for r in resources if r["resourceType"] == "Encounter"):
            cls = enc["class"]["code"]
            start, end = enc["period"]["start"], enc["period"].get("end")
            fac_name = enc.get("serviceProvider", {}).get("display", "UNKNOWN")
            if int(start[:4]) < since:
                continue
            # Legacy hospital feed: all emergency and inpatient visits, plus outpatient visits at hospitals
            if not (cls in ("EMER", "IMP") or (cls == "AMB" and "HOSP" in fac_name.upper())):
                continue

            visit = visit_for(enc["id"])
            fac = facility_code(fac_name)
            pclass = {"IMP": "I", "EMER": "E"}.get(cls, "O")
            truth.append([mrn, pid_fhir, visit, enc["id"], fac_name])

            events = [("A01" if cls == "IMP" else "A04", start)]
            if cls == "IMP" and end and rng.random() < 0.3:
                mid = datetime.fromisoformat(start) + (datetime.fromisoformat(end) - datetime.fromisoformat(start)) / 2
                events.append(("A02", mid.isoformat()))
            if end:
                events.append(("A03", end))

            for event, when in events:
                ctrl += 1
                upper = rng.random() < 0.10
                fam = family.upper() if upper else family
                giv = [g.upper() if upper else g for g in given]
                mrn_out = mrn.lstrip("0") if rng.random() < 0.05 else mrn
                pid3 = f"{mrn_out}^^^LEGACYHIS^MR"
                if rng.random() >= 0.40:
                    pid3 += f"~{pid_fhir}^^^SYNTHEA^PI"

                msh = (f"MSH|^~\\&|LEGACY_ADT|{fac}|DATAHUB|HEALTHREGION|{ts(when, rng)}||"
                       f"ADT^{event}^ADT_{'A01' if event in ('A01','A04') else event}|MSG{ctrl:08d}|P|2.5.1")
                evn = f"EVN|{event}|{ts(when, rng)}"
                pid = ("PID|1||" + pid3 + "||" +
                       f"{esc(fam)}^{esc(giv[0])}^{esc(' '.join(giv[1:]))}||{dob}|{sex}|||"
                       f"{esc(' '.join(addr.get('line', [])))}^^{esc(addr.get('city'))}^{esc(addr.get('state'))}^"
                       f"{esc(addr.get('postalCode'))}^{esc(addr.get('country'))}||||||||{ssn}")
                admit = ts(start, rng)
                disch = "" if (event != "A03" or rng.random() < 0.02) else ts(end, rng)
                unit = "WARD2" if event == "A02" else ("ED" if cls == "EMER" else ("WARD1" if cls == "IMP" else "OPD"))
                pv1 = (f"PV1|1|{pclass}|{unit}^^^{fac}^^^^^{esc(fac_name)}" + "|" * 16 +
                       f"{visit}" + "|" * 25 + f"{admit}|{disch if event == 'A03' else ''}")
                segments = [msh, evn, pid, pv1]
                if rng.random() >= 0.08:
                    for i, code in enumerate(conditions.get(enc["id"], [])[:5], start=1):
                        segments.append(f"DG1|{i}||{code['code']}^{esc(code.get('display'))}^SCT||{admit}|W")

                message = "\r".join(segments)
                month = when[:7].replace("-", "")
                by_month[month].append((when, message))
                if rng.random() < 0.03:  # re-sent duplicate
                    by_month[month].append((when, message))

    total = 0
    for month, msgs in by_month.items():
        msgs.sort(key=lambda m: m[0])
        with open(os.path.join(out, f"adt_{month}.hl7"), "w", encoding="utf-8", newline="") as f:
            for _, m in msgs:
                f.write(m + "\n")
        total += len(msgs)

    with open(os.path.join(out, "..", "hl7_ground_truth.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["legacy_mrn", "synthea_patient_id", "visit_number", "fhir_encounter_id", "facility"])
        w.writerows(truth)

    print(f"{total} messages, {len(by_month)} monthly files, {len(truth)} encounters, "
          f"{len({t[0] for t in truth})} patients")


if __name__ == "__main__":
    args = sys.argv[1:]
    since = SINCE_YEAR
    if "--since" in args:
        i = args.index("--since"); since = int(args[i + 1]); del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    main(args[0], args[1], since)
