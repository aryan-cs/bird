"""Render the full assembled fuselage (Fuse 2 + Fuse 3 + Fuse 4) with the
twin-duct internals overlaid translucently. One image, clear at-a-glance view.
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


def downsample(mesh: trimesh.Trimesh, target: int) -> trimesh.Trimesh:
    if len(mesh.faces) <= target:
        return mesh
    rng = np.random.default_rng(0)
    sel = rng.choice(len(mesh.faces), target, replace=False)
    return trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces[sel], process=False)


def main():
    P.OUT_PLOTS.mkdir(parents=True, exist_ok=True)

    parts = []
    ducts = []
    for name in ("fuse2", "fuse3", "fuse4"):
        m = trimesh.load_mesh(P.OUT_STL / f"{name}_modified.stl", process=True)
        d = trimesh.load_mesh(P.OUT_STL / f"{name}_new_ducts.stl", process=True)
        parts.append(downsample(m, 12000))
        ducts.append(downsample(d, 8000))

    # Concatenate
    full_part = trimesh.util.concatenate(parts)
    full_ducts = trimesh.util.concatenate(ducts)

    fig = plt.figure(figsize=(16, 10))
    views = [
        ("Isometric", (22, -65)),
        ("Top (down Z)", (90, -90)),
        ("Side (along X)", (0, 0)),
        ("Front (along Y, looking aft)", (0, -90)),
        ("Rear (along Y, looking fwd)", (0, 90)),
        ("Iso rear-quarter", (18, 60)),
    ]
    for i, (label, (elev, azim)) in enumerate(views):
        ax = fig.add_subplot(2, 3, i + 1, projection="3d")
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(label, fontsize=10)
        ax.set_box_aspect((1, 2, 0.6))
        ax.plot_trisurf(
            full_part.vertices[:, 0],
            full_part.vertices[:, 1],
            full_part.vertices[:, 2],
            triangles=full_part.faces,
            color="#a8c8ec",
            edgecolor="#1f4ea3",
            linewidth=0.03,
            alpha=0.6,
            shade=True,
        )
        ax.plot_trisurf(
            full_ducts.vertices[:, 0],
            full_ducts.vertices[:, 1],
            full_ducts.vertices[:, 2],
            triangles=full_ducts.faces,
            color="#ff6666",
            edgecolor="#a31f1f",
            linewidth=0.03,
            alpha=0.3,
            shade=False,
        )
        bbox_min = full_part.bounds[0]
        bbox_max = full_part.bounds[1]
        ctr = (bbox_min + bbox_max) / 2
        extent_y = (bbox_max[1] - bbox_min[1]) / 2 * 1.1
        extent_xz = max(bbox_max[0] - bbox_min[0], bbox_max[2] - bbox_min[2]) / 2 * 1.2
        ax.set_xlim(ctr[0] - extent_xz, ctr[0] + extent_xz)
        ax.set_ylim(ctr[1] - extent_y, ctr[1] + extent_y)
        ax.set_zlim(ctr[2] - extent_xz / 2, ctr[2] + extent_xz / 2)
        ax.set_xlabel("X", fontsize=7)
        ax.set_ylabel("Y", fontsize=7)
        ax.set_zlabel("Z", fontsize=7)
        ax.tick_params(labelsize=6)

    fig.suptitle(
        "Twin-EDF F-22 — Fuse 2 + Fuse 3 + Fuse 4 modified (blue solid + red twin-duct overlay)",
        fontsize=13,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = P.OUT_PLOTS / "assembly_3d_views.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    print(f"wrote {out.relative_to(P.REPO_ROOT)}")


if __name__ == "__main__":
    main()
