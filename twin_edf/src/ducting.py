"""Parametric build123d geometry for the twin-EDF F-22 internal ducting.

Three functions produce the *air-channel volumes* (the negative space — the
ducts themselves) for each modified Fuse part. The volumes are intended to be
boolean-subtracted from TimF's STL to carve the new ducting out of the existing
airframe.

A fourth helper produces a "single-duct cutter" body sized to scoop out the
existing single-duct void from TimF's STL, so the rear of Fuse 2, Fuse 3, and
the front of Fuse 4 don't retain TimF's old single-channel walls.

Coordinate system matches TimF: X lateral, Y longitudinal, Z up.
"""

from __future__ import annotations

import math

from build123d import (
    BuildPart,
    BuildSketch,
    Box,
    Circle,
    Cylinder,
    Locations,
    Plane,
    Pos,
    Rectangle,
    Rot,
    Solid,
    loft,
    Align,
    Mode,
)

import parameters as P


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _y_plane(y: float) -> Plane:
    """A sketch plane perpendicular to the Y axis at position y, with in-plane
    X = global X and in-plane Y = global Z."""
    # Plane.XZ has x_dir=+X, y_dir=+Z, z_dir=-Y. Offsetting by -y along z_dir
    # moves the plane origin to (0, +y, 0) globally.
    return Plane.XZ.offset(-y)


def _intake_profile_at_front(y: float, side: int):
    """Front intake opening profile for one side of Fuse 2.

    side = +1 for starboard (X > 0), -1 for port (X < 0).
    Modeled as a rectangle on the sketch plane (which lies in the X-Z space at
    fuselage station y).
    """
    cx = side * (P.INTAKE_FRONT_OUTER_X + P.INTAKE_FRONT_INNER_X) / 2.0
    cz = P.INTAKE_FRONT_Z_CENTER
    width = P.INTAKE_FRONT_OUTER_X - P.INTAKE_FRONT_INNER_X
    height = P.INTAKE_FRONT_HEIGHT
    with BuildSketch(_y_plane(y)) as sk:
        with Locations((cx, cz)):
            Rectangle(width, height)
    return sk.sketch


def _circle_profile_at(y: float, side: int):
    """A 56-mm bore profile on the sketch plane at fuselage station y, centered
    at (side * DUCT_CENTER_X, DUCT_CENTER_Z)."""
    cx = side * P.DUCT_CENTER_X
    cz = P.DUCT_CENTER_Z
    with BuildSketch(_y_plane(y)) as sk:
        with Locations((cx, cz)):
            Circle(P.EDF_BORE_RADIUS)
    return sk.sketch


# ---------------------------------------------------------------------------
# Per-Fuse duct geometry
# ---------------------------------------------------------------------------


def make_fuse2_ducts() -> Solid:
    """Two intake channels through Fuse 2. They never merge.

    Each channel is a loft from a rounded-rectangle intake opening at the front
    face (y=171) to a 56-mm round bore at the rear face (y=341). Mirror-
    symmetric in X.
    """
    parts = []
    for side in (-1, +1):
        front = _intake_profile_at_front(P.FUSE2_Y_FRONT, side)
        rear = _circle_profile_at(P.FUSE2_Y_REAR, side)
        with BuildPart() as bp:
            loft([front, rear], ruled=False)
        parts.append(bp.part)
    # Union the two channels into a single body.
    return parts[0] + parts[1]


def make_fuse3_ducts() -> Solid:
    """Two straight 56-mm bores running the full length of Fuse 3."""
    parts = []
    for side in (-1, +1):
        cx = side * P.DUCT_CENTER_X
        cz = P.DUCT_CENTER_Z
        # Cylinder oriented along Y; build123d Cylinder is by default oriented
        # along Z, so rotate it.
        c = Cylinder(
            radius=P.EDF_BORE_RADIUS,
            height=P.FUSE3_LEN + 4.0,  # slight overrun for clean boolean
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        )
        # Re-orient: Cylinder's height is along Z. Rotate -90 about X so height
        # is along Y. Then translate so the cylinder spans Fuse 3.
        c = Rot(-90, 0, 0) * c
        c = Pos(cx, (P.FUSE3_Y_FRONT + P.FUSE3_Y_REAR) / 2.0, cz) * c
        parts.append(c)
    return parts[0] + parts[1]


def make_fuse4_ducts() -> Solid:
    """Twin → single merger through Fuse 4.

    Modeled as a 3-stage loft per side, then union at the centerline:
      Stage A (y=463 → y=520):
        Each side stays a 56-mm round bore.
      Stage B (y=520 → y=553):
        Each side morphs from a circle to half of a wide rectangle, with the
        inner edge migrating toward X=0 so the two halves meet at the
        centerline (merging into a single wide cross-section).
      Stage C (y=553 → y=653.4):
        Single wide rectangular duct, gently tapering to the nozzle exit size.
    """
    parts = []

    y_stage_a = P.FUSE4_Y_FRONT                 # 463.0
    y_stage_b_start = P.FUSE4_Y_FRONT + 57.0    # 520.0
    y_stage_b_end = P.FUSE4_Y_FRONT + P.MERGER_BLEND_LENGTH   # 553.0
    y_stage_c_end = P.FUSE4_Y_REAR              # 653.4

    # ---- Stage A: parallel circular ducts (per side) ---- #
    for side in (-1, +1):
        cx = side * P.DUCT_CENTER_X
        cz = P.DUCT_CENTER_Z
        c = Cylinder(
            radius=P.EDF_BORE_RADIUS,
            height=(y_stage_b_start - y_stage_a) + 2.0,
            align=(Align.CENTER, Align.CENTER, Align.CENTER),
        )
        c = Rot(-90, 0, 0) * c
        c = Pos(cx, (y_stage_a + y_stage_b_start) / 2.0, cz) * c
        parts.append(c)

    # ---- Stage B: morph circles to merged half-rectangle (per side) ---- #
    half_merged_width = P.NOZZLE_REAR_WIDTH / 2.0
    merged_height = P.NOZZLE_REAR_HEIGHT
    for side in (-1, +1):
        cx_start = side * P.DUCT_CENTER_X
        cx_end = side * (half_merged_width / 2.0)  # half-rect center, touching centerline
        cz = P.DUCT_CENTER_Z

        # Start profile: a circle.
        with BuildSketch(_y_plane(y_stage_b_start)) as sk_start:
            with Locations((cx_start, cz)):
                Circle(P.EDF_BORE_RADIUS)
        # End profile: half a rectangle (the side adjacent to centerline).
        with BuildSketch(_y_plane(y_stage_b_end)) as sk_end:
            with Locations((cx_end, cz)):
                Rectangle(half_merged_width, merged_height)

        with BuildPart() as bp:
            loft([sk_start.sketch, sk_end.sketch], ruled=False)
        parts.append(bp.part)

    # ---- Stage C: single rectangular duct tapering to exit ---- #
    with BuildSketch(_y_plane(y_stage_b_end)) as sk_c_front:
        with Locations((0, P.NOZZLE_REAR_Z_CENTER)):
            Rectangle(P.NOZZLE_REAR_WIDTH, P.NOZZLE_REAR_HEIGHT)
    with BuildSketch(_y_plane(y_stage_c_end - 0.5)) as sk_c_rear:
        with Locations((0, P.NOZZLE_REAR_Z_CENTER)):
            # Slight taper toward the exit (10% narrower W, same H)
            Rectangle(P.NOZZLE_REAR_WIDTH * 0.9, P.NOZZLE_REAR_HEIGHT)
    with BuildPart() as bp:
        loft([sk_c_front.sketch, sk_c_rear.sketch], ruled=False)
    parts.append(bp.part)

    # Union everything
    result = parts[0]
    for p in parts[1:]:
        result = result + p
    return result


# ---------------------------------------------------------------------------
# Old-duct cutter (for removing TimF's existing single-channel void shape)
# ---------------------------------------------------------------------------


def make_old_duct_cutter_for(part_name: str) -> Solid:
    """A simple bounding-box cutter sized to the area where TimF's old duct
    walls live. Subtracting this from TimF's STL flattens out the old internal
    structure so we can re-cut the new twin ducts cleanly.

    NOTE: this is a coarse cutter — it will also remove some material from
    the inner fuselage skin. The intent for v1 is just to clear the way; a
    refined cutter that conforms more precisely to the old duct walls is a
    next-rev improvement.
    """
    if part_name == "fuse2":
        y_front, y_rear = P.FUSE2_Y_FRONT, P.FUSE2_Y_REAR
    elif part_name == "fuse3":
        y_front, y_rear = P.FUSE3_Y_FRONT, P.FUSE3_Y_REAR
    elif part_name == "fuse4":
        y_front, y_rear = P.FUSE4_Y_FRONT, P.FUSE4_Y_REAR
    else:
        raise ValueError(part_name)

    length = y_rear - y_front
    width = 2 * P.OLD_DUCT_CUTTER_X_HALFWIDTH
    height = 2 * P.OLD_DUCT_CUTTER_Z_HALFHEIGHT

    b = Box(width, length, height, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    b = Pos(0, (y_front + y_rear) / 2.0, P.DUCT_CENTER_Z) * b
    return b


if __name__ == "__main__":
    print("Generating geometry (smoke test) ...")
    for name, factory in [
        ("fuse2", make_fuse2_ducts),
        ("fuse3", make_fuse3_ducts),
        ("fuse4", make_fuse4_ducts),
    ]:
        s = factory()
        bbox = s.bounding_box()
        print(
            f"  {name} duct volume: bbox X[{bbox.min.X:.1f},{bbox.max.X:.1f}] "
            f"Y[{bbox.min.Y:.1f},{bbox.max.Y:.1f}] "
            f"Z[{bbox.min.Z:.1f},{bbox.max.Z:.1f}]  volume={s.volume:.0f} mm^3"
        )
