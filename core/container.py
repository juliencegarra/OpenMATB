# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

class Container:
    def __init__(self, name, l, b, w, h):
        self.name = name
        self.l = l  # left
        self.b = b  # bottom
        self.w = w  # width
        self.h = h  # height
        self.x1, self.y1, self.x2, self.y2 = self.l, self.b + self.h, self.l + self.w, self.b
        self.cx = self.x1 + (self.x2 - self.x1)/2
        self.cy = self.y1 + (self.y2 - self.y1)/2

    def __repr__(self):
        return f'Container(name={self.name}, l={self.l}, b={self.b}, w={self.w}, h={self.h})'

    def get_x1y1x2y2(self):             #JC: pour les méthodes du Core j'aurai systématiquement imposé le return type ex : def get_x1y1x2y2(self) -> Vector:
        return self.x1, self.y1, self.x2, self.y2

    def get_lbwh(self):
        return self.l, self.b, self.w, self.h

    def get_center(self):
        return self.cx, self.cy

    def get_reduced(self, width_ratio, height_ratio):
        # Get a centered reduced version of the current Container
        l = self.l + self.w * (1 - width_ratio) / 2
        b = self.b + self.h * (1 - height_ratio) / 2
        w = self.w * width_ratio
        h = self.h * height_ratio
        return Container(f'{self.name}_reduced', l, b, w, h)

    def get_translated(self, x=0, y=0):
        l = self.l + x
        b = self.b + y
        return Container(f'{self.name}_translated', l, b, self.w, self.h)
        
    def reduce_and_translate(self, width=1, height=1, x=0, y=0):
        _, _, w, h = self.get_reduced(width, height).get_lbwh()
        l = self.l + x * (self.w - w)
        b = self.b + y * (self.h - h)        
        return Container(f'{self.name}_reduced_translated', l, b, w, h)

    def contains_xy(self, x, y):
        return all([self.x1 <= x <= self.x2, self.y1 >= y >= self.y2])
