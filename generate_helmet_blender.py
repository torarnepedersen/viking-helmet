"""
Viking Helmet – Blender Generator Script
=========================================
Run from Blender's Scripting workspace (paste & press Run Script),
or headlessly:

    blender --background --python generate_helmet_blender.py

All design parameters are in the PARAMETERS section below.
Each helmet part becomes its own named object so you can select,
hide, or further edit individual parts after generation.

Blender 3.x / 4.x / 5.x compatible.  No external libraries needed.
"""

import bpy
import bmesh
import math
import os
import random
from mathutils import Vector

# ─────────────────────────────────────────────────────────────────────────────
#  PARAMETERS  ← edit freely and re-run
# ─────────────────────────────────────────────────────────────────────────────

# ── Dome ──────────────────────────────────────────────────────────────────────
R            = 100.0   # Outer radius (mm)
CUT_Z        = -18.0   # Cut-plane height (mm, below equator)
OVAL_Z       =   1.30  # Z stretch: 1.0 = sphere, 1.3 = 30 % taller/egg-shaped

# ── Rim ───────────────────────────────────────────────────────────────────────
RIM_OUT      =   8.0   # Protrusion beyond dome edge (mm)
RIM_H        =  10.0   # Vertical height (mm)

# ── Nose guard ────────────────────────────────────────────────────────────────
SHOW_NOSE    =  True   # Set to False to skip nose guard entirely
NOSE_W_TOP   =  40.0   # Width at the top attachment point (mm)
NOSE_W_BOT   =  20.0   # Width at the bottom tip (mm)
NOSE_H       =  68.0   # Total length (mm)
NOSE_T       =   5.0   # Thickness / depth (mm)
NOSE_STEPS   =  20     # Vertical segments (more = smoother taper)

# ── Rivets ────────────────────────────────────────────────────────────────────
RIVET_R      =   4.0   # Hemisphere radius (mm)
N_RIVETS     =  16     # Count around rim

# ── Runes ─────────────────────────────────────────────────────────────────────
RUNE_RAISE       =   2.8   # Relief height above dome surface (mm)
RUNE_SW          =   2.0   # Stroke width (mm)
RUNE_SIZE        =  18.0   # Glyph cell size on dome (mm)
RUNE_PHI_OFFSET  =  45.0   # Extra degrees toward the rim (0 = original height)
SHOW_RUNES       =  True   # Set to False to skip runes entirely

# ── Tessellation ──────────────────────────────────────────────────────────────
DOME_SEGS_T  =  72     # Azimuthal segments (around)
DOME_SEGS_P  =  36     # Polar segments (top → cut)
SUBD_DOME    =   1     # Subdivision Surface level on dome (0 = off)

# ── Worn / battle-used look ───────────────────────────────────────────────────
# 0.0 = pristine showroom  |  0.2 = light use  |  1.0 = heavy battle damage
WORN_AMOUNT  =   0.20
WORN_SEED    =   42    # change for a different random damage pattern

# ── Visual ────────────────────────────────────────────────────────────────────
COL_STEEL    = (0.55, 0.57, 0.60)
COL_GOLD     = (0.90, 0.73, 0.18)

# ── Export ────────────────────────────────────────────────────────────────────
# Leave OUTPUT_STL = "" to skip export (use File ▸ Export ▸ STL manually).
try:
    _here = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _here = os.path.expanduser("~/førstetest")
OUTPUT_STL = os.path.join(_here, "viking_helmet_blender.stl")


# ─────────────────────────────────────────────────────────────────────────────
#  RUNE DEFINITIONS  (Elder Futhark, strokes in normalised [0,1]² glyph space)
#  Each stroke: (x0, y0, x1, y1)   x = right,  y = up
# ─────────────────────────────────────────────────────────────────────────────
RUNE_STROKES = {
    "fehu":     [(0.0,.10,.20,.90),(.20,.90,.50,.50),(.20,.50,.50,.90)],
    "uruz":     [(0.0,.10,.00,.90),(.00,.90,.40,.50),(.40,.50,.40,.10)],
    "thurisaz": [(0.0,.50,1.0,.50),(.50,.10,.50,.90),(.00,.90,.50,.50)],
    "ansuz":    [(0.0,.10,.00,.90),(.40,.10,.40,.90),(.00,.70,.40,.40)],
    "gebo":     [(0.0,.10,1.0,.90),(1.0,.10,0.0,.90)],
    "raido":    [(0.0,.10,.00,.90),(.00,.90,.40,.60),(.40,.60,.20,.10),
                 (.00,.50,.40,.50)],
    "wunjo":    [(0.0,.90,.50,.30),(0.0,.10,.50,.50),(.50,.30,.50,.90)],
    "tiwaz":    [(.50,.10,.50,.90),(0.0,.50,.50,.90),(1.0,.50,.50,.90)],
}

# (rune, theta °, base_phi °)  – RUNE_PHI_OFFSET is added at build time
RUNE_PLACEMENTS = [
    ("fehu",      40,  42),   # front-right
    ("uruz",     130,  42),   # back-right
    ("thurisaz", 220,  42),   # back-left
    ("ansuz",    310,  42),   # front-left
    ("gebo",      90,  28),   # right, higher
    ("raido",    270,  28),   # left, higher
    ("wunjo",    180,  35),   # back center
    ("tiwaz",      0,  28),   # front, above nose guard
]


# ─────────────────────────────────────────────────────────────────────────────
#  DERIVED GEOMETRY QUANTITIES  (recalculated from parameters each run)
# ─────────────────────────────────────────────────────────────────────────────
def _phi_max():
    """Polar angle (radians) where the oval dome meets the cut-plane."""
    return math.acos(max(-1.0, min(1.0, CUT_Z / (R * OVAL_Z))))

def _r_inner():
    """X-Y radius of the dome at the cut-plane (= inner rim radius)."""
    return R * math.sin(_phi_max())


# ─────────────────────────────────────────────────────────────────────────────
#  GEOMETRY HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def sph_oval(r, phi, theta):
    """Oval spherical → Cartesian.  Z axis is scaled by OVAL_Z."""
    return Vector((
        r * math.sin(phi) * math.cos(theta),
        r * math.sin(phi) * math.sin(theta),
        r * OVAL_Z * math.cos(phi),
    ))

def oval_normal(pos):
    """Outward surface normal of the dome ellipsoid at world position pos."""
    # gradient of  x²/R² + y²/R² + z²/(R·OVAL_Z)² = 1
    return Vector((pos.x, pos.y, pos.z / (OVAL_Z ** 2))).normalized()


# ─────────────────────────────────────────────────────────────────────────────
#  SCENE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    s = bpy.context.scene
    s.unit_settings.system       = 'METRIC'
    s.unit_settings.scale_length = 0.001
    s.unit_settings.length_unit  = 'MILLIMETERS'

def make_material(name, color, metallic=0.0, roughness=0.5):
    mat  = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value   = metallic
    bsdf.inputs["Roughness"].default_value  = roughness
    return mat


# ─────────────────────────────────────────────────────────────────────────────
#  MESH BUILDER
# ─────────────────────────────────────────────────────────────────────────────
class MB:
    """Accumulate triangles / quads, then build a Blender mesh object."""

    def __init__(self):
        self.verts = []
        self.faces = []

    def tri(self, a, b, c):
        i = len(self.verts)
        self.verts += [tuple(a), tuple(b), tuple(c)]
        self.faces.append((i, i+1, i+2))

    def quad(self, a, b, c, d):
        self.tri(a, b, c)
        self.tri(a, c, d)

    def build(self, name, mat=None, smooth=False):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(self.verts, [], self.faces)
        mesh.update()

        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.02)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()

        if smooth:
            for p in mesh.polygons:
                p.use_smooth = True
        if mat:
            mesh.materials.append(mat)

        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        return obj


# ─────────────────────────────────────────────────────────────────────────────
#  WORN / BATTLE-USED LOOK
# ─────────────────────────────────────────────────────────────────────────────

def _apply_dents(obj):
    """
    Push spherical dents into the dome mesh vertices.
    Called before the Subdivision modifier so dents are smoothly blended.
    Number and depth of dents scale with WORN_AMOUNT.
    """
    rng  = random.Random(WORN_SEED)
    pmax = _phi_max()
    n    = max(1, round(WORN_AMOUNT * 5 + 0.5))   # 1 – 6 dents

    dents = []
    for _ in range(n):
        theta  = rng.uniform(0, 2 * math.pi)
        phi    = rng.uniform(math.radians(12), pmax * 0.80)
        impact = sph_oval(R, phi, theta)
        radius = rng.uniform(10.0, 22.0)                     # mm, fixed spread
        depth  = rng.uniform(3.0,  9.0) * WORN_AMOUNT        # scales with wear
        dents.append((impact, radius, depth))

    mesh = obj.data
    for v in mesh.vertices:
        nrm = v.co.normalized()
        for impact, radius, depth in dents:
            d = (v.co - impact).length
            if d < radius:
                w = (1.0 - (d / radius) ** 2) ** 3   # smooth cubic falloff
                v.co -= nrm * (depth * w)
    mesh.update()


def _add_noise_modifier(obj, strength, scale):
    """
    Add a DISPLACE modifier with a CLOUDS texture for micro surface detail.
    'strength' is in mm; positive/negative bumps are centered at mid_level=0.5.
    """
    tex = bpy.data.textures.new(f"Worn_{obj.name}", type='CLOUDS')
    tex.noise_scale = scale
    tex.noise_depth = 4

    mod = obj.modifiers.new("WornSurface", 'DISPLACE')
    mod.texture        = tex
    mod.strength       = strength
    mod.texture_coords = 'GLOBAL'
    mod.mid_level      = 0.5


def _apply_rim_notches(obj):
    """
    Displace outer top-edge rim vertices downward to simulate sword notches
    (hakk). Each notch is a sharp V-cut scaled by WORN_AMOUNT.
    """
    rng       = random.Random(WORN_SEED + 7)
    r_out     = _r_inner() + RIM_OUT
    n_notches = max(1, round(WORN_AMOUNT * 7))
    notch_t   = [rng.uniform(0, 2 * math.pi) for _ in range(n_notches)]

    mesh = obj.data
    for v in mesh.vertices:
        vr = math.sqrt(v.co.x ** 2 + v.co.y ** 2)
        vt = math.atan2(v.co.y, v.co.x)
        # Only affect the outer top edge
        if abs(vr - r_out) < 3.5 and v.co.z > CUT_Z - 4.0:
            for nt in notch_t:
                diff  = abs(math.atan2(math.sin(vt - nt), math.cos(vt - nt)))
                width = math.radians(3.5)
                if diff < width:
                    depth = rng.uniform(2.0, 6.0) * WORN_AMOUNT
                    v.co.z -= depth * (1.0 - diff / width) ** 2
    mesh.update()


# ─────────────────────────────────────────────────────────────────────────────
#  PART 1 – DOME
# ─────────────────────────────────────────────────────────────────────────────
def build_dome(mat):
    mb   = MB()
    pmax = _phi_max()
    T    = [2 * math.pi * i / DOME_SEGS_T for i in range(DOME_SEGS_T)]
    P    = [pmax         * j / DOME_SEGS_P for j in range(DOME_SEGS_P + 1)]

    apex = sph_oval(R, 0, 0)
    for i in range(DOME_SEGS_T):
        mb.tri(apex,
               sph_oval(R, P[1], T[i]),
               sph_oval(R, P[1], T[(i + 1) % DOME_SEGS_T]))

    for j in range(1, DOME_SEGS_P):
        for i in range(DOME_SEGS_T):
            i2 = (i + 1) % DOME_SEGS_T
            mb.quad(sph_oval(R, P[j],     T[i]),
                    sph_oval(R, P[j],     T[i2]),
                    sph_oval(R, P[j + 1], T[i2]),
                    sph_oval(R, P[j + 1], T[i]))

    obj = mb.build("Dome", mat, smooth=True)

    # Dents go BEFORE subdivision so the modifier smooths over them naturally
    if WORN_AMOUNT > 0:
        _apply_dents(obj)

    if SUBD_DOME > 0:
        sub               = obj.modifiers.new("Subsurf", 'SUBSURF')
        sub.levels        = SUBD_DOME
        sub.render_levels = SUBD_DOME + 1

    # Fine surface noise goes AFTER subdivision for micro-detail
    if WORN_AMOUNT > 0:
        _add_noise_modifier(obj, WORN_AMOUNT * 4.5, 14.0)

    return obj


# ─────────────────────────────────────────────────────────────────────────────
#  PART 2 – RIM
# ─────────────────────────────────────────────────────────────────────────────
def build_rim(mat):
    mb    = MB()
    r_in  = _r_inner()
    r_out = r_in + RIM_OUT
    z_t   = CUT_Z
    z_b   = CUT_Z - RIM_H
    T     = [2 * math.pi * i / DOME_SEGS_T for i in range(DOME_SEGS_T)]

    for i in range(DOME_SEGS_T):
        t,  t2  = T[i], T[(i + 1) % DOME_SEGS_T]
        ct,  st  = math.cos(t),  math.sin(t)
        ct2, st2 = math.cos(t2), math.sin(t2)

        oi  = Vector((r_out * ct,  r_out * st,  z_t))
        oi2 = Vector((r_out * ct2, r_out * st2, z_t))
        ii  = Vector((r_in  * ct,  r_in  * st,  z_t))
        ii2 = Vector((r_in  * ct2, r_in  * st2, z_t))
        ob  = Vector((r_out * ct,  r_out * st,  z_b))
        ob2 = Vector((r_out * ct2, r_out * st2, z_b))
        ib  = Vector((r_in  * ct,  r_in  * st,  z_b))
        ib2 = Vector((r_in  * ct2, r_in  * st2, z_b))

        mb.quad(ii,  ii2, oi2, oi)    # top    (+z)
        mb.quad(ob,  ob2, ib2, ib)    # bottom (−z)
        mb.quad(ob,  oi,  oi2, ob2)   # outer  (+r)
        mb.quad(ib2, ii2, ii,  ib)    # inner  (−r)

    obj = mb.build("Rim", mat)

    if WORN_AMOUNT > 0:
        _apply_rim_notches(obj)
        _add_noise_modifier(obj, WORN_AMOUNT * 2.5, 7.0)

    return obj


# ─────────────────────────────────────────────────────────────────────────────
#  PART 3 – RIVETS
# ─────────────────────────────────────────────────────────────────────────────
def build_rivets(mat):
    mb    = MB()
    r_mid = _r_inner() + RIM_OUT * 0.5
    NR, NRT = 8, 16
    PR = [math.pi / 2 * j / NR  for j in range(NR + 1)]
    TR = [2 * math.pi * i / NRT for i in range(NRT)]

    for k in range(N_RIVETS):
        ang        = 2 * math.pi * k / N_RIVETS
        cx, cy, cz = r_mid * math.cos(ang), r_mid * math.sin(ang), CUT_Z

        # Default-arg capture avoids closure-over-loop-variable bug
        def rv(phi, theta, _cx=cx, _cy=cy, _cz=cz):
            return Vector((_cx + RIVET_R * math.sin(phi) * math.cos(theta),
                           _cy + RIVET_R * math.sin(phi) * math.sin(theta),
                           _cz + RIVET_R * math.cos(phi)))

        apex = Vector((cx, cy, cz + RIVET_R))
        for i in range(NRT):
            mb.tri(apex, rv(PR[1], TR[i]), rv(PR[1], TR[(i + 1) % NRT]))

        for j in range(1, NR):
            for i in range(NRT):
                i2 = (i + 1) % NRT
                mb.quad(rv(PR[j],     TR[i]),  rv(PR[j],     TR[i2]),
                        rv(PR[j + 1], TR[i2]), rv(PR[j + 1], TR[i]))

        cbase = Vector((cx, cy, cz))
        for i in range(NRT):
            mb.tri(cbase,
                   rv(math.pi / 2, TR[(i + 1) % NRT]),
                   rv(math.pi / 2, TR[i]))

    return mb.build("Rivets", mat, smooth=True)


# ─────────────────────────────────────────────────────────────────────────────
#  PART 4 – NOSE GUARD
# ─────────────────────────────────────────────────────────────────────────────
def build_nose_guard(mat):
    mb    = MB()
    r_in  = _r_inner()
    z_top = CUT_Z - RIM_H
    z_bot = z_top - NOSE_H

    # Width linearly interpolates between top and bottom values
    def hw(t):  return ((1.0 - t) * NOSE_W_TOP + t * NOSE_W_BOT) / 2.0
    # Front face recedes slightly toward the tip
    def xfr(t): return r_in + NOSE_T * (1.0 - 0.5 * t)

    for i in range(NOSE_STEPS):
        t0, t1 = i / NOSE_STEPS, (i + 1) / NOSE_STEPS
        z0 = z_top + (z_bot - z_top) * t0
        z1 = z_top + (z_bot - z_top) * t1
        hw0, hw1  = hw(t0),  hw(t1)
        xf0, xf1  = xfr(t0), xfr(t1)
        xb0, xb1  = xf0 - NOSE_T, xf1 - NOSE_T

        fl0 = Vector((xf0, -hw0, z0));  fr0 = Vector((xf0,  hw0, z0))
        fl1 = Vector((xf1, -hw1, z1));  fr1 = Vector((xf1,  hw1, z1))
        bl0 = Vector((xb0, -hw0, z0));  br0 = Vector((xb0,  hw0, z0))
        bl1 = Vector((xb1, -hw1, z1));  br1 = Vector((xb1,  hw1, z1))

        mb.quad(fl0, fr0, fr1, fl1)   # front (+x)
        mb.quad(br0, bl0, bl1, br1)   # back  (−x)
        mb.quad(fl0, fl1, bl1, bl0)   # left  (−y)
        mb.quad(fr1, fr0, br0, br1)   # right (+y)

    # Top cap
    hw0, xf, xb = hw(0), xfr(0), xfr(0) - NOSE_T
    mb.quad(Vector((xf, -hw0, z_top)), Vector((xb, -hw0, z_top)),
            Vector((xb,  hw0, z_top)), Vector((xf,  hw0, z_top)))

    # Bottom cap
    hw1, xf, xb = hw(1), xfr(1), xfr(1) - NOSE_T
    mb.quad(Vector((xf,  hw1, z_bot)), Vector((xb,  hw1, z_bot)),
            Vector((xb, -hw1, z_bot)), Vector((xf, -hw1, z_bot)))

    obj = mb.build("NoseGuard", mat)

    if WORN_AMOUNT > 0:
        _add_noise_modifier(obj, WORN_AMOUNT * 2.0, 6.0)

    return obj


# ─────────────────────────────────────────────────────────────────────────────
#  PART 5 – RUNES
# ─────────────────────────────────────────────────────────────────────────────
def _stroke_box(mb, p0, p1, nrm, sw, sh):
    d = p1 - p0
    if d.length < 1e-6:
        return
    along = d.normalized()
    side  = along.cross(nrm)
    if side.length < 1e-9:
        return
    side = side.normalized()
    h = sw / 2.0

    b00 = p0 - side * h;  b01 = p0 + side * h
    b10 = p1 - side * h;  b11 = p1 + side * h
    nsh = nrm * sh
    t00 = b00 + nsh;  t01 = b01 + nsh
    t10 = b10 + nsh;  t11 = b11 + nsh

    mb.quad(t00, t10, t11, t01)   # top face
    mb.quad(b01, b00, t00, t01)   # p0 end-cap
    mb.quad(b10, b11, t11, t10)   # p1 end-cap
    mb.quad(b00, b10, t10, t00)   # left side
    mb.quad(b11, b01, t01, t11)   # right side


def build_runes(mat):
    mb = MB()

    for (name, theta_deg, base_phi_deg) in RUNE_PLACEMENTS:
        theta = math.radians(theta_deg)
        # RUNE_PHI_OFFSET shifts all runes toward the rim (larger phi = lower)
        phi   = math.radians(base_phi_deg + RUNE_PHI_OFFSET)
        # Clamp so runes never slip past the cut-plane
        phi   = min(phi, _phi_max() * 0.92)

        center = sph_oval(R, phi, theta)
        nrm    = oval_normal(center)   # correct ellipsoid normal

        # Local frame: right along +theta, up toward pole
        right = Vector((-math.sin(theta), math.cos(theta), 0.0))
        right = (right - right.dot(nrm) * nrm).normalized()
        up    = nrm.cross(right).normalized()

        # Closure-safe: capture loop variables as defaults
        def cell(nx, ny, _c=center, _r=right, _u=up):
            return _c + _r * (nx - 0.5) * RUNE_SIZE + _u * (ny - 0.5) * RUNE_SIZE

        for (x0, y0, x1, y1) in RUNE_STROKES[name]:
            _stroke_box(mb, cell(x0, y0), cell(x1, y1), nrm, RUNE_SW, RUNE_RAISE)

    return mb.build("Runes", mat)


# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT
# ─────────────────────────────────────────────────────────────────────────────
def export_stl(path):
    if not path:
        return
    bpy.ops.object.select_all(action='SELECT')
    try:
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
    except Exception:
        try:
            bpy.ops.export_mesh.stl(filepath=path, use_selection=True)
        except Exception as e:
            print(f"  STL export failed ({e}) – save via File ▸ Export ▸ STL")
            return
    print(f"  Exported → {path}")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("\n── Viking Helmet Blender Generator ──")
    print(f"   OVAL_Z={OVAL_Z}  WORN={WORN_AMOUNT}  "
          f"PHI_OFFSET={RUNE_PHI_OFFSET}°  "
          f"NOSE {NOSE_W_TOP}→{NOSE_W_BOT} mm")

    clear_scene()

    steel = make_material("Steel", COL_STEEL, metallic=0.90, roughness=0.30)
    gold  = make_material("Gold",  COL_GOLD,  metallic=1.00, roughness=0.15)

    print("  Dome …")       ; build_dome(steel)
    print("  Rim …")        ; build_rim(gold)
    print("  Rivets …")     ; build_rivets(gold)
    if SHOW_NOSE:
        print("  Nose guard …") ; build_nose_guard(steel)
    else:
        print("  Nose guard … skipped (SHOW_NOSE = False)")
    if SHOW_RUNES:
        print("  Runes …")  ; build_runes(gold)
    else:
        print("  Runes … skipped (SHOW_RUNES = False)")

    bpy.context.scene.cursor.location = (0, 0, 0)
    names = [o.name for o in bpy.context.scene.objects
             if o.type == 'MESH']
    print(f"  Objects: {names}")

    export_stl(OUTPUT_STL)
    print("── Done! ──\n")


main()
