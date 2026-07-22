# stat-gov-mcp

Local MCP server for the **Polish Central Statistical Office (GUS) Bank Danych Lokalnych (BDL)** — the definitive public source for Polish socioeconomic statistics: population, prices, business demographics, unemployment, GDP, at country / voivodeship / powiat / gmina resolution.

Part of the [honest-mcp family](https://github.com/bartosz-kuc?tab=repositories) of small, auditable, local-first MCP servers.

## Why

BDL contains tens of thousands of time series about Poland. Its web UI ([bdl.stat.gov.pl](https://bdl.stat.gov.pl/)) is powerful but slow to navigate when you know exactly what you want. The public REST API is the fast path but has enough concepts (subjects → variables → units → data) to make manual use annoying. This server lets your AI find the right variable and unit and pull the data — one conversation, done.

Same trust model as the rest of the family: data flows only between your machine and GUS.

## Features

Five tools:

- `search_subjects` — browse or search the subject tree (e.g., "CENY", "LUDNOŚĆ")
- `search_variables` — find data series in a subject
- `search_units` — find territorial units (voivodeship, powiat, gmina) by name and/or level
- `get_unit_details` — full record for a unit ID
- `get_data` — pull actual values for a variable across chosen units and year range

## Data source

- Endpoint: [bdl.stat.gov.pl/api/v1](https://bdl.stat.gov.pl/api/v1/) — GUS BDL public REST API
- No API key required for the free tier (5 req/sec, ~5000 req/day)
- Higher-volume tier available with free registration; not needed for typical interactive use

## Requirements

- Python 3.10+

## Setup

```bash
git clone https://github.com/bartosz-kuc/stat-gov-mcp.git
cd stat-gov-mcp
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Register with Claude Code:

```bash
claude mcp add stat-gov /absolute/path/to/venv/bin/python /absolute/path/to/server.py
```

Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "stat-gov": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

## Example usage

> "How has the average monthly wage changed in Mazowieckie over the last 10 years?"

Three-step: `search_variables(name="przeciętne wynagrodzenie")` → note variable ID → `search_units(name="mazowieckie", level=2)` → note unit ID → `get_data(variable_id=..., unit_ids=[...], year_from=2015)`.

> "Which voivodeships had the highest unemployment in 2024?"

`search_variables(name="stopa bezrobocia")` → `get_data(variable_id=..., year_from=2024, year_to=2024)` — default returns all voivodeships.

## Data flow

```
Your AI client
     ↕  MCP stdio
This server (Python, on your machine)
     ↕  HTTPS
bdl.stat.gov.pl (GUS)
```

No cloud middle. No telemetry.

## Author

**Bartosz Kuć** — Warsaw-based developer, JDG owner running [skanfirmy.pl](https://skanfirmy.pl).

- GitHub: https://github.com/bartosz-kuc

- Email: firma@bartosza.pl

## Consulting

Available for consulting on Polish tax and business integrations (KSeF, GUS/NFZ/GIOŚ APIs, mBank data), MCP server design, and AI-assisted tooling for JDGs and small teams. See **[skanfirmy.pl/uslugi](https://skanfirmy.pl/uslugi)** for productized packages (audit 3k PLN, setup 8-15k PLN, retainer 2-4k PLN/mo), or reach out via email.

## License

MIT — see [LICENSE](LICENSE).

## Related

- Part of the honest-mcp family — see the [family index](https://github.com/bartosz-kuc?tab=repositories).
