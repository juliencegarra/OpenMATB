# Copyright 2023-2024, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""
Rendering abstraction layer for pyglet 2.x migration.

Uses a custom vec2 shader for 2D colored rendering, with a ShaderGroup
that binds the program during batch.draw().
"""

from pyglet.gl import GL_BLEND, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA, glBlendFunc, glDisable, glEnable
from pyglet.graphics import Group
from pyglet.graphics.shader import Shader, ShaderProgram

_VERTEX_SHADER_SRC = """#version 150 core
    in vec2 position;
    in vec4 colors;
    out vec4 vertex_colors;

    uniform WindowBlock
    {
        mat4 projection;
        mat4 view;
    } window;

    void main()
    {
        gl_Position = window.projection * window.view * vec4(position, 0.0, 1.0);
        vertex_colors = colors;
    }
"""

_FRAGMENT_SHADER_SRC = """#version 150 core
    in vec4 vertex_colors;
    out vec4 final_color;

    void main()
    {
        final_color = vertex_colors;
    }
"""

_program = None


class ShaderGroup(Group):
    """Group that binds the 2D shader program during batch rendering."""

    def __init__(self, program, order=0, parent=None):
        super().__init__(order=order, parent=parent)
        self.program = program

    def set_state(self):
        self.program.bind()
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def unset_state(self):
        glDisable(GL_BLEND)
        self.program.unbind()

    def __eq__(self, other):
        return (
            isinstance(other, ShaderGroup)
            and self.program == other.program
            and self.order == other.order
            and self.parent == other.parent
        )

    def __hash__(self):
        return hash((self.program, self.order, self.parent))


def get_program():
    """Return a cached ShaderProgram singleton for 2D colored vertices."""
    global _program
    if _program is None:
        vert_shader = Shader(_VERTEX_SHADER_SRC, "vertex")
        frag_shader = Shader(_FRAGMENT_SHADER_SRC, "fragment")
        _program = ShaderProgram(vert_shader, frag_shader)
    return _program


def get_group(order=0, parent=None):
    """Return a ShaderGroup bound to the 2D shader program."""
    return ShaderGroup(get_program(), order=order, parent=parent)


def quad_indices(n):
    """Generate triangle indices for n/4 quads."""
    indices = []
    for i in range(0, n, 4):
        indices.extend([i, i + 1, i + 2, i, i + 2, i + 3])
    return indices


def polygon_indices(n):
    """Generate triangle fan indices for a convex polygon with n vertices."""
    indices = []
    for i in range(1, n - 1):
        indices.extend([0, i, i + 1])
    return indices


def line_loop_to_lines(vertices):
    """Convert a GL_LINE_LOOP vertex list to GL_LINES segments."""
    n = len(vertices) // 2
    result = []
    for i in range(n):
        x1, y1 = vertices[i * 2], vertices[i * 2 + 1]
        j = (i + 1) % n
        x2, y2 = vertices[j * 2], vertices[j * 2 + 1]
        result.extend([x1, y1, x2, y2])
    return result, n * 2


def colors_3to4(data, n):
    """Convert c3B (RGB) color data to c4B (RGBA) by adding alpha=255."""
    result = []
    for i in range(n):
        r, g, b = data[i * 3], data[i * 3 + 1], data[i * 3 + 2]
        result.extend([r, g, b, 255])
    return tuple(result)


def expand_colors_for_line_loop(colors, orig_n):
    """Expand colors from LINE_LOOP (n vertices) to LINES (2n vertices)."""
    bpv = 4
    result = []
    for i in range(orig_n):
        j = (i + 1) % orig_n
        result.extend(colors[i * bpv : (i + 1) * bpv])
        result.extend(colors[j * bpv : (j + 1) * bpv])
    return tuple(result)
