# cycling_pois-mcp

An MCP server that finds Points of Interest along cycling routes using OpenStreetMap data.

## What it does

Give it a GPX file and it queries the Overpass API for nearby POIs — water sources, cafes, supermarkets, gas stations — within a configurable distance of the route. It can also identify "dry sections": stretches of route with no POI of a given type.

## Tools

- **`find_pois`** — find POIs near a single coordinate
- **`find_pois_along_route`** — find POIs along a full GPX route, with optional dry section analysis

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # add your EMAIL
```

Add to your MCP client config:

```json
{
  "mcpServers": {
    "cycling_pois": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/cycling_pois-mcp",
        "fastmcp",
        "run",
        "src/server.py"
      ]
    }
  }
}
```

## Usage

Ask your LLM things like:
- *"What water sources are along this route?"*
- *"Where is the last cafe before the finish?"*
- *"What's the longest section without a supermarket?"*
- *"Can I find something to eat/drink around the 50km mark?"*