"""Host tests for DIVE: rules, sprite table, glyph coverage, sound and the renderer.

The renderer runs against an emulated ST7789 GRAM with hardware scroll, so the
dirty-rectangle test checks exactly the pixels the panel would show.
"""
import ctypes
import re
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from host_tools import CC, SHARED_EXPORT, unload_library

ROOT = Path(__file__).resolve().parent
BOARD = ROOT / 'xiaozhi-esp32/main/boards/folotoy/ai-passport-nabo'
SOURCES = ['nabo_dive_model.c', 'nabo_dive_anim.c', 'nabo_dive_render.c', 'nabo_dive_draw.c', 'nabo_dive_text.c',
           'nabo_dive_sound.c', 'nabo_dive_sprites.c', 'nabo_menu_font_16.c', 'nabo_ui_font_18.c',
           'nabo_poster_font_28.c', 'nabo_poster_font_48.c', 'nabo_mono_font_12.c']
TITLE, PLAY, PAUSE, OVER = 0, 1, 2, 3
X, Y, O2, VY, PHASE, CAM, LB, ZONE, HITS, INV = range(10)

temp = tempfile.TemporaryDirectory()
library = Path(temp.name) / 'dive.so'
subprocess.run([CC, '-std=gnu11', '-O2', '-shared', SHARED_EXPORT, '-DNABO_DIVE_HOST', '-Wall', '-Wextra', '-Werror',
                '-Wno-missing-field-initializers', '-I', str(ROOT / 'tests/dive_host'), '-I', str(BOARD)]
               + [str(BOARD / s) for s in SOURCES] + [str(ROOT / 'tests/dive_host/dive_host.c'), '-lz', '-o',
                                                       str(library)], check=True)
lib = ctypes.CDLL(str(library))
lib.host_init.argtypes = [ctypes.c_uint32, ctypes.c_float]
lib.host_step.argtypes = [ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_int]
lib.host_step.restype = ctypes.c_uint32
lib.host_frame.argtypes = [ctypes.c_int, ctypes.c_int]
lib.host_frame.restype = ctypes.c_uint32
lib.host_jump.argtypes = [ctypes.c_float, ctypes.c_float]
lib.host_get.argtypes = [ctypes.c_int]
lib.host_get.restype = ctypes.c_float
lib.host_set_o2.argtypes = lib.host_set_x.argtypes = [ctypes.c_float]
lib.host_tune.argtypes = [ctypes.c_float] * 4
EV_FLIP, EV_BUBBLE, EV_HIT, EV_LAST_BREATH, EV_DIE, EV_DASH_ON = 1, 2, 4, 64, 256, 1024


def snapshot():
    buf = (ctypes.c_uint16 * (240 * 320))()
    lib.host_snapshot(buf)
    return list(buf)


def play(frames, seed=7, flip_every=0, dash=False, frame=True):
    lib.host_init(seed, 0)
    events = 0
    for f in range(frames):
        flip = 1 if flip_every and f % flip_every == 0 else 0
        events |= lib.host_step(1 / 60, flip, int(dash), PLAY)
        if frame:
            lib.host_frame(-1, 0)
    return events


class Rules(unittest.TestCase):
    def test_same_seed_same_dive(self):
        play(240, seed=99, flip_every=37)
        a = [lib.host_get(i) for i in (X, Y, O2)]
        play(240, seed=99, flip_every=37)
        self.assertEqual(a, [lib.host_get(i) for i in (X, Y, O2)])

    def test_oxygen_drains_and_dash_trades_speed_for_air(self):
        lib.host_init(5, 0)
        lib.host_jump(1400, 100)  # twilight: 6 per second
        for _ in range(60):
            lib.host_step(1 / 60, 0, 0, PLAY)
            lib.host_set_x(120)
        normal_drop, normal_vy = 100 - lib.host_get(O2), lib.host_get(VY)
        self.assertAlmostEqual(normal_drop, 6, delta=0.6)
        lib.host_init(5, 0)
        lib.host_jump(1400, 100)
        events = 0
        for _ in range(60):
            events |= lib.host_step(1 / 60, 0, 1, PLAY)
            lib.host_set_x(120)
        self.assertTrue(events & EV_DASH_ON)
        self.assertAlmostEqual((100 - lib.host_get(O2)) / normal_drop, 1.5, delta=0.1)
        self.assertGreater(lib.host_get(VY), normal_vy * 1.6)

    def test_wall_hit_costs_air_and_last_breath_ends_the_dive(self):
        lib.host_init(11, 0)
        lib.host_jump(1500, 80)
        events = 0
        for _ in range(240):  # never flip: NABO reaches a wall
            events |= lib.host_step(1 / 60, 0, 0, PLAY)
            if events & EV_HIT:
                break
        self.assertTrue(events & EV_HIT)
        self.assertLess(lib.host_get(O2), 80 - 20)
        lib.host_set_o2(0.01)
        events = 0
        for f in range(240):
            lib.host_clear_rescues()  # nothing may rescue the last breath here
            events |= lib.host_step(1 / 60, 1 if f % 25 == 0 else 0, 0, PLAY)
            if events & EV_DIE:
                break
        self.assertTrue(events & EV_LAST_BREATH)
        self.assertTrue(events & EV_DIE)


class Assets(unittest.TestCase):
    def test_every_frame_inflates_into_the_palette(self):
        text = (BOARD / 'nabo_dive_sprites.c').read_text('utf-8')
        header = (BOARD / 'nabo_dive_sprites.h').read_text('utf-8')
        cell = int(re.search(r'NABO_DIVE_CELL (\d+)', header).group(1))
        frames = int(re.search(r'NABO_DIVE_FRAME_COUNT (\d+)', header).group(1))
        palette = int(re.search(r'NABO_DIVE_PALETTE_SIZE (\d+)', header).group(1))
        offsets = [int(v) for v in re.search(r'nabo_dive_frame_offsets\[\d+\] = \{([^}]*)\}', text).group(1).replace('\n', '').split(',') if v.strip()]
        data = bytes(int(v) for v in re.search(r'nabo_dive_pixels\[\d+\] = \{([^}]*)\}', text).group(1).replace('\n', '').split(',') if v.strip())
        self.assertEqual(len(offsets), frames + 1)
        for f in range(frames):
            px = zlib.decompress(data[offsets[f]:offsets[f + 1]], -15)
            self.assertEqual(len(px), cell * cell)
            self.assertLess(max(px), palette)
            self.assertGreater(sum(1 for v in px if v), cell * cell // 10)

    def test_ui_strings_have_glyphs(self):
        used = set()
        for name in ('nabo_dive_render.c', 'nabo_apps.cc'):
            for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', (BOARD / name).read_text('utf-8')):
                used |= {c for c in literal if ord(c) > 0x7e and c != '·'}
        for font in ('nabo_menu_font_16.c', 'nabo_ui_font_18.c'):
            have = {chr(int(h, 16)) for h in re.findall(r'/\* U\+([0-9A-F]+) ', (BOARD / font).read_text('utf-8'))}
            self.assertEqual(sorted(c for c in used if c not in have), [], font)


class Renderer(unittest.TestCase):
    def test_dirty_rectangles_match_a_full_redraw(self):
        # Incremental frames (hardware scroll + dirty rects) must leave the same picture as
        # redrawing the final state from scratch; any stale pixel is a renderer bug.
        for seed, dash in ((3, False), (8, True)):
            lib.host_init(seed, 1500)
            for f in range(420):
                lib.host_step(1 / 60, 1 if f % 41 == 0 else 0, int(dash and f > 200), PLAY)
                lib.host_frame(-1, 0)
            incremental = snapshot()
            lib.host_invalidate()
            lib.host_frame(-1, 0)
            full = snapshot()
            diff = sum(1 for a, b in zip(incremental, full) if a != b)
            self.assertEqual(diff, 0, f'seed {seed}: {diff} stale pixels')

    def test_title_and_over_screens_render_and_partial_frames_stay_small(self):
        lib.host_init(4, 0)
        for _ in range(20):
            lib.host_step(1 / 60, 0, 0, TITLE)
            lib.host_frame(-1, 0)
        title = snapshot()
        self.assertGreater(len(set(title)), 200)
        sizes = []
        lib.host_init(4, 0)
        for f in range(600):
            lib.host_step(1 / 60, 1 if f % 47 == 0 else 0, 0, PLAY)
            sizes.append(lib.host_frame(-1, 0))
        partial = sorted(sizes[10:])
        self.assertLess(partial[len(partial) // 2], 60 * 1024)


class Sound(unittest.TestCase):
    def test_cues_are_audible_and_never_clip(self):
        class Cue(ctypes.Structure):
            _fields_ = [('events', ctypes.c_uint32), ('zone', ctypes.c_uint8), ('chain', ctypes.c_uint8),
                        ('flips', ctypes.c_uint16)]
        state = (ctypes.c_uint8 * 4096)()
        lib.dive_sound_reset(state)
        lib.dive_sound_state.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_int, ctypes.c_float,
                                         ctypes.c_bool]
        lib.dive_sound_state(state, True, True, 2, 80.0, False)
        lib.dive_sound_cue(state, ctypes.byref(Cue(EV_FLIP | EV_BUBBLE | EV_HIT, 2, 3, 5)))
        pcm = (ctypes.c_int16 * 3200)()
        lib.dive_sound_fill(state, pcm, 3200)
        peak = max(abs(v) for v in pcm)
        self.assertGreater(peak, 1000)
        self.assertLess(peak, 32767)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=1)
    finally:
        unload_library(lib._handle)
