# Campfire income statement

A small Python application for the [Campfire take-home](https://github.com/Campfire-eng/income-statement-take-home).
The accounting engine uses exact integer cents. FastAPI will serve JSON and a Jinja2 page from one process.

## Development setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked
```

Implementation is being built in order: accounting engine, API, server-rendered design, then final review and documentation.
