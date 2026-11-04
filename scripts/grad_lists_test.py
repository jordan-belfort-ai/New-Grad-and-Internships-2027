"""Offline checks for grad_lists.kind(): python -P tools/grad_lists_test.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grad_lists import co_key, kind, salary  # noqa: E402

CASES = {
    "Software Engineer, New Grad 2027": "newgrad", "Junior Data Engineer": "newgrad", "Software Engineer I": "newgrad",
    "Entry-Level Software Engineer": "newgrad", "Associate Software Engineer": "newgrad",
    "Graduate Power Engineer": None, "Building Engineer I": None, "Senior Software Engineer": None,
    "Software Engineer II": None, "Full-Stack Engineer 4 (Java)": None, "Junior Account Executive": None,
    "Software Engineer": None, "Junior Business Analyst/Software Tester": None,
    "Avionics Engineer I - Top Secret Clearance": None, "Public Safety (Security) Officer": None,
    "Software Engineering Graduate Scheme 2027": "newgrad", "Trainee Software Developer (m/w/d)": "newgrad",
    "Absolvent Data Science (w/m/d)": "newgrad", "Ingénieur logiciel jeune diplômé": "newgrad",
    "Early Talent - Cloud Engineer": "newgrad", "Senior Trainee Manager": None,
    "Software Engineer Intern": "intern", "Summer 2027 Internship - Quantum Software": "intern",
    "Working Student - Data Analytics (m/f/d)": "intern", "Firmware Engineering Co-Op": "intern",
    "Data Scientist Assistant - Stage (6 mois) Mars 2027": "intern", "Addetto/a data entry junior": None,
    "Senior Scientist, Statistical Programming, Late-Stage Oncology": None,
    "NVIDIA 2027 Internships: Autonomous Vehicles and Robotics": "intern",
    "Marketing Intern": None, "Alternance - Juriste protection des données (H/F)": None, "Highway Engineering Intern": None,
}
bad = [(t, kind({"title": t}), want) for t, want in CASES.items() if kind({"title": t}) != want]
from grad_lists import esc  # noqa: E402
assert esc("[2027 Intern] <SWE> | Ops") == "(2027 Intern) (SWE) / Ops", esc("[2027 Intern] <SWE> | Ops")
assert co_key("The Boeing Company") == co_key("Boeing"), co_key("The Boeing Company")
assert salary({"salaryMin": 140000, "salaryMax": 140000, "salaryInterval": "year", "salaryCurrency": "USD"}) == "USD 140k"
assert salary({"salaryMin": 20, "salaryMax": 25, "salaryInterval": "year"}) == ""
for b in bad:
    print("FAIL", b)
print(f"{len(CASES) - len(bad)}/{len(CASES)} ok")
sys.exit(1 if bad else 0)
