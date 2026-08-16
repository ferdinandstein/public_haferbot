# Datei für ungenutzte Funktionen

from collections import deque

def order_clusters(clusters):
    """Sortiert Felder im Cluster nach Anfang bis Ende des Clusters"""
    ordered_clusters = []
    for cluster in clusters:
        start = cluster[0]
        for field in cluster:
            count = 0
            for x, y in [
                (0, 1),
                (0, -1),
                (1, 0),
                (-1, 0),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]:
                nx, ny = field[0] + x, field[1] + y
                if (nx, ny) in cluster:
                    count += 1
                    start = field
            if count == 1:
                break

        ordered_cluster = []
        queue = deque([start])
        visited = set()
        visited.add(start)
        while queue:
            current = queue.popleft()
            ordered_cluster.append(current)
            for x, y in [
                (0, 1),
                (0, -1),
                (1, 0),
                (-1, 0),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]:
                nx, ny = current[0] + x, current[1] + y
                if (nx, ny) in cluster and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    queue.append((nx, ny))
        ordered_clusters.append(ordered_cluster)
    return ordered_clusters
