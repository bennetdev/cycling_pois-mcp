from fastmcp import FastMCP
from overpass import OverpassAPI, POIType
from dotenv import load_dotenv
import os

mcp = FastMCP(
    "cyclingroute",
    instructions="Find Places of Interest along the route like water sources, cafes and restaurants. Visualize them on the map.",
)

load_dotenv()
overpass = OverpassAPI(user_agent=f"cyclingroute-mcp/0.1 ({os.environ.get('EMAIL')})")


@mcp.tool()
async def find_pois(
    lat: float,
    lon: float,
    radius_m: int = 500,
    types: list[POIType] = ["water", "cafe", "supermarket", "gas_station"],
) -> list[dict]:
    """Find points of interest near a given coordinate.

    Args:
        lat: Latitude of the center point.
        lon: Longitude of the center point.
        radius_m: Search radius in meters (default 500).
        types: POI categories to search.
    """
    return await overpass.find_pois(lat, lon, radius_m, types)


from route import parse_gpx, downsample, find_dry_sections


@mcp.tool()
async def find_pois_along_route(
    gpx: str,
    buffer_m: int = 500,
    types: list[POIType] = ["water", "cafe"],
    include_dry_sections: bool = True,
) -> dict:
    """Find points of interest alongside a GPX route.

    Useful for questions like:
    - What water sources are along this route?
    - Will I find water around km 40-50?
    - What is the longest section without any cafe?
    - Where is the last water source before the finish?

    Args:
        gpx: Full GPX file content as a string.
        buffer_m: Max distance from the route in meters to include a POI (default 500).
        types: POI categories to search.
        include_dry_sections: If True, also return sections of the route with no POI of the requested types.
    """
    route_points = parse_gpx(gpx)
    total_km = route_points[-1]["distance_km"]
    sampled = downsample(route_points, interval_m=100)

    pois = await overpass.find_pois_along_route(sampled, buffer_m, types)

    result = {
        "total_km": round(total_km, 2),
        "route_points_sampled": len(sampled),
        "pois_found": len(pois),
        "pois": pois,
    }

    if include_dry_sections:
        gaps = find_dry_sections(route_points, pois, max_distance_m=buffer_m)
        result["dry_sections"] = gaps
        result["longest_dry_section_km"] = gaps[0]["length_km"] if gaps else 0.0

    return result


if __name__ == "__main__":
    mcp.run()
