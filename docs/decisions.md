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
I
## Tools

**`search_jobs` doesn't fetch descriptions; `get_job` calls the detail endpoint.**
Fetching `content=true` for every search would download every description for every
company on each cache refresh, mostly text never read. The detail endpoint returns
the same data for one job, and `get_job` works on its own without a prior search.

**Descriptions are double-escaped HTML.** Greenhouse `content` is HTML stored as escaped
text (`&lt;p&gt;`), with some entities escaped twice (`&amp;amp;`). Plain text requires:
unescape, strip tags, unescape again.

## Lanes

**Three lanes: `deployment`, `pm`, `new_grad`.** Real data showed the original keyword
lists miss roles like "AddeGrad Program (2027) - Client Solutions Analyst".

**A job can match several lanes, so output uses `lanes` (a list).** The Notion `Lane`
property is multi-select, and `save_job_to_notion` takes a list of lanes.

**Matching uses whole words and ignores case, on titles only.** Substring matching
caused false matches: "grad" in "Upgrade", "staff" in "Staffing", "intern" in
"International". Tradeoff: whole words are stricter, so "grad program" no longer matches
"AddeGrad Program". Years in `new_grad` (e.g. `2027`) need updating each hiring season.

**`program` is not a `new_grad` keyword.** It would tag every "Technical Program Manager".

**`intern` is excluded.** Internships aren't a target.

## Error handling

**A malformed job (e.g. no title) is skipped, not fatal.** The tool response includes a
`warnings` list so the skip is visible in conversation, and it's also logged to stderr
(stdout is reserved for the MCP protocol). Company-level failures go in an `errors` list,
and results from other companies still return.

## Testing

**Fixtures are a few real entries from a real response, unedited.** Picked on purpose
to include edge cases. Raw exploration downloads live in `test-files/` and are gitignored.