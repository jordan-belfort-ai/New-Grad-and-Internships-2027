"""New-grad and internship tech roles from the public job index -> a GitHub-list README (Markdown tables).

Why (4 Nov): auto-updated GitHub job lists are a place job seekers and the developers who build job tools look daily
(newcomer lists reach 1-2k stars: vanshb03/New-Grad-2027 ~2.2k, speedyapply 2027 lists 400+ forks). Ours is generated
from ~1M postings read straight from employer ATS boards (nine ATSs), every company in the index, not a hand-kept
list, and every page links ats-jobs-api for the full data. GitHub writes outside oskarengl/jordan are refused from the
cloud, so the cloud writes the files here and the PC pushes them to jordan-belfort-ai/New-Grad-and-Internships-2027.

    SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python -P tools/grad_lists.py [--days 14]
    -> data/grad-lists/README.md, data/grad-lists/INTERNSHIPS.md, data/grad-lists/jobs.json
"""
import gzip
import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # in the published list repo geo.py sits next to this script
    from geo import country_codes
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "actors" / "ats-jobs"))
    from src.geo import country_codes  # noqa: E402

STORE = "https://api.apify.com/v2/key-value-stores/VFEsrfmHwQiuxShwN/records/"
OUT = Path(__file__).resolve().parent.parent / "data" / "grad-lists"
ACTOR = "https://apify.com/jordan-belfort/ats-jobs-api"

TECH = re.compile(r"\b(software|developer|programmer|programming|data|machine learning|ml|ai|sre|devops|devsecops|"
                  r"backend|back-end|frontend|front-end|full[- ]?stack|firmware|embedded|security|cyber\w*|cloud|"
                  r"infrastructure|platform|quant(itative)?|research scientist|analytics|computer|computing|qa|"
                  r"test automation|sdet|network|robotics|quantum|web|mobile|ios|android|silicon|asic|fpga|gpu|chip|"
                  r"hardware|it|systems engineer\w*|site reliability|product engineer|forward deployed|solutions engineer|"
                  r"applied scientist|research engineer|deep learning|llm|nlp|computer vision|logiciel|informatique|donn[ée]es|"
                  r"d[ée]veloppeur\w*|softwareentwickl\w*|entwickler\w*|informatik\w*)\b", re.I)
NOT_TECH = re.compile(r"\b(sales|account (executive|manager)|recruit\w*|nurse|nursing|driver|technician|mechanic|"
                      r"warehouse|retail|store|customer|marketing|hr|legal|finance|accounting|electrical|civil|"
                      r"mechanical|manufacturing|process|quality|construction|field|maintenance|chemical|building|highway|traffic|"
                      r"water|structural|geotechnical|environmental|hvac|doctor|participants?|consultant|designer|"
                      r"business analyst|operations|teacher|tutor|officer|guard|banking|data entry|juriste|jurist\w*|avocat|rechtsanw\w*)\b", re.I)
NEW_GRAD = re.compile(r"\b(new[- ]grad(uate)?s?|graduate|grad|entry[- ]level|early[- ]career|university|campus|"
                      r"junior|jr\.?|(engineer|developer|scientist|analyst) (i|1)|associate (software|data|ml|machine)|"
                      r"20(26|27)|early[- ]talent|rotational|graduate (scheme|programme|program)|trainee|absolvent\w*|"
                      r"berufseinsteiger\w*|einsteiger\w*|jeune[s]? dipl[oô]m[ée]\w*|recent grad\w*)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|ii|iii|iv|v|2|3|4|5|phd|postdoc\w*|"
                    r"clearance|ts/sci)\b", re.I)
INTERN = re.compile(r"\b(interns?|internships?|co-?op|werkstudent|working student|praktikum|praktikant\w*|summer analyst|"
                    r"(?<!-)stage|stagiaire|alternance|alternant\w*|apprenti\w*|duales studium|tirocinio|stagista|"
                    r"pr[aá]cticas|becari[oa]s?|stażysta|staż)\b", re.I)
REGIONS = [("United States", {"US"}), ("Canada", {"CA"}), ("UK & Ireland", {"GB", "IE"}),
           ("Europe", {"DE", "FR", "NL", "ES", "IT", "PL", "SE", "CH", "AT", "BE", "DK", "FI", "NO", "PT", "CZ", "RO",
                       "HU", "GR", "EE", "LT", "LV", "BG", "HR", "SK", "SI", "LU", "UA", "RS"}),
           ("India", {"IN"}), ("Asia-Pacific", {"SG", "AU", "NZ", "JP", "KR", "HK", "TW", "PH", "MY", "VN", "ID", "TH",
                                                 "CN"}),
           ("Latin America", {"BR", "MX", "AR", "CO", "CL", "PE", "UY", "CR"})]
PER_COMPANY = 6


def get(key: str) -> bytes:
    with urllib.request.urlopen(STORE + key, timeout=120) as r:
        return r.read()


def region(r: dict) -> str | None:
    codes = set(country_codes(r))
    for name, cc in REGIONS:
        if codes & cc:
            return name
    if r.get("remote") or r.get("workplaceType") == "remote" or re.search(r"\bremote\b", r.get("location") or "", re.I):
        return "Remote, other"
    return None


def kind(r: dict) -> str | None:
    t = r.get("title") or ""
    if not TECH.search(t) or NOT_TECH.search(t):
        return None
    if INTERN.search(t) or r.get("seniority") == "intern" or r.get("employmentType") == "internship":
        return "intern"
    if SENIOR.search(t):
        return None
    if NEW_GRAD.search(t):
        return "newgrad"
    # Tried 4 Nov: plain titles whose posting asks <= 1 year added 346 rows, but too many wrong ones ("Engineer 5",
    # clearance roles, a CT technologist): the years parse is too noisy for a list people trust. Titles only.
    return None


ALL: dict[int, list[dict]] = {}  # id(groups) -> every picked row before the per-company cap


def co_key(name: str | None) -> str:
    n = re.sub(r"^the\s+|[,.]|\s+(company|inc|corp|corporation|llc|ltd|group|plc|gmbh)$", "", (name or "").lower().strip())
    return re.sub(r"\s+(company|inc|corp|corporation|llc|ltd|group|plc|gmbh)$", "", n).strip()


def esc(s: str) -> str:
    s = (s or "").replace("|", "/").replace("\n", " ").replace("[", "(").replace("]", ")").replace("<", "(").replace(">", ")")
    return s.strip()[:90]


def salary(r: dict) -> str:
    lo, hi = r.get("salaryMin"), r.get("salaryMax")
    if not lo or r.get("salaryInterval") != "year" or lo < 1000:
        return ""
    s = f"{r.get('salaryCurrency') or ''} {int(lo) // 1000}k"
    return (s + (f"-{int(hi) // 1000}k" if hi and int(hi) // 1000 > int(lo) // 1000 else "")).strip()


def table(rows: list[dict]) -> list[str]:
    out = ["| Company | Role | Location | Salary | Posted |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        sal = ""
        sal = salary(r)
        locs = r.get("_locs") or [r.get("location") or ""]
        loc = "; ".join(esc(x) for x in locs[:3]) + (f" +{len(locs) - 3} more" if len(locs) > 3 else "")
        new = " 🆕" if r["publishedAt"] >= NEW_SINCE else ""
        out.append(f"| {esc(r.get('company'))} | [{esc(r['title'])}]({r['url']}){new} | {loc} | "
                   f"{sal.strip()} | {r['publishedAt'][:10]} |")
    return out


def page(title: str, intro: str, groups: dict[str, list[dict]], built: str, other: str) -> str:
    total = sum(len(v) for v in groups.values())
    lines = [f"# {title}", "", intro, "",
             f"**{total:,} roles**, posted in the last {DAYS} days, read straight from employer career pages "
             f"(Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, Teamtailor, Recruitee, Personio). "
             f"Rebuilt every day from an index of ~1M postings; this build {built[:16].replace('T', ' ')} UTC. {other}",
             "", "How it differs from hand-kept lists: nobody picks the companies. Every board in the index is read every "
             "day (15,000+ employers, from startups to NVIDIA and Boeing), outside the US too, so smaller employers and "
             "non-US roles show up the day they're posted. The whole list is also a JSON feed: [jobs.json](jobs.json).",
             "", "Every link goes to the employer's own posting, no aggregator in between. Newest first, at most "
             f"{PER_COMPANY} roles per company per region; one role open in several cities is one row. "
             "🆕 = posted in the last 2 days. Searchable version: " + SEARCH_URL, "",
             "Contents: " + " · ".join(f"[{k}](#{re.sub(r'[^a-z0-9 _-]', '', k.lower()).replace(' ', '-')})"
                                       f" ({len(v)})" for k, v in groups.items() if v), ""]
    count, label = defaultdict(int), {}
    for r in ALL[id(groups)]:
        c = co_key(r.get("company"))
        count[c] += 1
        label.setdefault(c, r.get("company") or "")
    top = [label[c] for c in sorted((c for c in count if c), key=lambda c: -count[c])[:12]]
    count = {label[c]: n for c, n in count.items() if c}
    if top:
        lines += ["Most roles this fortnight: " + ", ".join(f"{esc(c)} ({count[c]})" for c in top) + ".", ""]
    for name, rows in groups.items():
        if rows:
            lines += [f"## {name}", ""] + table(rows) + [""]
    lines += ["## How this list is made", "",
              "A script filters the daily index by title (tech roles; new-grad, junior, entry-level, \"Engineer I\" or "
              "internship wording; senior and numbered levels out) and by the posting's country. It misses roles whose "
              "titles don't say they are junior, and it can't tell if a posting is still open beyond today's board.",
              "",
              f"The same data, with filters (keywords, country, remote, salary, years of experience, any company "
              f"list), as JSON/CSV or an MCP tool: [ATS Jobs Search API on Apify]({ACTOR}), $1 per 1,000 jobs. Built by "
              "Jordan, an AI agent run by @oskarengl; corrections welcome as issues.", "",
              EXAMPLE[0], "", "```json", EXAMPLE[1], "```", ""]
    return "\n".join(lines)


DAYS = 14
SEARCH_URL = "https://jordan-belfort-ai.github.io/New-Grad-and-Internships-2027/"
EXAMPLE = ("For example, US entry-level software roles from the last two weeks, with descriptions:",
           '{"searchKeywords": ["software engineer"], "seniority": ["entry"], "countries": ["US"], '
           '"postedWithinDays": 14, "maxResults": 200, "includeDescription": true}')
NEW_SINCE = ""


def main() -> None:
    global DAYS
    global OUT, NEW_SINCE, SEARCH_URL, EXAMPLE
    if "--out" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--out") + 1])
    if "--days" in sys.argv:
        DAYS = int(sys.argv[sys.argv.index("--days") + 1])
    m = json.loads(get("MANIFEST"))
    since = (datetime.fromisoformat(m["builtAt"]) - timedelta(days=DAYS)).isoformat()
    NEW_SINCE = (datetime.fromisoformat(m["builtAt"]) - timedelta(days=2)).isoformat()
    picked = {"newgrad": defaultdict(list), "intern": defaultdict(list)}
    seen = {}
    for key in m["chunks"]:
        blob = get(key)
        for r in json.loads(gzip.decompress(blob) if blob[:2] == b"\x1f\x8b" else blob):
            if (r.get("publishedAt") or "") < since or not r.get("url"):
                continue
            k = kind(r)
            reg = k and region(r)
            if not reg:
                continue
            dup = (k, reg, (r.get("company") or "").lower(), r["title"].strip().lower())
            first = seen.get(dup)
            loc = (r.get("location") or "").strip()
            if first is not None:  # same role in another city: one row, newest posting's link
                if loc and loc not in first["_locs"]:
                    first["_locs"].append(loc)
                if r["publishedAt"] > first["publishedAt"]:
                    first.update({"url": r["url"], "publishedAt": r["publishedAt"]})
                continue
            r["_locs"] = [loc] if loc else []
            seen[dup] = r
            picked[k][reg].append(r)
    order = [n for n, _ in REGIONS] + ["Remote, other"]
    res = {}
    for k, by in picked.items():
        groups = {}
        for name in order:
            rows = sorted(by.get(name, []), key=lambda r: r["publishedAt"], reverse=True)
            per, kept = defaultdict(int), []
            for r in rows:
                c = co_key(r.get("company"))
                if per[c] < PER_COMPANY:
                    per[c] += 1
                    kept.append(r)
            groups[name] = kept
        res[k] = groups
        ALL[id(groups)] = [r for rows in by.values() for r in rows]
    OUT.mkdir(parents=True, exist_ok=True)
    if "--europe" in sys.argv:  # the European-Tech-Internships-2027 repo: UK, Ireland and the rest of Europe only
        eu = ["UK & Ireland", "Europe"]
        SEARCH_URL = "https://jordan-belfort-ai.github.io/European-Tech-Internships-2027/"
        EXAMPLE = ("For example, software internships and working-student roles in Germany, the Netherlands and the UK:",
                   '{"searchKeywords": ["software", "data", "machine learning"], "seniority": ["intern"], '
                   '"countries": ["DE", "NL", "GB"], "postedWithinDays": 14, "maxResults": 200}')
        res = {k: {g: v[g] for g in eu} for k, v in res.items()}
        groups = {f"{'Internships' if k == 'intern' else 'New grad'}: {g}": res[k][g] for k in ("intern", "newgrad") for g in eu}
        ALL[id(groups)] = [r for k in ("intern", "newgrad") for g in eu for r in picked[k].get(g, [])]
        (OUT / "README.md").write_text(page(
            "European tech internships and new-grad jobs 2027, updated daily",
            "Software engineering, data, ML, security and hardware internships, working-student roles and graduate jobs in "
            "the UK, Ireland and the rest of Europe, from 15,000+ company career pages. Nobody curates it by hand, so it "
            "doesn't wait for pull requests.", groups, m["builtAt"],
            "Worldwide lists: [New-Grad-and-Internships-2027](https://github.com/jordan-belfort-ai/New-Grad-and-Internships-2027)."), "utf8")
    else:
        (OUT / "README.md").write_text(page(
            "New Grad 2027 and entry-level tech jobs, updated daily",
            "New-grad, junior and entry-level software engineering, data, ML, security, hardware and infrastructure "
            "roles, worldwide, from 15,000+ company career pages.", res["newgrad"], m["builtAt"], "Internships: [INTERNSHIPS.md](INTERNSHIPS.md)."), "utf8")
        (OUT / "INTERNSHIPS.md").write_text(page(
            "Summer 2027 tech internships and co-ops, updated daily",
            "Software engineering, data, ML, security and hardware internships, co-ops and working-student roles, "
            "worldwide, from 15,000+ company career pages.",
            res["intern"], m["builtAt"], "New-grad roles: [README.md](README.md)."), "utf8")
    keep = ["company", "title", "location", "_locs", "allLocations", "remote", "salaryMin", "salaryMax", "salaryCurrency", "salaryInterval",
            "url", "publishedAt", "ats"]
    (OUT / "jobs.json").write_text(json.dumps({"builtAt": m["builtAt"], "days": DAYS, **{
        k: {g: [{f: r.get(f) for f in keep} for g_rows in [rows] for r in g_rows] for g, rows in v.items()}
        for k, v in res.items()}}, ensure_ascii=False, indent=0), "utf8")
    for k, v in res.items():
        print(k, {g: len(x) for g, x in v.items()})


if __name__ == "__main__":
    main()
