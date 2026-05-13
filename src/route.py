import gpxpy
from math import radians, sin, cos, sqrt, atan2


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def parse_gpx(gpx_string: str) -> list[dict]:
    """Parse a GPX string into a list of {lat, lon, distance_km} points."""
    gpx = gpxpy.parse(gpx_string)
    points = []
    cumulative = 0.0

    for track in gpx.tracks:
        for segment in track.segments:
            for i, pt in enumerate(segment.points):
                if i > 0:
                    prev = segment.points[i - 1]
                    cumulative += haversine(
                        prev.latitude, prev.longitude, pt.latitude, pt.longitude
                    )
                points.append(
                    {
                        "lat": pt.latitude,
                        "lon": pt.longitude,
                        "distance_km": round(cumulative / 1000, 3),
                    }
                )

    return points


def downsample(points: list[dict], interval_m: float = 100.0) -> list[dict]:
    """Keep one point every interval_m meters to limit Overpass query size."""
    if not points:
        return []
    sampled = [points[0]]
    last_dist = 0.0
    for pt in points[1:]:
        dist = pt["distance_km"] * 1000
        if dist - last_dist >= interval_m:
            sampled.append(pt)
            last_dist = dist
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled


def nearest_route_point(
    poi_lat: float, poi_lon: float, route_points: list[dict]
) -> dict:
    """Return the route point closest to a POI, with its distance_km along the route."""
    best = min(
        route_points,
        key=lambda p: haversine(poi_lat, poi_lon, p["lat"], p["lon"]),
    )
    return best


def find_dry_sections(
    route_points: list[dict],
    pois: list[dict],
    max_distance_m: float,
) -> list[dict]:
    """
    Find sections of the route where no POI is within max_distance_m.
    Returns gaps as {start_km, end_km, length_km}.
    """
    # Mark each route point as covered or not
    covered_at = set()
    for poi in pois:
        ref_km = poi["route_distance_km"]
        for pt in route_points:
            if abs(pt["distance_km"] - ref_km) * 1000 <= max_distance_m:
                covered_at.add(pt["distance_km"])

    gaps = []
    gap_start = None
    for pt in route_points:
        if pt["distance_km"] not in covered_at:
            if gap_start is None:
                gap_start = pt["distance_km"]
        else:
            if gap_start is not None:
                gaps.append(
                    {
                        "start_km": round(gap_start, 2),
                        "end_km": round(pt["distance_km"], 2),
                        "length_km": round(pt["distance_km"] - gap_start, 2),
                    }
                )
                gap_start = None

    if gap_start is not None:
        gaps.append(
            {
                "start_km": round(gap_start, 2),
                "end_km": round(route_points[-1]["distance_km"], 2),
                "length_km": round(route_points[-1]["distance_km"] - gap_start, 2),
            }
        )

    return sorted(gaps, key=lambda g: g["length_km"], reverse=True)
