# job-board-mcp

An [MCP](https://modelcontextprotocol.io) server that lets an AI assistant like Claude search open roles at a short list of companies through their **official, public job board APIs** (Greenhouse, Lever, and Ashby), filter them to my career lanes, and save matches to a Notion tracker.

> **Status:** in progress. This README describes what's planned. Each section will be filled in as it's built.

## Why official APIs instead of scraping

Many job tools scrape LinkedIn and Indeed, often using proxies to get around blocking. This project takes the opposite approach:

- **Official APIs only.** Many companies publish their openings through their applicant tracking system's public job board API. These need no authentication and are meant to be read.
- **A short list of companies I chose,** not the whole internet.
- **Light on requests.** Responses are cached so the APIs aren't hit repeatedly.

## Planned features

| Tool | What it does |
|---|---|
| `list_companies()` | Lists the configured companies and the ATS each one uses |
| `search_jobs(lane?, keywords?, location?, companies?, posted_within_days?)` | Finds matching jobs across all companies in one normalized format, newest first |
| `get_job(company, job_id)` | Returns the full job description as plain text |
| `save_job_to_notion(company, job_id, lane)` | Adds the job to a Notion "Jobs" database and skips duplicates |

Also planned:

- Configuration in YAML: `config/companies.yaml` for the companies to search and `config/lanes.yaml` for title keywords per lane
- About 15 minutes of response caching
- If one company's request fails, the error is reported and results from the other companies still come back
- Unit tests that run against saved API responses

## Coming soon

- Setup (Python environment, Notion integration, Claude Desktop config)
- Example prompts
- Architecture diagram
- Demo GIF

## License

[MIT](LICENSE)
