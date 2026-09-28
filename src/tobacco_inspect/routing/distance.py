"""Road-network drive-time matrix via OSMnx/NetworkX, cached to data/interim.

Straight-line distance misleads in Pittsburgh (rivers, bridges, hills).

TODO: implement; provide a haversine fallback for offline tests.
"""


def travel_time_matrix(config, points):
    raise NotImplementedError
