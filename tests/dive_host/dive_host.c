/* Host harness for DIVE: runs the real model, animation and renderer against an
 * emulated ST7789 GRAM with hardware vertical scroll, for screenshots and tests. */
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include "nabo_dive_anim.h"
#include "nabo_dive_model.h"
#include "nabo_dive_render.h"

static uint16_t gram[DIVE_H][DIVE_W];  // big-endian, as the panel receives it
static int scroll_top;
static dive_t game;
static dive_gfx_t gfx;
static dive_anim_t anim;
static dive_view_t view;
static dive_tune_t tune = {1, 1, 1, 1};
static uint32_t sent_bytes, transfers;

static void send(void* ctx, int x0, int gy, int w, int rows, uint16_t* px) {
    (void)ctx;
    for (int r = 0; r < rows; ++r)
        memcpy(&gram[gy + r][x0], px + r * w, (size_t)w * 2);
    sent_bytes += (uint32_t)(w * rows * 2);
    ++transfers;
}
static void scroll(void* ctx, int top) {
    (void)ctx;
    scroll_top = top;
}
static bool decode(void* ctx, int frame, uint8_t* out) {
    (void)ctx;
    z_stream s;
    memset(&s, 0, sizeof(s));
    if (inflateInit2(&s, -15) != Z_OK)
        return false;
    s.next_in = (Bytef*)&nabo_dive_pixels[nabo_dive_frame_offsets[frame]];
    s.avail_in = nabo_dive_frame_offsets[frame + 1] - nabo_dive_frame_offsets[frame];
    s.next_out = out;
    s.avail_out = NABO_DIVE_CELL * NABO_DIVE_CELL;
    int rc = inflate(&s, Z_FINISH);
    inflateEnd(&s);
    return rc == Z_STREAM_END && s.avail_out == 0;
}

int host_init(uint32_t seed, float best_px) {
    dive_reset(&game, seed, best_px);
    dive_anim_reset(&anim);
    memset(&view, 0, sizeof(view));
    view.best_m = -1;
    memset(gram, 0, sizeof(gram));
    if (gfx.rows)
        dive_gfx_free(&gfx);
    return dive_gfx_init(&gfx, send, scroll, decode, NULL) ? 0 : -1;
}
void host_tune(float speed, float drain, float bubbles, float obstacles) {
    tune = (dive_tune_t){speed, drain, bubbles, obstacles};
}
// Advances the model by dt in 1/120 s steps, then the animation; returns raised events.
uint32_t host_step(float dt, int flip, int dash, int screen) {
    uint32_t ev = 0;
    int steps = (int)(dt * 120 + 0.5f);
    for (int i = 0; i < steps; ++i) {
        if (screen == DIVE_SCREEN_PLAY)
            dive_step(&game, &tune, 1.0f / 120, flip && i == 0, dash);
        ev |= dive_take_events(&game);
    }
    view.time += dt;
    dive_anim_update(&anim, &game, (dive_screen_t)screen, dash, ev, dt, &view);
    return ev;
}
uint32_t host_frame(int best_m, int dash_hint) {
    view.best_m = best_m;
    view.dash_hint = dash_hint;
    sent_bytes = 0;
    transfers = 0;
    dive_gfx_frame(&gfx, &game, &view);
    return sent_bytes;
}
uint32_t host_transfers(void) { return transfers; }
// Screen as the viewer sees it (native RGB565), honouring hardware scroll.
void host_snapshot(uint16_t* out) {
    for (int y = 0; y < DIVE_H; ++y)
        for (int x = 0; x < DIVE_W; ++x) {
            uint16_t v = gram[(scroll_top + y) % DIVE_H][x];
            out[y * DIVE_W + x] = (uint16_t)((v >> 8) | (v << 8));
        }
}
dive_t* host_game(void) { return &game; }
int host_frame_index(void) { return view.frame; }
void host_view_time(float t) { view.time = t; }
// Moves the dive to world row px with fresh surroundings (like the prototype's DIVE.jump).
void host_jump(float px, float o2) {
    game.y = px;
    game.cam_y = px - DIVE_SCREEN_Y;
    game.gen_y = px - 160;
    game.next_bubble_y = px + 100;
    memset(game.obs, 0, sizeof(game.obs));
    memset(game.bubbles, 0, sizeof(game.bubbles));
    memset(game.vents, 0, sizeof(game.vents));
    game.t = 2;
    game.o2 = o2;
    float l, r;
    dive_corridor(&game, px, &l, &r);
    game.x = (l + r) / 2;
    dive_gfx_invalidate(&gfx);
}
void host_die(void) {
    game.o2 = 0;
    game.lb = true;
    game.lb_t = 0.001f;
}
void host_invalidate(void) { dive_gfx_invalidate(&gfx); }
// Plain accessors so the Python tests do not mirror dive_t's layout.
float host_get(int what) {
    switch (what) {
        case 0: return game.x;
        case 1: return game.y;
        case 2: return game.o2;
        case 3: return game.vy;
        case 4: return (float)game.phase;
        case 5: return game.cam_y;
        case 6: return (float)game.lb;
        case 7: return (float)game.zone;
        case 8: return (float)game.stat_hits;
        case 9: return game.inv;
        default: return 0;
    }
}
void host_set_o2(float o2) { game.o2 = o2; }
void host_set_x(float x) { game.x = x; }
// Removes everything that could rescue NABO (bubbles and near-miss creatures).
void host_clear_rescues(void) {
    memset(game.bubbles, 0, sizeof(game.bubbles));
    memset(game.obs, 0, sizeof(game.obs));
    memset(game.vents, 0, sizeof(game.vents));
}
