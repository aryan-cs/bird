"""Programmatically inspect TimF's F-22 Fuse 2/3/4 STLs.

Extracts bounding boxes, axis alignment, cross-section areas/contours, and locates
the existing EDF bore in Fuse 3. Outputs measurements as JSON for downstream
parametric design, and PNG cross-section plots for visual sanity check.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh

REPO_ROOT = Path(__file__).resolve().parents[2]
STL_DIR = REPO_ROOT / "jet" / "LW-PLA" / "F22_Raptor_Fuselage"
OUT_DIR = REPO_ROOT / "twin_edf"
PLOTS_DIR = OUT_DIR / "output" / "plots"
ANALYSIS_DIR = OUT_DIR / "analysis"

PARTS = {
    "fuse2": STL_DIR / "f22_raptor_fuse_2.stl",
    "fuse3": STL_DIR / "f22_raptor_fuse_3.stl",
    "fuse4": STL_DIR / "f22_raptor_fuse_4.stl",
}

# Number of evenly spaced cross-section stations to sample along the fuselage axis.
N_STATIONS = 21

# All three Fuse parts share a global coordinate system:
#   X = lateral (wingspan), centered at 0, range ~[-95.5, +95.5]
#   Y = longitudinal (nose-to-tail), parts stack with shared boundary Y values
#   Z = vertical, range roughly [-45, +25]
# Slice perpendicular to Y to get true fuselage cross-sections (looking forward).
FUSELAGE_AXIS = 1  # Y


@dataclass
class PartMeasurements:
    name: str
    file: str
    n_triangles: int
    bbox_min: list[float]
    bbox_max: list[float]
    size: list[float]
    longest_axis: int  # 0=x, 1=y, 2=z
    centroid: list[float]
    volume_mm3: float
    is_watertight: bool
    surface_area_mm2: float
    stations: list[dict]


def axis_name(i: int) -> str:
    return "xyz"[i]


def sample_cross_sections(
    mesh: trimesh.Trimesh, axis: int, n: int
) -> list[dict]:
    """Slice the mesh perpendicular to `axis` at n evenly spaced stations.

    Returns a list of dicts capturing: station value along axis, polygon count,
    total slice area (sum of polygon areas), bbox of slice in the perpendicular
    plane, and any circular features (radius/center) detected via min-enclosing
    circle proxy.
    """
    lo, hi = mesh.bounds[0][axis], mesh.bounds[1][axis]
    # Step in slightly from the ends so we don't slice at a degenerate boundary.
    margin = 0.02 * (hi - lo)
    stations = np.linspace(lo + margin, hi - margin, n)
    normal = np.zeros(3)
    normal[axis] = 1.0

    perp_axes = [a for a in range(3) if a != axis]

    results = []
    for s in stations:
        plane_origin = np.zeros(3)
        plane_origin[axis] = s
        section = mesh.section(plane_origin=plane_origin, plane_normal=normal)
        if section is None:
            results.append(
                {
                    "station": float(s),
                    "polygons": 0,
                    "total_area_mm2": 0.0,
                    "bbox_in_plane": None,
                    "n_outer_loops": 0,
                    "n_inner_loops": 0,
                }
            )
            continue
        # Project to 2D in the perpendicular plane.
        try:
            planar, _to_3d = section.to_planar()
        except Exception:
            results.append(
                {
                    "station": float(s),
                    "polygons": 0,
                    "total_area_mm2": 0.0,
                    "bbox_in_plane": None,
                    "n_outer_loops": 0,
                    "n_inner_loops": 0,
                }
            )
            continue

        polygons = list(planar.polygons_full)
        total_area = float(sum(p.area for p in polygons))
        if polygons:
            # 2D bbox across all polygons.
            xs = np.concatenate([np.asarray(p.exterior.coords)[:, 0] for p in polygons])
            ys = np.concatenate([np.asarray(p.exterior.coords)[:, 1] for p in polygons])
            bbox = [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]
        else:
            bbox = None

        # Count inner loops (interiors == ducting holes).
        n_inner = sum(len(p.interiors) for p in polygons)

        # Detect roughly circular interior loops — those are EDF bores.
        circular_holes = []
        for p in polygons:
            for ring in p.interiors:
                coords = np.asarray(ring.coords)
                cx, cy = coords[:, 0].mean(), coords[:, 1].mean()
                radii = np.hypot(coords[:, 0] - cx, coords[:, 1] - cy)
                r_mean = float(radii.mean())
                r_std = float(radii.std())
                # Tight std relative to mean => nearly circular.
                if r_mean > 5 and r_std / r_mean < 0.08:
                    circular_holes.append(
                        {
                            "cx": float(cx),
                            "cy": float(cy),
                            "r_mean_mm": r_mean,
                            "r_std_mm": r_std,
                        }
                    )

        results.append(
            {
                "station": float(s),
                "polygons": len(polygons),
                "total_area_mm2": total_area,
                "bbox_in_plane": bbox,
                "n_outer_loops": len(polygons),
                "n_inner_loops": n_inner,
                "circular_holes": circular_holes,
            }
        )
    return results, perp_axes


def render_cross_section_grid(
    mesh: trimesh.Trimesh,
    axis: int,
    n: int,
    out_path: Path,
    title: str,
) -> None:
    """Render an n-station cross-section grid for visual inspection."""
    lo, hi = mesh.bounds[0][axis], mesh.bounds[1][axis]
    margin = 0.02 * (hi - lo)
    stations = np.linspace(lo + margin, hi - margin, n)
    normal = np.zeros(3)
    normal[axis] = 1.0

    cols = 5
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.0, rows * 3.0))
    axes = np.atleast_2d(axes).ravel()

    perp = [a for a in range(3) if a != axis]
    plane_lim = [
        (mesh.bounds[0][perp[0]], mesh.bounds[1][perp[0]]),
        (mesh.bounds[0][perp[1]], mesh.bounds[1][perp[1]]),
    ]
    span = max(plane_lim[0][1] - plane_lim[0][0], plane_lim[1][1] - plane_lim[1][0])
    pad = 0.05 * span

    for ax, s in zip(axes, stations):
        plane_origin = np.zeros(3)
        plane_origin[axis] = s
        section = mesh.section(plane_origin=plane_origin, plane_normal=normal)
        ax.set_aspect("equal")
        ax.set_title(f"{axis_name(axis)}={s:.1f}", fontsize=8)
        ax.set_xlim(plane_lim[0][0] - pad, plane_lim[0][1] + pad)
        ax.set_ylim(plane_lim[1][0] - pad, plane_lim[1][1] + pad)
        ax.set_xticks([])
        ax.set_yticks([])
        if section is None:
            ax.text(0.5, 0.5, "empty", ha="center", va="center", transform=ax.transAxes)
            continue
        try:
            planar, _ = section.to_planar()
        except Exception:
            ax.text(0.5, 0.5, "err", ha="center", va="center", transform=ax.transAxes)
            continue
        for poly in planar.polygons_full:
            ext = np.asarray(poly.exterior.coords)
            ax.fill(ext[:, 0], ext[:, 1], color="#aac8ff", edgecolor="#1f4ea3", lw=0.6)
            for ring in poly.interiors:
                interior = np.asarray(ring.coords)
                ax.fill(
                    interior[:, 0],
                    interior[:, 1],
                    color="white",
                    edgecolor="#d04848",
                    lw=0.6,
                )

    for ax in axes[len(stations) :]:
        ax.axis("off")

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def inspect_part(name: str, stl_path: Path) -> PartMeasurements:
    print(f"[{name}] loading {stl_path.name} ({stl_path.stat().st_size / 1e6:.1f} MB)")
    mesh: trimesh.Trimesh = trimesh.load_mesh(stl_path, process=False)
    size = mesh.extents
    # Slice along the fuselage longitudinal axis Y (not the auto-longest, which is
    # often X = wingspan width).
    axis = FUSELAGE_AXIS
    print(
        f"[{name}] bbox size = {size.tolist()} mm  slicing along {axis_name(axis)} (fuselage axis)"
    )

    stations, _perp = sample_cross_sections(mesh, axis, N_STATIONS)

    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_path = PLOTS_DIR / f"{name}_original_sections.png"
    render_cross_section_grid(
        mesh,
        axis,
        N_STATIONS,
        plot_path,
        title=f"Original {name} cross-sections along {axis_name(axis)} (fuselage axis)",
    )
    print(f"[{name}] wrote cross-section plot -> {plot_path}")

    measurements = PartMeasurements(
        name=name,
        file=str(stl_path.relative_to(REPO_ROOT)),
        n_triangles=int(len(mesh.faces)),
        bbox_min=mesh.bounds[0].tolist(),
        bbox_max=mesh.bounds[1].tolist(),
        size=size.tolist(),
        longest_axis=axis,
        centroid=mesh.centroid.tolist(),
        volume_mm3=float(mesh.volume) if mesh.is_volume else float("nan"),
        is_watertight=bool(mesh.is_watertight),
        surface_area_mm2=float(mesh.area),
        stations=stations,
    )
    return measurements


def main() -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    all_measurements = {}
    for name, path in PARTS.items():
        m = inspect_part(name, path)
        all_measurements[name] = m.__dict__

    out = ANALYSIS_DIR / "measurements.json"
    with out.open("w") as f:
        json.dump(all_measurements, f, indent=2)
    print(f"\nwrote {out}")

    # Summary print
    print("\n=== SUMMARY ===")
    for name, m in all_measurements.items():
        sz = m["size"]
        la = axis_name(m["longest_axis"])
        print(
            f"  {name}: size = {sz[0]:.1f} x {sz[1]:.1f} x {sz[2]:.1f} mm | "
            f"longest axis = {la} | tris = {m['n_triangles']:,} | "
            f"watertight = {m['is_watertight']}"
        )
        # Find stations with circular holes (EDF bore detection)
        bore_stations = [
            s for s in m["stations"] if s.get("circular_holes")
        ]
        if bore_stations:
            print(f"    detected {len(bore_stations)} stations with circular bore features")
            for s in bore_stations[:3]:
                for h in s["circular_holes"]:
                    print(
                        f"      @ {la}={s['station']:.1f}: r = {h['r_mean_mm']:.2f} mm "
                        f"(std {h['r_std_mm']:.2f}), center ({h['cx']:.1f},{h['cy']:.1f})"
                    )


if __name__ == "__main__":
    main()
