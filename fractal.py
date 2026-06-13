import moderngl_window as mglw
import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont

VERT = """
#version 330
in vec2 in_vert;
out vec2 v_uv;
void main() {
    v_uv = in_vert;
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

FRAG = """
#version 330
in vec2 v_uv;
out vec4 fragColor;

uniform vec2 center;
uniform float zoom;
uniform vec2 resolution;

vec3 palette(float t) {
    return 0.5 + 0.5 * cos(6.28318 * (t + vec3(0.0, 0.333, 0.667)));
}

void main() {
    vec2 aspect = vec2(resolution.x / resolution.y, 1.0);
    vec2 c = center + v_uv * aspect * zoom;

    vec2 z = vec2(0.0);
    float iter = 0.0;
    float maxIter = 256.0;

    for (float i = 0.0; i < 256.0; i++) {
        if (dot(z, z) > 4.0) break;
        z = vec2(z.x*z.x - z.y*z.y + c.x, 2.0*z.x*z.y + c.y);
        iter++;
    }

    if (iter >= maxIter) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    float smooth_iter = iter - log2(log2(dot(z, z))) + 4.0;
    float t = smooth_iter / maxIter;
    fragColor = vec4(palette(t), 1.0);
}
"""

OVERLAY_VERT = """
#version 330
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    v_uv = in_uv;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

OVERLAY_FRAG = """
#version 330
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D tex;
void main() {
    fragColor = texture(tex, v_uv);
}
"""

CONTROLS = [
    "Z         hold to zoom in",
    "Shift+Z   hold to zoom out",
    "Scroll    zoom in / out",
    "Drag      pan",
    "0         reset view",
]

def make_overlay_texture(ctx, lines, font_size=15):
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Courier.dfont", font_size)
    except Exception:
        font = ImageFont.load_default()

    padding = 10
    line_h = font_size + 4
    w = 260
    h = len(lines) * line_h + padding * 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w - 1, h - 1], fill=(0, 0, 0, 140))
    for i, line in enumerate(lines):
        draw.text((padding, padding + i * line_h), line, font=font, fill=(255, 255, 255, 230))

    data = img.tobytes()
    tex = ctx.texture((w, h), 4, data)
    tex.filter = moderngl.NEAREST, moderngl.NEAREST
    return tex, w, h


def make_cursor_texture(ctx, font_size=28):
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except Exception:
            font = ImageFont.load_default()

    symbol = "✦"
    size = font_size + 8
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((size // 2, size // 2), symbol, font=font, fill=(255, 255, 255, 220), anchor="mm")

    tex = ctx.texture((size, size), 4, img.tobytes())
    tex.filter = moderngl.LINEAR, moderngl.LINEAR
    return tex, size


class Fractal(mglw.WindowConfig):
    title = "Mandelbrot"
    window_size = (1200, 800)
    aspect_ratio = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.prog = self.ctx.program(vertex_shader=VERT, fragment_shader=FRAG)
        quad = np.array([-1,-1, 1,-1, -1,1, 1,1], dtype='f4')
        self.vao = self.ctx.simple_vertex_array(self.prog, self.ctx.buffer(quad), 'in_vert')

        self.overlay_prog = self.ctx.program(vertex_shader=OVERLAY_VERT, fragment_shader=OVERLAY_FRAG)
        self.overlay_tex, tw, th = make_overlay_texture(self.ctx, CONTROLS)
        self._build_overlay_vao(tw, th)
        self.cursor_tex, self.cursor_size = make_cursor_texture(self.ctx)
        self.cursor_vbo = self.ctx.buffer(reserve=4 * 4 * 4)
        self.cursor_vao = self.ctx.simple_vertex_array(
            self.overlay_prog, self.cursor_vbo, 'in_pos', 'in_uv'
        )

        self.center = np.array([-0.5, 0.0], dtype='f4')
        self.zoom = 1.5
        self.drag_start = None
        self.drag_center = None
        self.mouse_pos = np.array([0.0, 0.0], dtype='f4')
        self.zoom_dir = 0  # -1 out, 0 stopped, 1 in
        self.zoom_speed = 0.6

        self.wnd.cursor = False

    def _build_overlay_vao(self, tw, th):
        w, h = self.wnd.size
        # top-left corner, in NDC
        x0 = -1.0 + 10 / w * 2
        x1 = x0 + tw / w * 2
        y1 = 1.0 - 10 / h * 2
        y0 = y1 - th / h * 2
        verts = np.array([
            x0, y0,  0, 1,
            x1, y0,  1, 1,
            x0, y1,  0, 0,
            x1, y1,  1, 0,
        ], dtype='f4')
        self.overlay_vao = self.ctx.simple_vertex_array(
            self.overlay_prog, self.ctx.buffer(verts), 'in_pos', 'in_uv'
        )

    def _zoom_toward_mouse(self, factor):
        mx, my = self.mouse_pos
        w, h = self.wnd.size
        aspect = w / h
        mouse_c = self.center + np.array([
            (mx / w * 2 - 1) * aspect * self.zoom,
            (1 - my / h * 2) * self.zoom
        ], dtype='f4')
        self.zoom *= factor
        self.center = mouse_c - (mouse_c - self.center) * factor

    def on_render(self, time, frame_time):
        if self.zoom_dir != 0:
            factor = self.zoom_speed ** (frame_time * self.zoom_dir)
            self._zoom_toward_mouse(factor)

        self.ctx.clear()
        self.prog['center'].value = tuple(self.center)
        self.prog['zoom'].value = self.zoom
        self.prog['resolution'].value = self.wnd.size
        self.vao.render(moderngl.TRIANGLE_STRIP)

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        self.overlay_tex.use()
        self.overlay_vao.render(moderngl.TRIANGLE_STRIP)

        # Draw ✦ cursor centered on mouse position
        mx, my = self.mouse_pos
        w, h = self.wnd.size
        cs = self.cursor_size
        cx0 = (mx - cs / 2) / w * 2 - 1
        cx1 = (mx + cs / 2) / w * 2 - 1
        cy1 = 1 - (my - cs / 2) / h * 2
        cy0 = 1 - (my + cs / 2) / h * 2
        cursor_verts = np.array([
            cx0, cy0,  0, 1,
            cx1, cy0,  1, 1,
            cx0, cy1,  0, 0,
            cx1, cy1,  1, 0,
        ], dtype='f4')
        self.cursor_vbo.write(cursor_verts.tobytes())
        self.cursor_tex.use()
        self.cursor_vao.render(moderngl.TRIANGLE_STRIP)

        self.ctx.disable(moderngl.BLEND)

    def on_key_event(self, key, action, modifiers):
        keys = self.wnd.keys
        if key == keys.Z:
            if action == keys.ACTION_RELEASE:
                self.zoom_dir = 0
            else:
                self.zoom_dir = -1 if modifiers.shift else 1
        if action == keys.ACTION_PRESS and key == keys.NUMBER_0:
            self.center = np.array([-0.5, 0.0], dtype='f4')
            self.zoom = 1.5

    def on_mouse_position_event(self, x, y, dx, dy):
        self.mouse_pos = np.array([x, y], dtype='f4')

    def on_mouse_scroll_event(self, x_offset, y_offset):
        self._zoom_toward_mouse(0.95 ** y_offset)

    def on_mouse_press_event(self, x, y, button):
        if button == 1:
            self.drag_start = np.array([x, y], dtype='f4')
            self.drag_center = self.center.copy()

    def on_mouse_release_event(self, x, y, button):
        if button == 1:
            self.drag_start = None

    def on_mouse_drag_event(self, x, y, dx, dy):
        if self.drag_start is not None:
            w, h = self.wnd.size
            aspect = w / h
            delta = np.array([
                -(x - self.drag_start[0]) / w * 2 * aspect * self.zoom,
                (y - self.drag_start[1]) / h * 2 * self.zoom
            ], dtype='f4')
            self.center = self.drag_center + delta

if __name__ == '__main__':
    mglw.run_window_config(Fractal)
