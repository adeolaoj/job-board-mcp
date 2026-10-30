# Design decisions

A record of the choices made while building this project and why. Every entry is
based on a real API response, not documentation alone.

## Data sources

**Official public job board APIs.** Greenhouse, Lever, and Ashby publish unauthenticated job board endpoints meant to be read. Request volume is kept
 low with a ~15 minute cache.
 **Company slugs must be checked, not guessed.**

## Greenhouse field mapping

| Normalized field | Greenhouse field | Why |
|---|---|---|
| `job_id` | `id` | The post ID. It appears in `absolute_url` and the detail endpoint takes it. `internal_job_id` identifies the internal job instead. |
| `title` | `title` | |
| `location` | `location.name` | `offices[].name` uses a different, longer format ("Edinburgh, Scotland, United Kingdom" vs "Edinburgh, UK"). |
| `url` | `absolute_url` | |
| `posted_at` | `first_published` | Present on all 114 Addepar jobs (checked 2026-10-29). |

**`updated_at` is ignored.** It changes whenever a recruiter edits anything, so sorting
by it would make old jobs look new. A job appearing in the response already means it's open.

**Company-specific metadata is ignored.** Addepar's "Job Board Function" field
(e.g. "Interns & New Grads") is a custom field. Other companies won't have it, so it
can't be part of a normalized format shared across sources.

## Same title, different jobs

The same title can appear more than once. Addepar's "AddeGrad Program (2027) - Client
Solutions Analyst" is listed in Salt Lake City and Edinburgh as two separate jobs
(different `internal_job_id`s) with different descriptions: US pay range and work
authorization vs UK right-to-work text. We track each post by its `id`, show both in
search results, and save each as its own Notion row, since you apply to a specific one.

## Lever field mapping

Verified against Zoox (a test case, not a target company). Unlike Greenhouse, the
response is a bare list, and every posting includes its full description.

| Normalized field | Lever field | Why |
|---|---|---|
| `job_id` | `id` | A UUID string. Greenhouse IDs are integers, so `job_id` is always a string. |
| `title` | `text` | |
| `location` | `categories.allLocations`, joined with `; ` | One Lever posting can list several cities, where Greenhouse (at Addepar) used separate posts. Joining them lets a location search match any city. |
| `remote` | `workplaceType` | `remote` → true, `onsite`/`hybrid` → false, anything else → null. Compared after lowercasing and removing hyphens, because the docs say `on-site` but the data says `onsite`. |
| `url` | `hostedUrl` | `applyUrl` is the same page plus `/apply`. |
| `posted_at` | `createdAt` | Milliseconds since 1970, in UTC. Greenhouse gives local time with an offset, so both are converted the same way. |

**No pagination needed.** `skip` and `limit` are optional; one request returned all
229 postings, and `skip=229` returned an empty list.

**Escaping differs from Greenhouse.** Lever's `\u003C` is JSON escaping, undone by the
JSON parser. Greenhouse's `&lt;` is HTML escaping inside the string, which we undo ourselves.

**`descriptionPlain` is incomplete.** Responsibilities and qualifications are in
`lists[].content` as HTML only, so `get_job` combines `descriptionPlain`, each list
(heading plus text with tags removed), and `additionalPlain`.

## Ashby field mapping

Verified against Deepgram on 2026-10-29: 200 OK, `{"jobs": [...], "apiVersion": "1"}`,
80 postings, every posting includes its full description (~1.4 MB total).

| Normalized field | Ashby field | Why |
|---|---|---|
| `job_id` | `id` | A UUID string, like Lever. |
| `title` | `title` | |
| `location` | `location` plus `secondaryLocations[].location`, joined with `; ` | Same idea as Lever's `allLocations`. 14 of 80 Deepgram postings have secondary locations. |
| `remote` | `workplaceType`, falling back to `isRemote` | `Remote` → true, `OnSite`/`Hybrid` → false, same rule as Lever. If `workplaceType` is null (5 of 80), use `isRemote`; if both are null, `remote` is null. `workplaceType` wins when they disagree: "Executive Coordinator" is `Hybrid` but `isRemote: true`. |
| `url` | `jobUrl` | `applyUrl` is the same page plus `/application`. |
| `posted_at` | `publishedAt` | ISO string in UTC with milliseconds (`2026-10-10T23:22:04.170+00:00`). Present on all 80. |

**No public detail endpoint.** `/posting-api/job-board/{org}/{id}` returns 401, so it's
not public, and `developers.ashbyhq.com` couldn't be reached to check for another. Ashby's
`get_job` reads the posting from the cached list instead. This is the one exception to
"`get_job` calls the detail endpoint for every ATS", forced by the API.

**`descriptionPlain` is complete.** Unlike Lever, it has the same content as
`descriptionHtml` (1,757 vs 1,719 words on one posting), and the HTML isn't escaped.
`get_job` uses it directly.

**`isListed` was true on all 80 postings.** Postings with `isListed: false` are skipped
in case another company returns unlisted ones.

**`?includeCompensation=true` exists** and adds a `compensation` object. Not used, since
salary isn't in the normalized format.

## Wrong slugs

Each ATS answers a wrong slug with a 404, in a different format. Any 404 means
"check this company's slug in `companies.yaml`", reported in the `errors` list.

| ATS | Status | Body |
|---|---|---|
| Greenhouse | 404 | `{"status":404,"error":"Job not found"}` (JSON) |
| Lever | 404 | `{"ok":false,"error":"Document not found"}` (JSON) |
| Ashby | 404 | `Not Found` (plain text, not JSON) |

Ashby's plain-text body means error handling must check the status code before trying
to parse JSON.

## Tools

**`search_jobs` doesn't fetch descriptions; `get_job` calls the detail endpoint.**
Fetching `content=true` for every search would download every description for every
company on each cache refresh, mostly text never read. The detail endpoint returns
the same data for one job, and `get_job` works on its own without a prior search.

**Descriptions are double-escaped HTML.** Greenhouse `content` is HTML stored as escaped
text (`&lt;p&gt;`), with some entities escaped twice (`&amp;amp;`). Plain text requires:
unescape, strip tags, unescape again.

**`get_job` calls the detail endpoint for every ATS that has one,** even though Lever's
list already includes descriptions. Keeping the same flow for every source was chosen
over saving one request. Ashby has no public detail endpoint, so it reads from the cached list.

## Lanes

**Three lanes: `deployment`, `pm`, `new_grad`.** Real data showed the original keyword
lists missed relevant roles: "AddeGrad Program (2027) - Client Solutions Analyst" matched
no lane, and "Product Manager - Early Career, AI Platform" missed `pm` because plain
"product manager" wasn't a keyword. Added: `product manager` (pm), `applied ai` and
`customer facing` (deployment).

**A job can match several lanes, so output uses `lanes` (a list).** The Notion `Lane`
property is multi-select, and `save_job_to_notion` takes a list of lanes.

**Matching splits titles into words.** The title and each keyword are lowercased and
split into words (letters and digits only, dropping punctuation), and a keyword matches
if its words appear in order in the title. This replaced two approaches that failed on
real titles:
- Substring matching: "grad" matched "Upgrade", "staff" matched "Staffing", "intern"
  matched "International".
- Regex word boundaries: `\bsr\.\b` can't match "Sr. Account", because there's no
  boundary between "." and the following space.

Splitting on punctuation also handles "Staff/Principal" (two words) and keywords next
to commas or dashes. Tradeoff: "grad program" no longer matches "AddeGrad Program";
`2027` catches that one.

**`program` is not a `new_grad` keyword.** It would tag every "Technical Program Manager".

**Years in `new_grad` (e.g. `2027`) need updating each hiring season.**

**`intern` is excluded.** Internships aren't a target.

**Contract roles are kept.** No `contract` exclude keyword.

**A keyword's words must be next to each other, in order.** "customer engineer" does
not match "Customer Success Engineer"; otherwise multi-word keywords would match words
scattered across a long title.

**Known gaps, found in Deepgram data (open):**
- "Research Staff, Voice AI Foundations" is excluded by `staff`, but "Research Staff"
  there is a job family, not a seniority level.
- "Customer Success Engineer (Scaled)" matches no lane. Possibly a deployment role.

## Testing

**Fixtures are a few real entries from a real response, unedited.** Picked on purpose
to include edge cases. Raw exploration downloads live in `test-files/` and are gitignored.

| Fixture | Source | Entries |
|---|---|---|
| `greenhouse_jobs.json` | Addepar list | 5: same-title separate jobs (SLC, Edinburgh), early-career PM, Applied AI engineer, `Sr.` title with "Remote, USA" |
| `greenhouse_job_detail.json` | Addepar detail | Double-escaped HTML `content` |
| `lever_jobs.json` | Zoox list | 4: `onsite`, `hybrid`, a TPM matching `pm`, a 3-city `Staff/Principal` posting |
| `lever_job_detail.json` | Zoox detail | `lists[]` HTML that `descriptionPlain` leaves out |
| `ashby_jobs.json` | Deepgram list | 5: `forward-deployed` hyphen match (OnSite), `Senior` FDE with null `workplaceType` and `isRemote`, `Hybrid` vs `isRemote: true` conflict, "Research Staff" with 2 secondary locations, "Customer Success Engineer" with no lane |

Ashby has no detail fixture because it has no public detail endpoint.
## Stretch goals

**First stretch goal: `add_company(careers_url)`.** Instead of editing `companies.yaml`
by hand, Claude finds companies (with its own web search) and calls this tool, which
works out the ATS and slug from a direct ATS URL (`job-boards.greenhouse.io/{token}`,
`jobs.lever.co/{company}`, `jobs.ashbyhq.com/{org}`), checks it with one real request,
and saves it only if that request succeeds. Claude handles fuzzy discovery; the server
handles the reliable parts. Comes after the core tools and ahead of the spec's
other stretch goals, because it solves a problem hit in real use.

Open questions: whether added companies go into `companies.yaml` (tracked) or a
gitignored local file, and whether to support careers pages that embed a board.

**Rejected: searching beyond a chosen list.** These APIs are per company; there is no
public endpoint to search across all boards, so any wider search means knowing slugs
in advance. Loading thousands of slugs from community lists would mean thousands of
requests per search, which breaks the low-volume principle and becomes crawling.
Job aggregator APIs were also rejected: many aggregators get their data by scraping,
and they usually require keys or payment. Guessing slugs is brute force.
