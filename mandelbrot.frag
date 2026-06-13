#ifdef GL_ES
precision highp float;
#endif

uniform vec2 u_resolution;
uniform vec2 u_mouse;
uniform float u_time;

void main() {
    vec2 mouse_norm = u_mouse / u_resolution;
    mouse_norm.y = 1.0 - mouse_norm.y;

    // Mouse Y = zoom speed (top fast, bottom slow)
    float speed = 0.05 + mouse_norm.y * 1.5;

    // Loop zoom so it never loses float precision
    float zoomTime = mod(u_time * speed, 5.0);
    float zoom = exp(-zoomTime);

    // Mouse X pans to pick zoom target within interesting region
    vec2 pan = vec2(-0.5 + (mouse_norm.x - 0.5) * 2.4, 0.0);

    vec2 fragNorm = (gl_FragCoord.xy / u_resolution - 0.5);
    fragNorm.y = -fragNorm.y;
    vec2 c = pan + fragNorm * zoom * vec2(u_resolution.x / u_resolution.y, 1.0);

    // More iterations as zoom tightens
    float maxIter = 128.0 + 256.0 * (1.0 - zoom);

    vec2 z = vec2(0.0);
    float iter = 0.0;
    for (float i = 0.0; i < 384.0; i++) {
        if (i >= maxIter || dot(z, z) > 4.0) break;
        z = vec2(z.x*z.x - z.y*z.y, 2.0*z.x*z.y) + c;
        iter++;
    }

    float t = iter / maxIter;
    vec3 color = vec3(
        0.5 + 0.5 * cos(6.28318 * t + 0.0),
        0.5 + 0.5 * cos(6.28318 * t + 2.094),
        0.5 + 0.5 * cos(6.28318 * t + 4.189)
    );
    if (iter >= maxIter) color = vec3(0.0);

    gl_FragColor = vec4(color, 1.0);
}
