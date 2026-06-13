import moderngl_window as mglw
import moderngl
import numpy as np
import math
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

    // Use highp for coordinate math to push precision as far as float32 allows
    highp vec2 c = center + v_uv * aspect * zoom;
    highp vec2 z = vec2(0.0);

    // Scale iterations with zoom depth — more detail as we go deeper
    float maxIter = clamp(256.0 + 80.0 * log(1.5 / max(zoom, 1e-8)), 256.0, 1500.0);

    float iter = 0.0;
    for (float i = 0.0; i < 1500.0; i++) {
        if (i >= maxIter || dot(z, z) > 4.0) break;
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

# Bloom rendered in shader: smooth radial glow, no pixelation
BLOOM_VERT = """
#version 330
in vec2 in_vert;
void main() {
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

BLOOM_FRAG = """
#version 330
out vec4 fragColor;
uniform vec2 u_mouse;
uniform vec2 u_resolution;

void main() {
    vec2 fc = vec2(gl_FragCoord.x, u_resolution.y - gl_FragCoord.y);
    float d = length(fc - u_mouse);
    float sigma = 90.0;
    float glow = exp(-d * d / (2.0 * sigma * sigma));
    vec3 orange = vec3(1.0, 0.45, 0.08);
    float alpha = glow * 0.45;
    fragColor = vec4(orange * alpha, alpha);
}
"""

CONTROLS_STATIC = [
    "Z         hold to zoom in",
    "Shift+Z   hold to zoom out",
    "Scroll    zoom in / out",
    "Drag      pan",
    "0         reset view",
]

def _make_font(size):
    for path in ["/System/Library/Fonts/Courier.dfont", "/System/Library/Fonts/Menlo.ttc"]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()

def make_controls_texture(ctx, zoom_val, font_size=15):
    font = _make_font(font_size)
    mag = 1.5 / zoom_val
    if mag >= 1000:
        scale_str = f"Scale  {mag:.2e}x"
    else:
        scale_str = f"Scale  {mag:.1f}x"

    lines = CONTROLS_STATIC + ["", scale_str]
    padding = 10
    line_h = font_size + 4
    w = 280
    h = len(lines) * line_h + padding * 2

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w - 1, h - 1], fill=(0, 0, 0, 140))
    for i, line in enumerate(lines):
        color = (255, 160, 60, 255) if line.startswith("Scale") else (255, 255, 255, 230)
        draw.text((padding, padding + i * line_h), line, font=font, fill=color)

    tex = ctx.texture((w, h), 4, img.tobytes())
    tex.filter = moderngl.NEAREST, moderngl.NEAREST
    return tex, w, h

def make_cursor_texture(ctx, size=36):
    cx, cy = size / 2, size / 2
    outer = size / 2 - 2
    inner = outer * 0.30
    pts = []
    for i in range(8):
        angle = math.radians(i * 45 - 90)
        r = outer if i % 2 == 0 else inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).polygon(pts, fill=(255, 255, 255, 230))
    tex = ctx.texture((size, size), 4, img.tobytes())
    tex.filter = moderngl.LINEAR, moderngl.LINEAR
    return tex, size


class Fractal(mglw.WindowConfig):
    title = "Mandelbrot"
    window_size = (1200, 800)
    aspect_ratio = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Fractal
        self.prog = self.ctx.program(vertex_shader=VERT, fragment_shader=FRAG)
        quad = np.array([-1,-1, 1,-1, -1,1, 1,1], dtype='f4')
        self.vao = self.ctx.simple_vertex_array(self.prog, self.ctx.buffer(quad), 'in_vert')

        # Controls overlay
        self.overlay_prog = self.ctx.program(vertex_shader=OVERLAY_VERT, fragment_shader=OVERLAY_FRAG)
        self.zoom = 1.5
        self.overlay_tex, tw, th = make_controls_texture(self.ctx, self.zoom)
        self._build_overlay_vao(tw, th)
        self._last_overlay_zoom = self.zoom

        # Sharp ✦ cursor (texture)
        self.cursor_tex, self.cursor_size = make_cursor_texture(self.ctx)
        self.cursor_vbo = self.ctx.buffer(reserve=4 * 4 * 4)
        self.cursor_vao = self.ctx.simple_vertex_array(
            self.overlay_prog, self.cursor_vbo, 'in_pos', 'in_uv'
        )

        # Shader bloom (smooth radial glow, no pixelation)
        self.bloom_prog = self.ctx.program(vertex_shader=BLOOM_VERT, fragment_shader=BLOOM_FRAG)
        self.bloom_vao = self.ctx.simple_vertex_array(
            self.bloom_prog, self.ctx.buffer(quad), 'in_vert'
        )

        self.center = np.array([-0.5, 0.0], dtype='f4')
        self.drag_start = None
        self.drag_center = None
        self.mouse_pos = np.array([0.0, 0.0], dtype='f4')
        self.zoom_dir = 0
        self.zoom_speed = 0.6
        self.wnd.cursor = False

    def _build_overlay_vao(self, tw, th):
        w, h = self.wnd.size
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
        self.zoom = min(self.zoom * factor, 2.0)
        self.center = mouse_c - (mouse_c - self.center) * factor

    def _refresh_overlay(self):
        self.overlay_tex.release()
        self.overlay_tex, tw, th = make_controls_texture(self.ctx, self.zoom)
        self._build_overlay_vao(tw, th)
        self._last_overlay_zoom = self.zoom

    def on_render(self, time, frame_time):
        if self.zoom_dir != 0:
            self._zoom_toward_mouse(self.zoom_speed ** (frame_time * self.zoom_dir))

        # Refresh scale display when zoom changes by >1%
        if abs(self.zoom - self._last_overlay_zoom) / self._last_overlay_zoom > 0.01:
            self._refresh_overlay()

        self.ctx.clear()
        self.prog['center'].value = tuple(self.center)
        self.prog['zoom'].value = self.zoom
        self.prog['resolution'].value = self.wnd.size
        self.vao.render(moderngl.TRIANGLE_STRIP)

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        # Shader bloom glow
        w, h = self.wnd.size
        self.bloom_prog['u_mouse'].value = (self.mouse_pos[0], self.mouse_pos[1])
        self.bloom_prog['u_resolution'].value = (w, h)
        self.bloom_vao.render(moderngl.TRIANGLE_STRIP)

        # Controls overlay
        self.overlay_tex.use()
        self.overlay_vao.render(moderngl.TRIANGLE_STRIP)

        # Sharp ✦ cursor
        mx, my = self.mouse_pos
        cs = self.cursor_size
        cx0 = (mx - cs / 2) / w * 2 - 1
        cx1 = (mx + cs / 2) / w * 2 - 1
        cy1 = 1 - (my - cs / 2) / h * 2
        cy0 = 1 - (my + cs / 2) / h * 2
        self.cursor_vbo.write(np.array([
            cx0, cy0,  0, 1,
            cx1, cy0,  1, 1,
            cx0, cy1,  0, 0,
            cx1, cy1,  1, 0,
        ], dtype='f4').tobytes())
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
            self._refresh_overlay()

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
        self.mouse_pos = np.array([x, y], dtype='f4')
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
