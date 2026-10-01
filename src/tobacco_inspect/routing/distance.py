"""Road-network drive-time matrix via OSMnx/NetworkX, cached to data/interim.

Straight-line distance misleads in Pittsburgh (rivers, bridges, hills), so the default is the
OSM drive network with free-flow speeds. A haversine fallback (circuity factor and a fixed urban
speed) keeps tests offline and is used when the network download fails. Times are in minutes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_KM = 6371.0088
CIRCUITY = 1.35  # road distance / straight-line distance, typical urban value (assumption)
URBAN_KMH = 25.0  # average urban drive speed including signals (assumption)


def haversine_minutes(lons, lats, circuity: float = CIRCUITY, kmh: float = URBAN_KMH) -> np.ndarray:
    """Pairwise drive-time estimate (minutes) from coordinates."""
    lon, lat = np.radians(np.asarray(lons, float)), np.radians(np.asarray(lats, float))
    dlat, dlon = lat[:, None] - lat[None, :], lon[:, None] - lon[None, :]
    a = np.sin(dlat / 2) ** 2 + np.cos(lat)[:, None] * np.cos(lat)[None, :] * np.sin(dlon / 2) ** 2
    km = 2 * EARTH_KM * np.arcsin(np.sqrt(a))
    return km * circuity / kmh * 60.0


def _osm_matrix(lons, lats, graph_path, polygon):
    """Shortest drive times (minutes) between points on the OSM network (directed)."""
    import networkx as nx
    import osmnx as ox

    ox.settings.cache_folder = str(graph_path.parent / "osmnx_cache")
    if graph_path.exists():
        g = ox.load_graphml(graph_path)
    else:
        g = ox.graph_from_polygon(polygon, network_type="drive", simplify=True)
        g = ox.add_edge_speeds(g)
        g = ox.add_edge_travel_times(g)
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(g, graph_path)
    nodes = ox.distance.nearest_nodes(g, X=list(lons), Y=list(lats))
    unique = sorted(set(nodes))
    minutes = {}
    for src in unique:
        lengths = nx.single_source_dijkstra_path_length(g, src, weight="travel_time")
        minutes[src] = {dst: lengths.get(dst, np.inf) / 60.0 for dst in unique}
    n = len(nodes)
    mat = np.zeros((n, n))
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            mat[i, j] = 0.0 if a == b else minutes[a][b]
    return mat


def travel_time_matrix(
    config, points: pd.DataFrame, *, use_osm: bool = True, refresh: bool = False
):
    """Drive-time matrix (minutes) for `points` (columns lon, lat), row/col order preserved.

    Cached at data/interim/travel_time_matrix.csv.gz keyed by the point list. Returns
    (matrix, source) where source is "osm" or "haversine".
    """
    cache = config.path("interim") / "travel_time_matrix.csv.gz"
    sig = "|".join(f"{x:.5f},{y:.5f}" for x, y in zip(points["lon"], points["lat"], strict=True))
    sig_path = cache.with_suffix(".sig")
    if cache.exists() and sig_path.exists() and sig_path.read_text() == sig and not refresh:
        return pd.read_csv(cache, header=None).to_numpy(), "osm"
    lons, lats = points["lon"].to_numpy(), points["lat"].to_numpy()
    source, mat = "haversine", haversine_minutes(lons, lats)
    if use_osm:
        try:
            from tobacco_inspect.data import ingest

            bounds = ingest.fetch_boundaries(
                config.path("raw"),
                config.raw["data"]["state_fips"],
                int(config.raw["data"]["tiger_year"]),
            )
            place = ingest.read_zipped_shapefile(bounds["place"])
            place = place[place["GEOID"] == config.raw["data"]["city_place_geoid"]]
            polygon = place.geometry.union_all().buffer(0.01)  # small buffer so edge nodes connect
            mat = _osm_matrix(lons, lats, config.path("raw") / "osm_pgh_drive.graphml", polygon)
            mat = np.where(np.isfinite(mat), mat, haversine_minutes(lons, lats))
            source = "osm"
        except Exception as exc:  # network/Overpass problems must not break the pipeline
            print(f"OSM drive network unavailable ({exc}); using haversine estimate")
    if source == "osm":
        cache.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(mat).to_csv(cache, header=False, index=False, compression="gzip")
        sig_path.write_text(sig)
    return mat, source
