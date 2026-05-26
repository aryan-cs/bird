"""Offscreen 3D renders of the modified Fuse 2/3/4 parts.

For each part: render iso, top, side, front views and combine into one PNG.
The ducts are shown as see-through cutaways by also overlaying the new_ducts
volume as a translucent body.

Uses pyrender if available (better lighting), otherwise falls back to a
matplotlib mplot3d projection.
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


PARTS = ["fuse2", "fuse3", "fuse4"]


def render_mpl_views(name: str) -> Path:
    """Matplotlib mplot3d render. Slow but dependable, no GL backend needed."""
    modified_path = P.OUT_STL / f"{name}_modified.stl"
    new_ducts_path = P.OUT_STL / f"{name}_new_ducts.stl"
    mesh = trimesh.load_mesh(modified_path, process=True)
    ducts = trimesh.load_mesh(new_ducts_path, process=True)

    # Downsample to keep matplotlib snappy
    if len(mesh.faces) > 30000:
        # Simplify by collapsing edges; trimesh.simplify_quadric_decimation needs open3d
        # Use a face sampling approach: take a random subset of faces.
        rng = np.random.default_rng(0)
        sel = rng.choice(len(mesh.faces), 30000, replace=False)
        v = mesh.vertices
        f = mesh.faces[sel]
        mesh = trimesh.Trimesh(vertices=v, faces=f, process=False)

    fig = plt.figure(figsize=(14, 4))
    views = [
        ("iso", (25, -60)),
        ("top (looking down Z)", (90, -90)),
        ("side (looking along X)", (0, 0)),
        ("front (looking along Y)", (0, -90)),
    ]
    for i, (label, (elev, azim)) in enumerate(views):
        ax = fig.add_subplot(1, len(views), i + 1, projection="3d")
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(f"{name} — {label}", fontsize=9)
        ax.set_box_aspect((1, 1, 0.5))
        # Plot modified mesh as a wireframe-with-faces using plot_trisurf
        ax.plot_trisurf(
            mesh.vertices[:, 0],
            mesh.vertices[:, 1],
            mesh.vertices[:, 2],
            triangles=mesh.faces,
            color="#bcd4f0",
            edgecolor="#1f4ea3",
            linewidth=0.05,
            alpha=0.7,
            shade=True,
        )
        # Overlay new ducts (the air channels) as a translucent red shape
        ax.plot_trisurf(
            ducts.vertices[:, 0],
            ducts.vertices[:, 1],
            ducts.vertices[:, 2],
            triangles=ducts.faces,
            color="#ff8888",
            edgecolor="#a31f1f",
            linewidth=0.05,
            alpha=0.25,
            shade=False,
        )
        # Equalize axes
        bbox_min = np.minimum(mesh.bounds[0], ducts.bounds[0])
        bbox_max = np.maximum(mesh.bounds[1], ducts.bounds[1])
        ctr = (bbox_min + bbox_max) / 2
        extent = (bbox_max - bbox_min).max() / 2
        ax.set_xlim(ctr[0] - extent, ctr[0] + extent)
        ax.set_ylim(ctr[1] - extent, ctr[1] + extent)
        ax.set_zlim(ctr[2] - extent / 2, ctr[2] + extent / 2)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")
        ax.tick_params(labelsize=6)

    fig.suptitle(
        f"{name}_modified.stl — solid (blue) + new ducts overlay (red translucent)",
        fontsize=11,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    out = P.OUT_PLOTS / f"{name}_3d_views.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def main():
    P.OUT_PLOTS.mkdir(parents=True, exist_ok=True)
    for name in PARTS:
        print(f"[{name}] rendering 3D views ...")
        out = render_mpl_views(name)
        print(f"[{name}] -> {out.relative_to(P.REPO_ROOT)}")
    print("\nDone.")


if __name__ == "__main__":
    main()
