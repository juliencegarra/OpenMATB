# Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

"""
Rendering abstraction layer for pyglet 2.x migration.

Uses a custom vec2 shader for 2D colored rendering, with a ShaderGroup
that binds the program during batch.draw().
"""

from __future__ import annotations

from typing import Any

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

_program: ShaderProgram | None = None


class ShaderGroup(Group):
    """Group that binds the 2D shader program during batch rendering."""

    def __init__(self, program: ShaderProgram, order: int = 0, parent: Group | None = None) -> None:
        super().__init__(order=order, parent=parent)
        self.program: ShaderProgram = program

    def set_state(self) -> None:
        self.program.bind()
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def unset_state(self) -> None:
        glDisable(GL_BLEND)
        self.program.unbind()

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, ShaderGroup)
            and self.program == other.program
            and self.order == other.order
            and self.parent == other.parent
        )

    def __hash__(self) -> int:
        return hash((self.program, self.order, self.parent))


def get_program() -> ShaderProgram:
    """Return a cached ShaderProgram singleton for 2D colored vertices."""
    global _program
    if _program is None:
        vert_shader = Shader(_VERTEX_SHADER_SRC, "vertex")
        frag_shader = Shader(_FRAGMENT_SHADER_SRC, "fragment")
        _program = ShaderProgram(vert_shader, frag_shader)
    return _program


def get_group(order: int = 0, parent: Group | None = None) -> ShaderGroup:
    """Return a ShaderGroup bound to the 2D shader program."""
    return ShaderGroup(get_program(), order=order, parent=parent)


def quad_indices(n: int) -> list[int]:
    """Generate triangle indices for n/4 quads."""
    indices: list[int] = []
    for i in range(0, n, 4):
        indices.extend([i, i + 1, i + 2, i, i + 2, i + 3])
    return indices


def polygon_indices(n: int) -> list[int]:
    """Generate triangle fan indices for a convex polygon with n vertices."""
    indices: list[int] = []
    for i in range(1, n - 1):
        indices.extend([0, i, i + 1])
    return indices


