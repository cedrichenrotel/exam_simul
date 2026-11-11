def py_graph_cycle_detector(graph: dict[int, list[int]]) -> bool:
    if graph == {}:
        return False
    file = set()
    termine = set()

    def _visiter(n) -> bool:
        file.add(n)
        for connect in graph.get(n, []):
            if connect in file:
                return True
            if connect not in termine and _visiter(connect):
                return True
        file.remove(n)
        termine.add(n)
        return False

    for noeud in graph:
        if noeud not in termine and _visiter(noeud):
            return True
    return False


if __name__ == "__main__":
    print(f"result generer: {py_graph_cycle_detector({0: [1], 1: [2], 2: [0]})}")
    print("result: True")