"""New-grad and internship tech roles from the public job index -> a GitHub-list README (Markdown tables).

Why (4 Nov): auto-updated GitHub job lists are a place job seekers and the developers who build job tools look daily
(newcomer lists reach 1-2k stars: vanshb03/New-Grad-2027 ~2.2k, speedyapply 2027 lists 400+ forks). Ours is generated
from ~1.3M postings read straight from employer ATS boards (nine ATSs), every company in the index, not a hand-kept
list, and every page links ats-jobs-api for the full data. GitHub writes outside oskarengl/jordan are refused from the
cloud, so the cloud writes the files here and the PC pushes them to jordan-belfort-ai/New-Grad-and-Internships-2027.

    SSL_CERT_FILE=/root/.ccr/ca-bundle.crt python -P tools/grad_lists.py [--days 14]
    -> data/grad-lists/README.md, data/grad-lists/INTERNSHIPS.md, data/grad-lists/jobs.json
"""
import gzip
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from itertools import chain
from datetime import datetime, timedelta, timezone
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
                      r"business analyst|operations|teacher|tutor|officer|guard|banking|data entry|juriste|jurist\w*|avocat|rechtsanw\w*|"
                      r"counsel|attorney|lawyer|law|radiolog\w*|physician|medical|clinical|instructor|teaching|adjunct|"
                      r"credit|accountant|accounts|auditor|audit|buyer|acheteur\w*|purchas\w*|procurement|business develop\w*|"
                      r"bdr|sdr|logistics|content|editor|media|product developer|selecci[oó]n|labell?er|labell?ing|"
                      r"cost|crm|fx|hiring event|security officers?|security specialist|summer analyst|"
                      r"gerente|construcci[oó]n|el[ée]ctrico|founding|head of)\b|^copy of\b", re.I)
NEW_GRAD = re.compile(r"\b(new[- ]grad(uate)?s?|graduate|grad|entry[- ]level|early[- ]career|university|campus|"
                      r"junior|jr\.?|(engineer|developer|scientist|analyst) (i|1)|associate (software|data|ml|machine)|"
                      r"20(26|27)|early[- ]talent|rotational|graduate (scheme|programme|program)|trainee|absolvent\w*|"
                      r"berufseinsteiger\w*|einsteiger\w*|jeune[s]? dipl[oô]m[ée]\w*|recent grad\w*)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|ii|iii|iv|v|2|3|4|5|phd|postdoc\w*|"
                    r"clearance|ts/sci|top secret|mid|regular|experienced)\b", re.I)
INTERN = re.compile(r"\b(interns?|internships?|co-?op|werkstudent|working student|praktikum|praktikant\w*|summer analyst|"
                    r"(?<!-)stage|stagiaire|alternance|alternant\w*|apprenti\w*|duales studium|tirocinio|stagista|"
                    r"pr[aá]cticas|becari[oa]s?|stażysta|staż|placement|co[- ]op|fellowship|residency|"
                    r"(undergraduate|graduate) research associate)\b", re.I)
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
    # the printed (primary) location decides first: Nitro's Porto internship also lists Dublin and sat under
    # UK & Ireland (4 Nov audit); all sites only when the primary one names no country
    codes = set(country_codes({"location": r.get("location"), "country": r.get("country")})) or set(country_codes(r))
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
    years = re.findall(r"\b20(\d\d)\b", t)
    if years and max(int(y) for y in years) < 27:  # "New College Grad 2026", "Mars 2026" in a 2027 list (4 Nov audit)
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
        new = " 🆕" if r["publishedAt"] >= NEW_SINCE and not r.get("_old") else ""
        out.append(f"| {esc(r.get('company'))} | [{esc(r['title'])}]({r['url']}){new} | {loc} | "
                   f"{sal.strip()} | {r['publishedAt'][:10]} |")
    return out


def page(title: str, intro: str, groups: dict[str, list[dict]], built: str, other: str) -> str:
    total = sum(len(v) for v in groups.values())
    lines = [f"# {title}", "", intro, "",
             f"**{total:,} roles**, posted in the last {DAYS} days, read straight from employer career pages "
             f"(Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, iCIMS, Oracle, SuccessFactors and more). "
             f"Rebuilt every day from an index of ~1.3M postings; this build {built[:16].replace('T', ' ')} UTC. {other}",
             "", "How it differs from hand-kept lists: nobody picks the companies. Every board in the index is read every "
             "day (20,000+ employers, from startups to NVIDIA and Boeing), outside the US too, so smaller employers and "
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


def amazon_rows() -> list[dict]:
    """Amazon hires students through amazon.jobs, not an ATS in the index. Its search.json is public (robots.txt only
    blocks /internal) and dated; a few early-career queries, newest first, ~30 GETs (4 Nov)."""
    seen, out = set(), []
    for q in ("intern", "early career", "2027", "university", "graduate"):
        for offset in range(0, 700, 100):
            url = (f"https://www.amazon.jobs/en/search.json?base_query={urllib.parse.quote(q)}&result_limit=100"
                   f"&offset={offset}&sort=recent")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                jobs = json.loads(urllib.request.urlopen(req, timeout=60).read()).get("jobs") or []
            except Exception as e:
                print("amazon:", e)
                break
            for j in jobs:
                path = j.get("job_path") or ""
                if not path or path in seen:
                    continue
                seen.add(path)
                try:
                    pub = datetime.strptime(re.sub(r"\s+", " ", j.get("posted_date") or ""), "%B %d, %Y").isoformat() + "+00:00"
                except ValueError:
                    continue
                parts = [x.strip() for x in (j.get("location") or "").split(",") if x.strip()]
                loc = ", ".join(parts[::-1]) if parts else ""
                out.append({"company": "Amazon", "title": (j.get("title") or "").strip(), "location": loc,
                            "country": parts[0] if parts and len(parts[0]) == 2 else None,
                            "url": "https://www.amazon.jobs" + path, "publishedAt": pub, "ats": "amazon"})
            if len(jobs) < 100:
                break
    return out


def microsoft_rows() -> list[dict]:
    """Microsoft's careers site (Eightfold) answers /api/pcsx/search keyless, and its robots.txt allows /api/pcsx
    explicitly (4 Nov). 10 positions a page; a few student queries, ~30 GETs, dated by postedTs."""
    seen, out = set(), []
    for q in ("intern", "university", "new graduate", "early career"):
        for start in range(0, 300, 10):
            url = ("https://apply.careers.microsoft.com/api/pcsx/search?domain=microsoft.com&location=&num=10"
                   f"&query={urllib.parse.quote(q)}&start={start}")
            pos = None
            for wait in (2, 30):  # it answers 429 to bursts: one slow page at a time, one back-off
                time.sleep(wait)
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    pos = (json.loads(urllib.request.urlopen(req, timeout=60).read()).get("data") or {}).get("positions") or []
                    break
                except Exception as e:
                    print("microsoft:", e)
            if pos is None:
                return out
            for j in pos:
                if j.get("id") in seen or not j.get("postedTs"):
                    continue
                seen.add(j.get("id"))
                locs = [", ".join([x.strip() for x in l.split(",")][::-1]) for l in j.get("locations") or []]
                locs = [l.replace("Multiple Locations, Multiple Locations, ", "") for l in locs]
                std = j.get("standardizedLocations") or []
                out.append({"company": "Microsoft", "title": (j.get("name") or "").strip(), "location": "; ".join(locs[:3]),
                            "country": std[0] if len(std) == 1 and len(std[0]) == 2 else None,
                            "url": "https://apply.careers.microsoft.com" + (j.get("positionUrl") or f"/careers/job/{j['id']}"),
                            "publishedAt": datetime.fromtimestamp(int(j["postedTs"]), tz=timezone.utc).isoformat(),
                            "workplaceType": j.get("workLocationOption"), "ats": "microsoft"})
            if len(pos) < 10:
                break
    return out


def firm_rows(built: str) -> list[dict]:
    """Jane Street, Citadel, D. E. Shaw and Two Sigma hire students only through their own sites (read by quant_list.py,
    which sits beside this script in the repo). Dated by the first build that saw each role, kept in jobs.json; a
    firm's first read is not marked new (4 Nov)."""
    try:
        import quant_list
    except ImportError:
        return []
    prev = {}
    if (OUT / "jobs.json").exists():
        d = json.loads((OUT / "jobs.json").read_text("utf8"))
        prev = {r["url"]: r["publishedAt"] for k in ("newgrad", "intern") for rows in (d.get(k) or {}).values() for r in rows}
    out = []
    for j in quant_list.own_site(built[:10], {}, True):
        dom = j["url"].split("/")[2]
        first_read = not any(u.split("/")[2] == dom for u in prev)
        cc = j["countries"]
        out.append({"company": j["company"], "title": j["title"], "location": j["location"], "country": cc[0] if len(cc) == 1 else None,
                    "url": j["url"], "publishedAt": prev.get(j["url"]) or built, "ats": j["ats"],
                    "employmentType": "internship" if j["category"] == "Internship" else None, "_old": first_read})
    return out


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
    def index_rows():
        for key in m["chunks"]:
            blob = get(key)
            yield from json.loads(gzip.decompress(blob) if blob[:2] == b"\x1f\x8b" else blob)

    for r in chain(index_rows(), firm_rows(m["builtAt"]), amazon_rows(), microsoft_rows()):
        if (r.get("publishedAt") or "") < since or not r.get("url"):
            continue
        k = kind(r)
        reg = k and region(r)
        if not reg:
            continue
        # "Hardware Engineer I (Full Time)" = "(Full-Time)", "Duolingo" = "Duolingo University": punctuation and
        # company forms don't make a second role (4 Nov audit)
        tkey = re.sub(r"\W+", "", re.sub(r"\(full[- ]?time\)", "", r["title"].lower()))
        dup = (k, reg, re.sub(r"\s+(university|careers|campus|early careers)$", "", co_key(r.get("company"))), tkey)
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
            "the UK, Ireland and the rest of Europe, from 20,000+ company career pages. Nobody curates it by hand, so it "
            "doesn't wait for pull requests.", groups, m["builtAt"],
            "Worldwide lists: [New-Grad-and-Internships-2027](https://github.com/jordan-belfort-ai/New-Grad-and-Internships-2027)."), "utf8")
    else:
        (OUT / "README.md").write_text(page(
            "New Grad 2027 and entry-level tech jobs, updated daily",
            "New-grad, junior and entry-level software engineering, data, ML, security, hardware and infrastructure "
            "roles, worldwide, from 20,000+ company career pages.", res["newgrad"], m["builtAt"], "Internships: [INTERNSHIPS.md](INTERNSHIPS.md)."), "utf8")
        (OUT / "INTERNSHIPS.md").write_text(page(
            "Summer 2027 tech internships and co-ops, updated daily",
            "Software engineering, data, ML, security and hardware internships, co-ops and working-student roles, "
            "worldwide, from 20,000+ company career pages.",
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
