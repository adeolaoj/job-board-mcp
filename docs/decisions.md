# Design decisions

A record of the choices made while building this project and why. Every entry is
based on a real API response, not documentation alone.

## Data sources

**Official public job board APIs.** Greenhouse, Lever, and Ashbypublish unauthenticated job board endpoints meant to be read. Request volume is kept
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

**Compcny-specific metadata is ignored.** Addepar's "Job Board Function" field
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

## Tools

**`search_jobs` doesn't fetch descriptions; `get_job` calls the detail endpoint.**
Fetching `content=true` for every search would download every description for every
company on each cache refresh, mostly text never read. The detail endpoint returns
the same data for one job, and `get_job` works on its own without a prior search.

**Descriptions are double-escaped HTML.** Greenhouse `content` is HTML stored as escaped
text (`&lt;p&gt;`), with some entities escaped twice (`&amp;amp;`). Plain text requires:
unescape, strip tags, unescape again.

**`get_job` calls the detail endpoint for every ATS,** even though Lever's list already
includes descriptions. Keeping the same flow for every source was chosen over saving
one request.

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

## Testing

**Fixtures are a few real entries from a real response, unedited.** Picked on purpose
to include edge cases. Raw exploration downloads live in `test-files/` and are gitignored.