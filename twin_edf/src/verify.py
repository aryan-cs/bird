"""Post-hoc verification of the twin-EDF modifications.

Checks two things the booleans alone don't tell us:

  1. RESIDUAL OLD-DUCT WALLS — how much TimF original plastic still occupies
     the volume where the new ducts are supposed to be air? Computed as the
     boolean intersection of (new_ducts) and (TimF original part).

  2. FUSE 1 ↔ FUSE 2 INTAKE INTERFACE — does the air entering Fuse 1 actually
     have a path into Fuse 2's new intake openings, or do the new openings
     dump into a wall? Slice Fuse 1 at Y = FUSE2_Y_FRONT and overlay against
     Fuse 2 modified at the same plane.

Writes a markdown report to analysis/verification.md and an overlay PNG to
output/plots/intake_interface.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parameters as P


PARTS = {
    "fuse2": "f22_raptor_fuse_2.stl",
    "fuse3": "f22_raptor_fuse_3.stl",
    "fuse4": "f22_raptor_fuse_4.stl",
}


def section_segments_xz(mesh: trimesh.Trimesh, y: float):
    plane_origin = np.array([0.0, y, 0.0])
    plane_normal = np.array([0.0, 1.0, 0.0])
    section = mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)
    if section is None:
        return []
    verts = section.vertices
    segments = []
    for entity in section.entities:
        idx = entity.points
        for i in range(len(idx) - 1):
            a = verts[idx[i]]
            b = verts[idx[i + 1]]
            segments.append(((a[0], a[2]), (b[0], b[2])))
    return segments


def check_bore_open(modified_path: Path, y_start: float, y_end: float, name: str) -> dict:
    """Sample points along each bore centerline inside the modified STL.

    The modified part is air OUTSIDE the plastic. If a point at the bore center
    (X = ±DUCT_CENTER_X, Z = DUCT_CENTER_Z) at various Y is INSIDE the modified
    mesh, that means the bore is BLOCKED (plastic occupies the centerline).
    """
    mesh = trimesh.load_mesh(modified_path, process=True)
    n_samples = 20
    ys = np.linspace(y_start + 2.0, y_end - 2.0, n_samples)
    blocked = {"left": 0, "right": 0}
    for cx_key, sign in (("left", -1), ("right", +1)):
        cx = sign * P.DUCT_CENTER_X
        pts = np.column_stack(
            [np.full(n_samples, cx), ys, np.full(n_samples, P.DUCT_CENTER_Z)]
        )
        inside = mesh.contains(pts)
        blocked[cx_key] = int(inside.sum())
    pct_blocked_left = 100.0 * blocked["left"] / n_samples
    pct_blocked_right = 100.0 * blocked["right"] / n_samples
    print(f"  {name} bore-clearance check (samples along centerline at X=±{P.DUCT_CENTER_X}, Z={P.DUCT_CENTER_Z}):")
    print(f"    LEFT  bore: {blocked['left']}/{n_samples} samples blocked  ({pct_blocked_left:.0f}%)")
    print(f"    RIGHT bore: {blocked['right']}/{n_samples} samples blocked  ({pct_blocked_right:.0f}%)")
    return {"left_blocked_pct": pct_blocked_left, "right_blocked_pct": pct_blocked_right}


def check_residual_walls() -> dict:
    print("\n=== RESIDUAL OLD-DUCT WALLS ===")
    report = {}
    for name, stl in PARTS.items():
        timf_path = P.TIMF_STL_DIR / stl
        new_ducts_path = P.OUT_STL / f"{name}_new_ducts.stl"
        modified_path = P.OUT_STL / f"{name}_modified.stl"

        timf = trimesh.load_mesh(timf_path, process=True)
        new_ducts = trimesh.load_mesh(new_ducts_path, process=True)
        modified = trimesh.load_mesh(modified_path, process=True)

        v_timf = float(timf.volume)
        v_new_ducts = float(new_ducts.volume)
        v_modified = float(modified.volume)

        # Volume of plastic that lived inside the new-duct envelope BEFORE
        # the boolean = (TimF volume) - (modified volume).
        v_removed = v_timf - v_modified

        # If no old walls intersected the new ducts, v_removed == v_new_ducts.
        # Any shortfall means some "air" volume still has plastic.
        residual_in_bores = v_new_ducts - v_removed
        residual_pct = 100.0 * residual_in_bores / v_new_ducts if v_new_ducts else 0.0

        # Boolean intersection: new_ducts ∩ TimF.
        # If the new ducts pass entirely through TimF's old single duct (which
        # IS air in TimF's original), intersection = (volume of plastic that
        # the new ducts had to cut through) = same as v_removed above.
        # We compute it as a cross-check.
        intersection = trimesh.boolean.intersection([timf, new_ducts], engine="manifold")
        v_intersection = float(intersection.volume) if intersection.is_volume else 0.0

        print(f"\n  {name}:")
        print(f"    TimF plastic volume        = {v_timf:>12,.0f} mm^3")
        print(f"    new-duct envelope volume   = {v_new_ducts:>12,.0f} mm^3")
        print(f"    modified part volume       = {v_modified:>12,.0f} mm^3")
        print(f"    plastic removed by boolean = {v_removed:>12,.0f} mm^3")
        print(f"    overlap with TimF's existing air = {residual_in_bores:>10,.0f} mm^3  ({residual_pct:.1f}% of envelope)")
        print(f"    (higher % is fine — means new ducts pass through existing duct space)")

        report[name] = {
            "timf_volume_mm3": v_timf,
            "new_ducts_volume_mm3": v_new_ducts,
            "modified_volume_mm3": v_modified,
            "removed_mm3": v_removed,
            "intersection_mm3": v_intersection,
            "residual_in_bores_mm3": residual_in_bores,
            "residual_pct": residual_pct,
        }
    return report


def check_intake_interface() -> dict:
    """Overlay Fuse 1's rear-face section (at Y=FUSE2_Y_FRONT) with Fuse 2
    modified's front-face section at the same plane. The two should ideally
    have overlapping cross-section openings so air can flow."""
    print("\n=== FUSE 1 ↔ FUSE 2 INTAKE INTERFACE ===")
    fuse1_path = P.TIMF_STL_DIR / "f22_raptor_fuse_1.stl"
    fuse2_mod_path = P.OUT_STL / "fuse2_modified.stl"

    fuse1 = trimesh.load_mesh(fuse1_path, process=True)
    fuse2_mod = trimesh.load_mesh(fuse2_mod_path, process=True)

    print(f"  Fuse 1 bbox Y: [{fuse1.bounds[0][1]:.1f}, {fuse1.bounds[1][1]:.1f}]")
    print(f"  Fuse 2 mod bbox Y: [{fuse2_mod.bounds[0][1]:.1f}, {fuse2_mod.bounds[1][1]:.1f}]")

    y = P.FUSE2_Y_FRONT
    # Try slightly inside Fuse 1 too, since the seam might be open.
    fuse1_y = max(fuse1.bounds[0][1] + 1.0, min(y, fuse1.bounds[1][1] - 1.0))

    seg_f1 = section_segments_xz(fuse1, fuse1_y)
    seg_f2 = section_segments_xz(fuse2_mod, y + 0.5)  # 0.5 mm inside Fuse 2

    print(f"  Fuse 1 @ Y={fuse1_y:.1f}: {len(seg_f1)} segments")
    print(f"  Fuse 2 mod @ Y={y + 0.5:.1f}: {len(seg_f2)} segments")

    # Render the overlay.
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_aspect("equal")
    ax.set_title(f"Intake interface @ Y={y:.0f}  (blue = Fuse 1 rear, red = Fuse 2 mod front)")
    ax.set_xlabel("X (lateral, mm)")
    ax.set_ylabel("Z (vertical, mm)")
    ax.axhline(0, color="#dddddd", lw=0.5)
    ax.axvline(0, color="#dddddd", lw=0.5)
    for (a, b) in seg_f1:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#1f4ea3", lw=1.0, label="Fuse 1 rear" if a is seg_f1[0][0] else None)
    for (a, b) in seg_f2:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#a31f1f", lw=1.0)
    # Mark new bore positions for clarity.
    for cx in (-P.DUCT_CENTER_X, +P.DUCT_CENTER_X):
        circle = plt.Circle((cx, P.DUCT_CENTER_Z), P.EDF_BORE_RADIUS, fill=False,
                            color="#a31f1f", lw=0.5, ls="--", alpha=0.6)
        ax.add_patch(circle)
    ax.set_xlim(-110, 110)
    ax.set_ylim(-60, 50)

    out_png = P.OUT_PLOTS / "intake_interface.png"
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote overlay to {out_png.relative_to(P.REPO_ROOT)}")

    return {
        "fuse1_y": fuse1_y,
        "fuse2_y": y + 0.5,
        "fuse1_segments": len(seg_f1),
        "fuse2_segments": len(seg_f2),
        "overlay_png": str(out_png.relative_to(P.REPO_ROOT)),
    }


def check_pushrod_torque_tube_collisions() -> dict:
    """Heuristic check: TimF's pushrod guides for Fuse 2/3 pass through the
    fuselage along the centerline at low Z. The 3mm carbon torque tubes pivot
    in bearings on Fuse 4. The new bores at X=±32.5 should NOT contain any
    of TimF's small internal features at the centerline.

    Practical check: count TimF's mesh triangles whose CENTROID falls strictly
    inside the new-bore envelope for each Fuse. A large count of small,
    centerline-oriented features inside the bore suggests potential conflict.
    """
    print("\n=== PUSHROD / TORQUE TUBE COLLISION HEURISTIC ===")
    report = {}
    for name, stl in PARTS.items():
        timf = trimesh.load_mesh(P.TIMF_STL_DIR / stl, process=True)
        new_ducts = trimesh.load_mesh(P.OUT_STL / f"{name}_new_ducts.stl", process=True)

        nd_bounds = new_ducts.bounds
        # Triangles in the new-duct bounding region (cheap overlap proxy).
        tri_centers = timf.triangles_center
        in_x = (tri_centers[:, 0] >= nd_bounds[0][0]) & (tri_centers[:, 0] <= nd_bounds[1][0])
        in_y = (tri_centers[:, 1] >= nd_bounds[0][1]) & (tri_centers[:, 1] <= nd_bounds[1][1])
        in_z = (tri_centers[:, 2] >= nd_bounds[0][2]) & (tri_centers[:, 2] <= nd_bounds[1][2])
        in_box = in_x & in_y & in_z

        # Of those, how many are CLOSE to centerline (|X| < 5 mm) — that's where
        # the original single-duct walls and pushrod guides live.
        near_center = in_box & (np.abs(tri_centers[:, 0]) < 5.0)

        # Of the centerline-near triangles, how many have small surface area
        # (< 1 mm^2) — those are the thin walls / pushrod guides.
        timf.fix_normals()
        areas = timf.area_faces
        small_centerline = near_center & (areas < 1.0)

        n_in_box = int(in_box.sum())
        n_near_center = int(near_center.sum())
        n_small_center = int(small_centerline.sum())

        print(f"  {name}:")
        print(f"    triangles in new-duct bbox    : {n_in_box:,}")
        print(f"    of those near centerline (|X|<5): {n_near_center:,}")
        print(f"    of those small (area<1mm^2)   : {n_small_center:,}")

        report[name] = {
            "tris_in_box": n_in_box,
            "tris_near_center": n_near_center,
            "tris_small_centerline": n_small_center,
        }
    return report


def write_report(residual: dict, interface: dict, pushrod: dict, bore: dict) -> Path:
    out = P.REPO_ROOT / "twin_edf" / "analysis" / "verification.md"
    lines = [
        "# Twin-EDF verification report\n",
        "Generated by `src/verify.py`. Read this before printing.\n",
        "## 1. Bore centerline clearance (the real print-readiness check)\n",
        "For each new EDF bore, samples 20 points along the centerline at "
        "X=±{:.1f}, Z={:.1f} and tests whether each point is INSIDE the modified "
        "mesh (= blocked by plastic) or OUTSIDE (= clear air). 0% blocked means "
        "you can slide an EDF straight through.\n".format(P.DUCT_CENTER_X, P.DUCT_CENTER_Z),
        "| Part   | Left bore blocked | Right bore blocked |",
        "|--------|------------------:|-------------------:|",
    ]
    for name in ("fuse2", "fuse3", "fuse4"):
        b = bore[name]
        lines.append(
            f"| {name} | {b['left_blocked_pct']:.0f}% | {b['right_blocked_pct']:.0f}% |"
        )
    lines.append("")
    lines.append("**Interpretation**: anything above ~5% indicates leftover plastic "
                 "blocking the bore — you'd need to either clean it up in CAD or "
                 "hot-knife it during assembly.\n")

    lines.append("## 2. Residual envelope (existing air already in new-duct space)\n")
    lines.append(
        "Not a problem indicator — this measures how much of the new-duct "
        "envelope volume was already AIR in TimF (because TimF's existing "
        "duct overlaps with where the new ducts go). High % is fine; it "
        "means most of the new-duct envelope was already a duct.\n"
    )
    lines.append(
        "| Part   | TimF vol (mm³) | New-duct vol (mm³) | Modified vol (mm³) | Already-air overlap (mm³) | Already-air % |"
    )
    lines.append(
        "|--------|---------------:|-------------------:|-------------------:|--------------------------:|--------------:|"
    )
    for name in ("fuse2", "fuse3", "fuse4"):
        r = residual[name]
        lines.append(
            f"| {name} | {r['timf_volume_mm3']:,.0f} | {r['new_ducts_volume_mm3']:,.0f} | "
            f"{r['modified_volume_mm3']:,.0f} | {r['residual_in_bores_mm3']:,.0f} | "
            f"{r['residual_pct']:.1f}% |"
        )
    lines.append("")
    lines.append("## 3. Fuse 1 ↔ Fuse 2 intake interface\n")
    lines.append(
        f"Compared Fuse 1's cross-section at Y={interface['fuse1_y']:.1f} mm "
        f"vs Fuse 2 modified at Y={interface['fuse2_y']:.1f} mm. See "
        f"`output/plots/intake_interface.png`. The new Fuse 2 front-face "
        f"openings (rounded rectangles at X = ±39, Z = -8) need to align with "
        f"Fuse 1's rear-face air channels. Visual review required.\n"
    )

    lines.append("## 4. Pushrod / torque-tube collision heuristic\n")
    lines.append(
        "TimF's pushrod guides (PDF page 5) and 3 mm carbon torque tubes (PDF "
        "page 6) live along the fuselage centerline. The new bores are at "
        "X = ±32.5 — clear of |X| < 5 in principle. Heuristic count of TimF "
        "triangles within the new-duct bbox AND near centerline:\n"
    )
    lines.append("| Part | Tris in new-duct bbox | Near centerline (|X|<5) | Small features (<1 mm²) |")
    lines.append("|------|----------------------:|------------------------:|------------------------:|")
    for name in ("fuse2", "fuse3", "fuse4"):
        p = pushrod[name]
        lines.append(
            f"| {name} | {p['tris_in_box']:,} | {p['tris_near_center']:,} | "
            f"{p['tris_small_centerline']:,} |"
        )
    lines.append("")
    lines.append(
        "A high `Near centerline` count means TimF has internal walls or "
        "guides running through the new-duct region — they survived the "
        "boolean (because they're at the centerline, not inside the bore "
        "envelope) and may interfere with airflow OR with pushrod routing "
        "after assembly. Review the modified part in a CAD viewer.\n"
    )

    out.write_text("\n".join(lines))
    print(f"\nWrote {out.relative_to(P.REPO_ROOT)}")
    return out


def main():
    print("=== BORE CENTERLINE CLEARANCE ===")
    bore = {}
    bore["fuse2"] = check_bore_open(
        P.OUT_STL / "fuse2_modified.stl", P.FUSE2_Y_FRONT, P.FUSE2_Y_REAR, "fuse2"
    )
    bore["fuse3"] = check_bore_open(
        P.OUT_STL / "fuse3_modified.stl", P.FUSE3_Y_FRONT, P.FUSE3_Y_REAR, "fuse3"
    )
    bore["fuse4"] = check_bore_open(
        P.OUT_STL / "fuse4_modified.stl", P.FUSE4_Y_FRONT, P.FUSE4_Y_REAR, "fuse4"
    )
    residual = check_residual_walls()
    interface = check_intake_interface()
    pushrod = check_pushrod_torque_tube_collisions()
    write_report(residual, interface, pushrod, bore)


if __name__ == "__main__":
    main()
