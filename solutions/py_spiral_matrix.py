def generate_spiral(n: int) -> list[list[int]]:
    if n < 1:
        return []
    grille = [[0] * n for _ in range(n)]
    total = n * n
    val = 1
    nord = 0
    est = n - 1
    sud = n - 1
    ouest = 0

    while val <= total:
        for col in range(ouest, est + 1):
            grille[nord][col] = val
            val += 1
        nord += 1
        for line in range(nord, sud + 1):
            grille[line][est] = val
            val += 1
        est -= 1
        for col in range(est, ouest - 1, - 1):
            grille[sud][col] = val
            val += 1
        sud -= 1
        for line in range(sud, nord - 1, - 1):
            grille[line][ouest] = val
            val += 1
        ouest += 1
    return grille


if __name__ == "__main__":
    print(f"sortie generer: {generate_spiral(3)}")
    print("sortie attendu: [[1, 2, 3], [8, 9, 4], [7, 6, 5]]")
