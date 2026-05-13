import httpx
from math import radians, sin, cos, sqrt, atan2
from typing import Literal

from route import nearest_route_point

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

POI_TAGS: dict[str, list[tuple[str, str]]] = {
    "water": [
        ("amenity", "drinking_water"),
        ("amenity", "water_point"),
    ],
    "cafe": [
        ("amenity", "cafe"),
        ("amenity", "restaurant"),
        ("amenity", "fast_food"),
        ("amenity", "bar"),
    ],
    "bike_repair": [
        ("amenity", "bicycle_repair_station"),
        ("shop", "bicycle"),
    ],
    "toilet": [
        ("amenity", "toilets"),
    ],
    "supermarket": [
        ("shop", "supermarket"),
        ("shop", "convenience"),
    ],
    "gas_station": [
        ("amenity", "fuel"),
    ],
}

POIType = Literal[
    "water", "cafe", "bike_repair", "toilet", "supermarket", "gas_station"
]


class OverpassAPI:

    def __init__(self, user_agent: str = "cyclingroute-mcp/0.1"):
        self.headers = {"User-Agent": user_agent}

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> int:
        R = 6_371_000
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        )
        return round(2 * R * atan2(sqrt(a), sqrt(1 - a)))

    def _build_around_query(
        self, tags: list[tuple], radius_m: int, lat: float, lon: float
    ) -> str:
        tag_filters = "\n  ".join(
            f'node["{k}"="{v}"](around:{radius_m},{lat},{lon});' for k, v in tags
        )
        return f"[out:json][timeout:15];\n(\n  {tag_filters}\n);\nout body;"

    async def _query(self, overpass_ql: str) -> list[dict]:
        async with httpx.AsyncClient(headers=self.headers) as client:
            response = await client.post(
                OVERPASS_URL,
                data={"data": overpass_ql},
                timeout=20,
            )
            response.raise_for_status()
            return response.json().get("elements", [])

    def _parse_elements(
        self, elements: list[dict], ref_lat: float, ref_lon: float, poi_type: str
    ) -> list[dict]:
        results = []
        for el in elements:
            tags = el.get("tags", {})
            el_lat, el_lon = el["lat"], el["lon"]
            el_type = (
                tags.get("amenity")
                or tags.get("natural")
                or tags.get("shop")
                or "unknown"
            )
            results.append(
                {
                    "name": tags.get("name", el_type.replace("_", " ").title()),
                    "poi_type": poi_type,
                    "osm_type": el_type,
                    "lat": el_lat,
                    "lon": el_lon,
                    "distance_m": self._haversine(ref_lat, ref_lon, el_lat, el_lon),
                    "osm_id": el["id"],
                    "tags": {
                        k: v
                        for k, v in tags.items()
                        if k
                        in (
                            "name",
                            "description",
                            "access",
                            "fee",
                            "seasonal",
                            "opening_hours",
                            "website",
                            "phone",
                        )
                    },
                }
            )
        return results

    async def find_pois(
        self, lat: float, lon: float, radius_m: int, types: list[str]
    ) -> list[dict]:
        unknown = [t for t in types if t not in POI_TAGS]
        if unknown:
            raise ValueError(
                f"Unknown POI type(s): {unknown}. Valid types: {list(POI_TAGS)}"
            )

        all_tags = [tag for t in types for tag in POI_TAGS[t]]
        query = self._build_around_query(all_tags, radius_m, lat, lon)
        elements = await self._query(query)

        # tag each result back to its poi_type
        tag_to_type = {(k, v): t for t, tags in POI_TAGS.items() for k, v in tags}
        results = []
        for el in elements:
            tags = el.get("tags", {})
            poi_type = next(
                (
                    tag_to_type[(k, tags[k])]
                    for k, _ in all_tags
                    if k in tags and (k, tags[k]) in tag_to_type
                ),
                "unknown",
            )
            results.extend(self._parse_elements([el], lat, lon, poi_type))

        results.sort(key=lambda x: x["distance_m"])
        return results

    def _build_route_query(
        self,
        tags: list[tuple],
        buffer_m: int,
        sampled_points: list[dict],
    ) -> str:
        coord_chain = ",".join(f"{p['lat']},{p['lon']}" for p in sampled_points)
        tag_filters = "\n  ".join(
            f'{element_type}["{k}"="{v}"](around:{buffer_m},{coord_chain});'
            for k, v in tags
            for element_type in ("node", "way", "relation")
        )
        return f"[out:json][timeout:30];\n(\n  {tag_filters}\n);\nout center;"

    async def find_pois_along_route(
        self,
        route_points: list[dict],
        buffer_m: int,
        types: list[str],
    ) -> list[dict]:
        unknown = [t for t in types if t not in POI_TAGS]
        if unknown:
            raise ValueError(f"Unknown POI type(s): {unknown}. Valid: {list(POI_TAGS)}")

        all_tags = [tag for t in types for tag in POI_TAGS[t]]
        query = self._build_route_query(all_tags, buffer_m, route_points)
        elements = await self._query(query)

        tag_to_type = {(k, v): t for t, tags in POI_TAGS.items() for k, v in tags}

        results = []
        seen_ids = set()
        for el in elements:
            if el["id"] in seen_ids:
                continue
            seen_ids.add(el["id"])

            tags = el.get("tags", {})
            el_lat = el.get("lat") or el.get("center", {}).get("lat")
            el_lon = el.get("lon") or el.get("center", {}).get("lon")

            if el_lat is None or el_lon is None:
                continue

            poi_type = next(
                (
                    tag_to_type[(k, tags[k])]
                    for k, _ in all_tags
                    if k in tags and (k, tags[k]) in tag_to_type
                ),
                "unknown",
            )

            nearest = nearest_route_point(el_lat, el_lon, route_points)
            dist_to_route = self._haversine(
                el_lat, el_lon, nearest["lat"], nearest["lon"]
            )
            el_type = (
                tags.get("amenity")
                or tags.get("natural")
                or tags.get("shop")
                or "unknown"
            )

            results.append(
                {
                    "name": tags.get("name", el_type.replace("_", " ").title()),
                    "poi_type": poi_type,
                    "osm_type": el_type,
                    "lat": el_lat,
                    "lon": el_lon,
                    "route_distance_km": nearest["distance_km"],
                    "distance_to_route_m": round(dist_to_route),
                    "osm_id": el["id"],
                    "tags": {
                        k: v
                        for k, v in tags.items()
                        if k
                        in (
                            "name",
                            "description",
                            "access",
                            "fee",
                            "seasonal",
                            "opening_hours",
                            "website",
                        )
                    },
                }
            )

        results.sort(key=lambda x: x["route_distance_km"])
        return results
