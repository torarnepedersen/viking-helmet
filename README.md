# Viking Helmet 3D Model Generator

Two Python scripts that generate a parametric Viking helmet as a 3D model — one using pure Python/numpy, one using Blender's scripting API.

![Viking helmet with dome, rim, rivets, nose guard and Elder Futhark runes]

---

## Scripts

### `generate_helmet.py` — Pure Python STL generator

Generates `viking_helmet.stl` directly using numpy for geometry and `struct` for binary STL output. No mesh libraries needed.

**Requirements:** Python 3.x + numpy

```bash
pip install numpy
python generate_helmet.py
```

Output: `viking_helmet.stl` (~500 KB, ~10 000 triangles)

---

### `generate_helmet_blender.py` — Blender script

Generates the helmet inside Blender with separate named objects per part, PBR materials (steel + gold), and optional modifiers. Exports STL automatically.

**Requirements:** Blender 3.x / 4.x / 5.x (no extra add-ons needed)

**Run from Blender's Scripting workspace:**
1. Open Blender → switch to the *Scripting* workspace
2. Open `generate_helmet_blender.py`
3. Press **Run Script**

**Run headlessly:**
```bash
blender --background --python generate_helmet_blender.py
```

---

## Parameters

All parameters are at the top of each script. Edit and re-run to update the model.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `R` | 100.0 | Dome outer radius (mm) |
| `CUT_Z` | -18.0 | Cut-plane height — how deep the helmet sits (mm) |
| `OVAL_Z` | 1.30 | Z stretch: `1.0` = sphere, `1.3` = 30 % taller/egg-shaped |
| `RIM_OUT` | 8.0 | How far the rim protrudes beyond the dome edge (mm) |
| `RIM_H` | 10.0 | Rim height (mm) |
| `SHOW_NOSE` | `True` | Include nose guard |
| `NOSE_W_TOP` | 40.0 | Nose guard width at top (mm) |
| `NOSE_W_BOT` | 20.0 | Nose guard width at bottom/tip (mm) |
| `NOSE_H` | 68.0 | Nose guard length (mm) |
| `NOSE_T` | 5.0 | Nose guard thickness (mm) |
| `N_RIVETS` | 16 | Number of rivets around the rim |
| `RIVET_R` | 4.0 | Rivet hemisphere radius (mm) |
| `SHOW_RUNES` | `True` | Include Elder Futhark runes on the dome |
| `RUNE_PHI_OFFSET` | 45.0 | Shift runes lower toward the rim (degrees) |
| `RUNE_SIZE` | 18.0 | Rune glyph size on dome surface (mm) |
| `WORN_AMOUNT` | 0.20 | Battle wear: `0.0` = pristine, `1.0` = heavily damaged |
| `WORN_SEED` | 42 | Random seed — change for a different damage pattern |

### Blender-only parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DOME_SEGS_T` | 72 | Azimuthal segments (higher = smoother) |
| `DOME_SEGS_P` | 36 | Polar segments |
| `SUBD_DOME` | 1 | Subdivision Surface level on dome (`0` = off) |
| `COL_STEEL` | `(0.55, 0.57, 0.60)` | Steel colour (R, G, B) |
| `COL_GOLD` | `(0.90, 0.73, 0.18)` | Gold colour (R, G, B) |
| `OUTPUT_STL` | auto | Export path — set to `""` to skip export |

---

## Helmet parts

| Part | Description |
|------|-------------|
| **Dome** | Oval UV sphere, clipped at the cut-plane |
| **Rim** | Solid annular ring at the base of the dome |
| **Rivets** | 16 hemispherical rivets on top of the rim |
| **Nose guard** | Tapered rectangular guard at the front |
| **Runes** | 8 Elder Futhark runes raised above the dome surface: *fehu, uruz, thurisaz, ansuz, gebo, raido, wunjo, tiwaz* |

---

## Viewing / slicing the STL

- **[MeshLab](https://www.meshlab.net/)** — free mesh viewer
- **[Blender](https://www.blender.org/)** — File → Import → STL
- **[UltiMaker Cura](https://ultimaker.com/software/ultimaker-cura/)** — drag and drop for 3D printing
- **Windows 3D Viewer** — built-in, just double-click the `.stl`
