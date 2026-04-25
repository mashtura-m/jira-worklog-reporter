# Jira Worklog Reporter

A small CLI tool that fetches Jira worklogs for a project, aggregates them, and writes an Excel report.

## Features

- Environment-driven configuration
- Jira REST API integration
- Worklog aggregation by Jira project and date range
- Excel report generation
- Local cache support

## Requirements

- Python 3.11+
- `python3-venv`
- `git` (for repository management and pushing to GitHub)

## Setup

From the project root:

```bash
cd jira-worklog-reporter
make install
```

This creates a virtual environment in `venv/` and installs dependencies from `requirements.txt`.

## Configuration

Copy `.env.example` to `.env` and set your Jira credentials and report parameters:

```bash
cp .env.example .env
```

Edit `.env` to include your Jira host, credentials, project key, and date range.

## Running

```bash
make run
```

The project uses the `.env` file to load configuration values automatically.

## Development

- `make install` — create venv and install dependencies
- `make run` — run the CLI tool
- `make clean` — remove the virtual environment

## GitHub

After installing `git`, initialize the repository and push to your private GitHub repo:

```bash
git init
git add .
git commit -m "Initial project setup with documentation"
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

## Notes

- Do not commit `.env` to GitHub.
- Keep your Jira API token secure.
