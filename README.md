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
| Scroll | Zoom in / out |
| Drag | Pan |
| `0` | Reset view |
