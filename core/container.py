# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from __future__ import annotations


class Container:
    def __init__(self, name: str, l: float, b: float, w: float, h: float) -> None:
        self.name: str = name
        self.l: float = l  # left
        self.b: float = b  # bottom
        self.w: float = w  # width
        self.h: float = h  # height
        self.x1: float = self.l
        self.y1: float = self.b + self.h
        self.x2: float = self.l + self.w
        self.y2: float = self.b
        self.cx: float = self.x1 + (self.x2 - self.x1) / 2
        self.cy: float = self.y1 + (self.y2 - self.y1) / 2

    def __repr__(self) -> str:
        return f"Container(name={self.name}, l={self.l}, b={self.b}, w={self.w}, h={self.h})"

    def get_x1y1x2y2(self) -> tuple[float, float, float, float]:
        return self.x1, self.y1, self.x2, self.y2

    def get_lbwh(self) -> tuple[float, float, float, float]:
        return self.l, self.b, self.w, self.h

    def get_center(self) -> tuple[float, float]:
        return self.cx, self.cy

    def get_reduced(self, width_ratio: float, height_ratio: float) -> Container:
        # Get a centered reduced version of the current Container
        l: float = self.l + self.w * (1 - width_ratio) / 2
        b: float = self.b + self.h * (1 - height_ratio) / 2
        w: float = self.w * width_ratio
        h: float = self.h * height_ratio
        return Container(f"{self.name}_reduced", l, b, w, h)

    def get_translated(self, x: float = 0, y: float = 0) -> Container:
        l: float = self.l + x
        b: float = self.b + y
        return Container(f"{self.name}_translated", l, b, self.w, self.h)

    def reduce_and_translate(self, width: float = 1, height: float = 1, x: float = 0, y: float = 0) -> Container:
        _, _, w, h = self.get_reduced(width, height).get_lbwh()
        l: float = self.l + x * (self.w - w)
        b: float = self.b + y * (self.h - h)
        return Container(f"{self.name}_reduced_translated", l, b, w, h)

    def contains_xy(self, x: float, y: float) -> bool:
        return all([self.x1 <= x <= self.x2, self.y1 >= y >= self.y2])
