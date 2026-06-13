# vibe-fractals

A super quick exploration of generating fractals with Claude. Spent an evening vibe-coding fractal renderers — tried XaoS (broken on modern macOS), a Python one-liner ASCII Mandelbrot, a GLSL shader via glslViewer, and landed on a proper GPU-accelerated interactive Mandelbrot viewer.

## What's here

- `fractal.py` — interactive Mandelbrot viewer using moderngl (OpenGL via Python)
- `mandelbrot.frag` — GLSL fragment shader for glslViewer (earlier experiment)

## Setup

```bash
pip3 install moderngl moderngl-window
```

## Run

```bash
python3 fractal.py
```

## Controls

| Input | Action |
|---|---|
| `Z` (hold) | Zoom in toward cursor |
| `Shift+Z` (hold) | Zoom out |
| Scroll | Zoom in / out |
| Drag | Pan |
| `0` | Reset view |

## Precision limit

The viewer uses 32-bit floats (float32) for all GPU math. Iteration count scales dynamically with zoom depth, but float32 runs out of precision around **1×10⁷ magnification** — at that point adjacent pixels map to the same coordinate value and the image breaks into large colored blocks. Going deeper requires either double-precision emulation or perturbation theory (see powerful explorers like Kalles Fraktaler or Ultra Fractal).

## Preview

![screenshot](screenshot.png)
