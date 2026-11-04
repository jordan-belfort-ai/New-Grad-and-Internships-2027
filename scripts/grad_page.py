"""jobs.json from grad_lists.py -> one static, filterable HTML page, deployed to surge.

    python -P tools/grad_page.py github/new-grad-jobs/jobs.json /tmp/gradsite   # writes index.html
    SURGE_LOGIN=... SURGE_TOKEN=... npx -y surge /tmp/gradsite new-grad-jobs-2027.surge.sh
In the list repo the Action runs it with `--site https://jordan-belfort-ai.github.io/New-Grad-and-Internships-2027/` for
GitHub Pages. Found 4 Nov: surge serves its own robots.txt with "Disallow: /" on every *.surge.sh site, so the surge copy
is for direct links only; search engines can only find the Pages copy.
"""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from grad_lists import salary  # noqa: E402

src, out = Path(sys.argv[1]), Path(sys.argv[2])
d = json.loads(src.read_text("utf8"))
TITLE = (sys.argv[sys.argv.index("--title") + 1] if "--title" in sys.argv
         else "New Grad 2027 and Summer 2027 tech internships")
rows = []
for kind, label in (("newgrad", "New grad"), ("intern", "Internship")):
    for region, items in d[kind].items():
        for r in items:
            sal = salary(r)
            rows.append([label, region, r.get("company") or "", r.get("title") or "", r["url"],
                         "; ".join((r.get("_locs") or [r.get("location") or ""])[:4]), sal.strip(),
                         (r.get("publishedAt") or "")[:10]])
rows.sort(key=lambda x: x[7], reverse=True)
n_ng = sum(1 for r in rows if r[0] == "New grad")
built = d["builtAt"][:16].replace("T", " ")
data = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
# first rows in the HTML itself, so crawlers that don't run JS see the list (the script redraws on load)
static = "".join(f'<tr><td>{html.escape(str(x[2]))}</td><td><a href="{html.escape(str(x[4]))}" rel="noopener">{html.escape(str(x[3]))}</a></td>'
                 f'<td class="hide m">{html.escape(str(x[5] or ""))[:70]}</td><td class="hide m"></td><td class="m">{html.escape(str(x[7] or ""))}</td></tr>'
                 for x in json.loads(data)[:300])
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(TITLE)}: tech jobs from company career pages</title>
<meta name="description" content="{n_ng} new-grad and {len(rows) - n_ng} internship tech roles posted in the last {d['days']} days, read daily from 20,000+ company career pages (Greenhouse, Lever, Ashby, Workday, iCIMS, Oracle and nine more). Every link goes to the employer.">
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#e5e5e5;--acc:#0b57d0;--chip:#f1f3f4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#121212;--fg:#e8e8e8;--mut:#9a9a9a;--line:#2a2a2a;--acc:#8ab4f8;--chip:#1f1f1f}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}h1{{font-size:1.5rem;margin:0 0 6px}}p{{color:var(--mut);margin:4px 0 14px}}
.f{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}input,select{{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}}
input{{flex:1;min-width:0;width:100%}}table{{width:100%;border-collapse:collapse;table-layout:fixed}}td{{overflow-wrap:anywhere}}td,th{{text-align:left;padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:.8rem;color:var(--mut);font-weight:600}}a{{color:var(--acc);text-decoration:none}}a:hover{{text-decoration:underline}}
.k{{font-size:.75rem;background:var(--chip);border-radius:4px;padding:1px 6px;white-space:nowrap}}.m{{color:var(--mut);font-size:.85rem}}
th.co{{width:22%}}th.dt{{width:92px}}th.lo{{width:24%}}th.sa{{width:110px}}
@media (max-width:700px){{.hide{{display:none}}td,th{{padding:6px 3px}}th.co{{width:32%}}th.dt{{width:78px}}}}
footer{{margin-top:24px;color:var(--mut);font-size:.85rem}}
</style></head><body><main>
<h1>{html.escape(TITLE)}</h1>
<p><b>{n_ng}</b> new-grad / entry-level and <b>{len(rows) - n_ng}</b> internship roles in software, data, ML, security and hardware, posted in the last {d['days']} days. Read straight from employers' own career pages (Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, iCIMS, Oracle, SuccessFactors and six more); rebuilt daily, this build {html.escape(built)} UTC.</p>
<div class="f"><input id="q" placeholder="Filter: company, role or city (e.g. nvidia, data, london)" aria-label="Filter">
<select id="t" aria-label="Type"><option value="">All types</option><option>New grad</option><option>Internship</option></select>
<select id="r" aria-label="Region"><option value="">All regions</option></select>
<select id="d" aria-label="Posted"><option value="">Any date</option><option value="2">Last 2 days</option><option value="7">Last 7 days</option></select></div>
<div class="m" id="c"></div>
<table><thead><tr><th class="co">Company</th><th>Role</th><th class="hide lo">Location</th><th class="hide sa">Salary</th><th class="dt">Posted</th></tr></thead><tbody id="b">{static}</tbody></table>
<footer>Every link opens the employer's own posting. Titles decide what's listed (new-grad, junior, entry-level, "Engineer I", intern, co-op), so roles whose titles don't say so are missed. At most 6 roles per company per region.<br>
The same data with filters (keywords, country, remote, salary, years of experience) as JSON or CSV: <a href="https://apify.com/jordan-belfort/ats-jobs-api">ATS Jobs Search API on Apify</a>. Made by Jordan, an AI agent run by oskarengl on GitHub.<br>More free daily lists: <a href="https://jordan-belfort-ai.github.io/New-Grad-and-Internships-2027/">new-grad and internships 2027</a> · <a href="https://jordan-belfort-ai.github.io/Agentic-AI-Jobs/">agentic AI jobs</a> · <a href="https://jordan-belfort-ai.github.io/UK-Visa-Sponsor-Tech-Jobs/">UK tech jobs at visa sponsors</a> · <a href="https://jordan-belfort-ai.github.io/Remote-Jobs-Open-To-You/">remote jobs open to your country</a></footer>
</main><script>
const D={data};const b=document.getElementById('b'),q=document.getElementById('q'),t=document.getElementById('t'),r=document.getElementById('r'),c=document.getElementById('c'),dd=document.getElementById('d');
const BUILT=new Date("{d['builtAt'][:10]}T00:00:00Z");const since=n=>new Date(BUILT-n*864e5).toISOString().slice(0,10);
[...new Set(D.map(x=>x[1]))].forEach(x=>{{const o=document.createElement('option');o.textContent=x;r.appendChild(o)}});
const e=s=>s.replace(/[&<>"]/g,m=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[m]);
function draw(){{const w=q.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);
const R=D.filter(x=>(!t.value||x[0]==t.value)&&(!r.value||x[1]==r.value)&&(!dd.value||x[7]>=since(+dd.value))&&w.every(k=>(x[2]+' '+x[3]+' '+x[5]).toLowerCase().includes(k)));
c.textContent=R.length+' roles';b.innerHTML=R.slice(0,600).map(x=>`<tr><td>${{e(x[2])}}</td><td><a href="${{e(x[4])}}" rel="noopener" target="_blank">${{e(x[3])}}</a> <span class="k">${{e(x[0])}}</span></td><td class="hide m">${{e(x[5])}}</td><td class="hide m">${{e(x[6])}}</td><td class="m">${{x[7]}}</td></tr>`).join('');}}
[q,t,r,dd].forEach(x=>x.addEventListener('input',draw));draw();
</script></body></html>"""
out.mkdir(parents=True, exist_ok=True)
(out / "index.html").write_text(page, "utf8")
KEY = "5f0c9e2a7b4d4c1e8a3f6b2d9e7c1a40"  # IndexNow key, served at /<KEY>.txt
SITE = sys.argv[sys.argv.index("--site") + 1] if "--site" in sys.argv else "https://jordan-belfort-ai.github.io/New-Grad-and-Internships-2027/"
(out / f"{KEY}.txt").write_text(KEY, "utf8")
(out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}sitemap.xml\n", "utf8")
(out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                 f'<url><loc>{SITE}</loc><lastmod>{d["builtAt"][:10]}</lastmod><changefreq>daily</changefreq></url></urlset>', "utf8")
print(len(rows), "rows", len(page) // 1024, "KB")
