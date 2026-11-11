def prism_detector(grid: list[str], pattern: str) -> list[tuple[int, int, str]]:
    rst = []
    if grid == [] or pattern == "":
        return rst

    directions = [
        (1, 0, "H"),
        (0, 1, "V"),
        (1, 1, "D"),
        (-1, 1, "A"),
        (0, -1, "HR"),
        (-1, -1, "DR"),
        (-1, 0, "VR"),
        (1, -1, "AR"),
    ]
    lines = len(grid)
    cols = len(grid[0])

    for line in range(lines):
        for col in range(cols):
            for dir in directions:
                for k in range(len(pattern)):
                    pl = line + k * dir[1]
                    pc = col + k * dir[0]
                    if (
                        pl < 0
                        or pl >= lines
                        or pc < 0
                        or pc >= cols
                        or grid[pl][pc] != pattern[k]
                    ):
                        break
                else:
                    rst.append((line, col, dir[2]))
    return rst


if __name__ == "__main__":
    print(f"result: {prism_detector(['CAT', 'A..', 'T..'], 'CAT')}")
    print("[(0, 0, 'H'), (0, 0, 'V')]")
