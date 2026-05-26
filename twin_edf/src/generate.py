"""Generate the modified Fuse 2/3/4 STL files for twin-EDF conversion.

Steps:
  1. Build the new twin-duct air-channel volumes (negative-space cutters)
     and the "old-duct" coarse cutter via build123d.
  2. Export each as a stand-alone STL + STEP for inspection.
  3. Boolean subtract from TimF's original STL using trimesh+manifold3d.
  4. Write the final modified part STLs to output/stl/.

Files produced:
  output/stl/fuseN_new_ducts.stl         # the new twin-duct air channel volume
  output/stl/fuseN_old_duct_cutter.stl   # the bounding cutter for the old duct
  output/stl/fuseN_modified.stl          # TimF's part - old_cutter - new_ducts
  output/step/fuseN_new_ducts.step       # STEP source for parametric tweaks
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from build123d import Part, export_step, export_stl
from scipy.spatial import ConvexHull
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parameters as P
import ducting


PARTS_SPEC = {
    "fuse2": {
        "timf_stl": P.TIMF_STL_DIR / "f22_raptor_fuse_2.stl",
        "make_ducts": ducting.make_fuse2_ducts,
    },
    "fuse3": {
        "timf_stl": P.TIMF_STL_DIR / "f22_raptor_fuse_3.stl",
        "make_ducts": ducting.make_fuse3_ducts,
    },
    "fuse4": {
        "timf_stl": P.TIMF_STL_DIR / "f22_raptor_fuse_4.stl",
        "make_ducts": ducting.make_fuse4_ducts,
    },
}


def b123d_to_trimesh(part) -> trimesh.Trimesh:
    """Tessellate a build123d Part to a trimesh.Trimesh via STL round-trip."""
    tmp = P.REPO_ROOT / "twin_edf" / "output" / "stl" / "_tmp.stl"
    export_stl(part, str(tmp))
    mesh = trimesh.load_mesh(tmp)
    tmp.unlink(missing_ok=True)
    return mesh


def boolean_subtract(skin: trimesh.Trimesh, cutter: trimesh.Trimesh) -> trimesh.Trimesh:
    """Boolean subtract `cutter` from `skin` using manifold3d backend."""
    result = trimesh.boolean.difference([skin, cutter], engine="manifold")
    return result


def make_outer_envelope(mesh: trimesh.Trimesh, y_min: float, y_max: float,
                        n_stations: int = 80) -> trimesh.Trimesh:
    """Build a solid filled mesh whose outer surface follows TimF's actual
    outer envelope at each Y station.

    Method: slice the mesh perpendicular to Y at n stations; at each station
    take the 2D convex hull of the cross-section's vertices in the (X, Z)
    plane; extrude that hull as a thin Y-aligned slab; union all slabs.

    This gives a much tighter outer skin than the whole-mesh convex hull
    (which extends past TimF's actual outer surface in regions where the
    fuselage is concave).
    """
    eps = 0.001
    ys = np.linspace(y_min + eps, y_max - eps, n_stations)
    slab_height = (y_max - y_min) / (n_stations - 1) * 1.1  # 10% overlap
    slabs = []
    for y in ys:
        section = mesh.section(plane_origin=(0, y, 0), plane_normal=(0, 1, 0))
        if section is None:
            continue
        # Project section vertices into 2D (X, Z).
        verts = section.vertices
        pts_2d = verts[:, [0, 2]]
        # Deduplicate for stability.
        pts_2d = np.unique(pts_2d.round(3), axis=0)
        if len(pts_2d) < 3:
            continue
        try:
            hull = ConvexHull(pts_2d)
        except Exception:
            continue
        hull_pts = pts_2d[hull.vertices]
        poly = Polygon(hull_pts)
        if not poly.is_valid or poly.area < 1.0:
            continue
        # Extrude as a slab in Z, height = slab_height. trimesh extrudes
        # along +Z by default; we then rotate to align with global +Y.
        slab = trimesh.creation.extrude_polygon(poly, height=slab_height)
        # extrude_polygon: polygon in XY plane, extruded along Z.
        # We rotate 90° about X so extrude direction becomes +Y, and the
        # polygon's Y axis maps to global Z. Then translate to Y.
        rot = trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0])
        slab.apply_transform(rot)
        slab.apply_translation([0, y - slab_height / 2.0, 0])
        slabs.append(slab)
    combined = trimesh.util.concatenate(slabs)
    # Use manifold union to collapse overlapping slabs into one watertight body.
    try:
        unioned = trimesh.boolean.union(slabs, engine="manifold")
        return unioned
    except Exception:
        return combined


def make_part_for(name: str, spec: dict) -> None:
    print(f"\n=== {name} ===")
    P.OUT_STL.mkdir(parents=True, exist_ok=True)
    P.OUT_STEP.mkdir(parents=True, exist_ok=True)

    # 1. New duct geometry
    t0 = time.time()
    new_ducts = spec["make_ducts"]()
    print(f"  new ducts built in {time.time()-t0:.1f}s  (volume {new_ducts.volume:.0f} mm^3)")

    stl_new = P.OUT_STL / f"{name}_new_ducts.stl"
    step_new = P.OUT_STEP / f"{name}_new_ducts.step"
    export_stl(new_ducts, str(stl_new))
    export_step(new_ducts, str(step_new))
    print(f"  wrote {stl_new.relative_to(P.REPO_ROOT)} + STEP")

    # 2. CLEAN-INTERIOR strategy:
    #    a. Compute the convex hull of TimF's part. This gives us a SOLID
    #       version of his outer envelope, with NO internal duct walls.
    #       The F-22 fuselage is mostly convex, so the hull approximates
    #       TimF's outer skin closely (tradeoff: minor concave features
    #       like wing-root undercuts and canopy depressions are smoothed).
    #    b. Subtract the new twin-duct envelope. Result: a watertight part
    #       whose outer surface matches TimF's outer envelope and whose
    #       only internal voids are the new twin ducts.
    print(f"  loading TimF: {spec['timf_stl'].name} ...")
    t0 = time.time()
    timf_mesh = trimesh.load_mesh(spec["timf_stl"], process=True)
    print(f"    loaded in {time.time()-t0:.1f}s  ({len(timf_mesh.faces):,} tris, "
          f"watertight={timf_mesh.is_watertight})")

    # Determine the Y range for this part (from TimF's bbox).
    y_min = float(timf_mesh.bounds[0][1])
    y_max = float(timf_mesh.bounds[1][1])

    print(f"  building per-Y outer envelope (80 stations, Y∈[{y_min:.1f},{y_max:.1f}]) ...")
    t0 = time.time()
    envelope = make_outer_envelope(timf_mesh, y_min, y_max, n_stations=80)
    print(f"    envelope built in {time.time()-t0:.1f}s  ({len(envelope.faces):,} tris, "
          f"volume {envelope.volume/1000:.0f} cm^3)")

    print(f"  tessellating new ducts to mesh ...")
    t0 = time.time()
    new_ducts_mesh = b123d_to_trimesh(new_ducts)
    print(f"    done in {time.time()-t0:.1f}s")

    print(f"  boolean: envelope - new_ducts ...")
    try:
        t0 = time.time()
        final = boolean_subtract(envelope, new_ducts_mesh)
        print(f"    done in {time.time()-t0:.1f}s  ({len(final.faces):,} tris, "
              f"watertight={final.is_watertight})")

        out_path = P.OUT_STL / f"{name}_modified.stl"
        final.export(out_path)
        print(f"  wrote {out_path.relative_to(P.REPO_ROOT)} "
              f"(volume {final.volume/1000:.0f} cm^3)")
    except Exception as e:
        print(f"  !! boolean failed: {e}")
        print(f"     skipping {name}_modified.stl")


def main():
    print(P.summary())
    for name, spec in PARTS_SPEC.items():
        make_part_for(name, spec)
    print("\nDone.")


if __name__ == "__main__":
    main()
