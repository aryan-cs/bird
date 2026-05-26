"""Side-by-side cross-section comparison: TimF original vs twin-EDF modified.

For each of Fuse 2/3/4, slices both meshes perpendicular to the fuselage Y
axis at N stations and renders them in two columns (original | modified)
into one PNG per part for visual review.
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


N_STATIONS = 13
FUSELAGE_AXIS = 1


PARTS = {
    "fuse2": {
        "original": P.TIMF_STL_DIR / "f22_raptor_fuse_2.stl",
        "modified": P.OUT_STL / "fuse2_modified.stl",
    },
    "fuse3": {
        "original": P.TIMF_STL_DIR / "f22_raptor_fuse_3.stl",
        "modified": P.OUT_STL / "fuse3_modified.stl",
    },
    "fuse4": {
        "original": P.TIMF_STL_DIR / "f22_raptor_fuse_4.stl",
        "modified": P.OUT_STL / "fuse4_modified.stl",
    },
}


def section_segments_xz(mesh: trimesh.Trimesh, y: float):
    """Return the 2D line segments (in X-Z) where the mesh is cut by plane Y=y."""
    plane_origin = np.array([0.0, y, 0.0])
    plane_normal = np.array([0.0, 1.0, 0.0])
    section = mesh.section(plane_origin=plane_origin, plane_normal=plane_normal)
    if section is None:
        return []
    verts = section.vertices  # 3D, but lies on Y=y
    segments = []
    for entity in section.entities:
        idx = entity.points
        for i in range(len(idx) - 1):
            a = verts[idx[i]]
            b = verts[idx[i + 1]]
            # X, Z components
            segments.append(((a[0], a[2]), (b[0], b[2])))
    return segments


def draw_sections(name: str, paths: dict, out_path: Path) -> None:
    print(f"[{name}] rendering before/after sections")
    original = trimesh.load_mesh(paths["original"], process=True)
    modified = trimesh.load_mesh(paths["modified"], process=True)

    # Use original's Y range (modified should match)
    lo, hi = original.bounds[0][FUSELAGE_AXIS], original.bounds[1][FUSELAGE_AXIS]
    margin = 0.04 * (hi - lo)
    stations = np.linspace(lo + margin, hi - margin, N_STATIONS)

    fig, axes = plt.subplots(N_STATIONS, 2, figsize=(8, 2.0 * N_STATIONS))
    fig.suptitle(
        f"{name}: TimF original (left) vs twin-EDF modified (right) — cross-sections along Y",
        fontsize=12,
    )

    # Common XZ limits.
    xlim = (
        min(original.bounds[0][0], modified.bounds[0][0]) - 5,
        max(original.bounds[1][0], modified.bounds[1][0]) + 5,
    )
    zlim = (
        min(original.bounds[0][2], modified.bounds[0][2]) - 5,
        max(original.bounds[1][2], modified.bounds[1][2]) + 5,
    )

    for row, y in enumerate(stations):
        for col, mesh, color, label in [
            (0, original, "#1f4ea3", "orig"),
            (1, modified, "#a31f1f", "mod"),
        ]:
            ax = axes[row, col]
            ax.set_aspect("equal")
            ax.set_xlim(xlim)
            ax.set_ylim(zlim)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.axhline(0, color="#dddddd", lw=0.5, zorder=0)
            ax.axvline(0, color="#dddddd", lw=0.5, zorder=0)
            segments = section_segments_xz(mesh, y)
            for (a, b) in segments:
                ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.7)
            # Annotation
            if col == 0:
                ax.set_ylabel(f"y={y:.0f}", fontsize=8, rotation=0, labelpad=24)
            ax.set_title(label, fontsize=8)
            # Mark twin-EDF bore centers on modified column.
            if col == 1 and P.FUSE2_Y_FRONT <= y <= P.FUSE4_Y_REAR:
                for cx in (-P.DUCT_CENTER_X, +P.DUCT_CENTER_X):
                    circle = plt.Circle(
                        (cx, P.DUCT_CENTER_Z),
                        P.EDF_BORE_RADIUS,
                        fill=False,
                        color="#a31f1f",
                        lw=0.3,
                        ls="--",
                        alpha=0.4,
                    )
                    ax.add_patch(circle)

    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    print(f"[{name}] -> {out_path.relative_to(P.REPO_ROOT)}")


def main():
    P.OUT_PLOTS.mkdir(parents=True, exist_ok=True)
    for name, paths in PARTS.items():
        draw_sections(name, paths, P.OUT_PLOTS / f"{name}_before_after.png")
    print("\nDone.")


if __name__ == "__main__":
    main()
