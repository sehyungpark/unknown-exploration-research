import unittest

from src.sensing import supercover_line


class SupercoverTests(unittest.TestCase):
    def test_endpoints_are_inclusive(self) -> None:
        self.assertEqual(
            supercover_line((2, 1), (2, 4)),
            ((2, 1), (2, 2), (2, 3), (2, 4)),
        )
        self.assertEqual(supercover_line((3, 3), (3, 3)), ((3, 3),))

    def test_corner_crossing_includes_both_side_cells(self) -> None:
        self.assertEqual(
            supercover_line((0, 0), (1, 1)),
            ((0, 0), (0, 1), (1, 0), (1, 1)),
        )

    def test_covered_set_is_symmetric(self) -> None:
        cells = tuple((row, col) for row in range(6) for col in range(6))
        for start in cells:
            for end in cells:
                with self.subTest(start=start, end=end):
                    forward = supercover_line(start, end)
                    reverse = supercover_line(end, start)
                    self.assertEqual(set(forward), set(reverse))
                    self.assertEqual(len(forward), len(set(forward)))


if __name__ == "__main__":
    unittest.main()
