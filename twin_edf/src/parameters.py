"""Centralized design parameters for the twin-EDF F-22 conversion.

Coordinate system (matches TimF's STLs — they share one global frame):
  X = lateral (wingspan), centered at 0, range ~[-95.5, +95.5]
  Y = longitudinal (nose-to-tail), increases toward the tail
  Z = vertical, up positive

Part boundaries from measurements.json (read from TimF's STLs):
  Fuse 2: Y 171.0 .. 341.0
  Fuse 3: Y 341.0 .. 463.0
  Fuse 4: Y 463.0 .. 653.4
"""

# -------- Y-axis (longitudinal) part boundaries -------- #
FUSE2_Y_FRONT = 171.0
FUSE2_Y_REAR = 341.0
FUSE3_Y_FRONT = 341.0
FUSE3_Y_REAR = 463.0
FUSE4_Y_FRONT = 463.0
FUSE4_Y_REAR = 653.4

FUSE2_LEN = FUSE2_Y_REAR - FUSE2_Y_FRONT  # 170 mm
FUSE3_LEN = FUSE3_Y_REAR - FUSE3_Y_FRONT  # 122 mm
FUSE4_LEN = FUSE4_Y_REAR - FUSE4_Y_FRONT  # 190.4 mm

# -------- EDF parameters -------- #
# 50 mm EDFs (FMS / XRP / XFly): outer housing diameter is ~52 mm.
# Sized tight to the housing so the bore fits inside the F-22 fuselage's
# narrow Z-envelope at the bore X-position.
EDF_OD = 50.0                # nominal fan OD
EDF_HOUSING_OD = 52.0        # outer housing OD
EDF_BORE_DIAMETER = 52.0     # bore = housing OD + a few tenths of tolerance
EDF_BORE_RADIUS = EDF_BORE_DIAMETER / 2.0
EDF_AXIAL_LENGTH = 70.0      # length of the parallel-duct section per EDF

# -------- Twin-duct layout -------- #
# Two parallel 52 mm bores. Centerlines moved closer to fuselage X-center so
# each bore stays within the inverted-U cross-section's Z envelope at that X.
# Wall between bores = 2*28 - 52 = 4 mm — minimum printable, max packing.
DUCT_CENTER_X = 28.0             # |X| centerline (so ±28)
DUCT_CENTER_Z = -5.0             # vertical center; pulled toward fuselage geometric center

# -------- Intake geometry (Fuse 2) -------- #
INTAKE_FRONT_WIDTH = 40.0        # approx. width of each intake opening
INTAKE_FRONT_HEIGHT = 40.0       # bounded to fit within fuselage envelope at front
INTAKE_FRONT_OUTER_X = 58.0      # |X| of the outer edge of each intake at the front
INTAKE_FRONT_INNER_X = 18.0      # |X| of the inner edge of each intake at the front
INTAKE_FRONT_Z_CENTER = -5.0     # match duct center Z
# Rear face of Fuse 2 ports = matching circles, ready to mate Fuse 3 bores.
# Same X/Z center as the duct.

# -------- Merger / nozzle (Fuse 4) -------- #
# At the front face of Fuse 4 (y=463) we accept two circular ducts and
# blend them into a single outlet by the rear (y=653.4).
NOZZLE_REAR_WIDTH = 60.0         # horizontal nozzle exit width
NOZZLE_REAR_HEIGHT = 22.0        # vertical nozzle exit height (fits within tapering tail)
NOZZLE_REAR_Z_CENTER = -5.0      # match duct center Z
MERGER_BLEND_LENGTH = 90.0       # mm of length over which the two ducts blend
                                 # into the single rectangular outlet
# The merger geometry is a loft from two circles at y=463 to a single
# rectangular slot at y=463+MERGER_BLEND_LENGTH, then a straight nozzle
# section to y=653.4.

# -------- Wall thickness & fillets -------- #
DUCT_WALL_T = 1.6                # min wall thickness for the new internal
                                 # ducting (matches TimF's printing intent)
EDGE_FILLET = 2.0                # fillet on internal edges to soften flow

# -------- Print and tolerance -------- #
# Holes are printed slightly oversize for press-fit / tolerance.
PRINT_TOLERANCE = 0.3

# -------- Cutter sizing (for boolean subtract against TimF's STL) -------- #
# Bound the cutter body that subtracts the OLD single-duct void from
# TimF's geometry. We oversize generously in X and Z to ensure full removal
# of the existing duct walls; Y is bound to the part length.
OLD_DUCT_CUTTER_X_HALFWIDTH = 50.0
OLD_DUCT_CUTTER_Z_HALFHEIGHT = 35.0

# -------- Output paths -------- #
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_STL = REPO_ROOT / "twin_edf" / "output" / "stl"
OUT_STEP = REPO_ROOT / "twin_edf" / "output" / "step"
OUT_PLOTS = REPO_ROOT / "twin_edf" / "output" / "plots"
TIMF_STL_DIR = REPO_ROOT / "jet" / "LW-PLA" / "F22_Raptor_Fuselage"


def summary() -> str:
    return (
        f"twin-EDF parameters:\n"
        f"  EDF bore diameter   = {EDF_BORE_DIAMETER} mm\n"
        f"  duct centerline |X| = {DUCT_CENTER_X} mm\n"
        f"  duct centerline  Z  = {DUCT_CENTER_Z} mm\n"
        f"  wall between ducts  = {2 * DUCT_CENTER_X - EDF_BORE_DIAMETER:.1f} mm\n"
        f"  Fuse 2 length       = {FUSE2_LEN:.1f} mm\n"
        f"  Fuse 3 length       = {FUSE3_LEN:.1f} mm\n"
        f"  Fuse 4 length       = {FUSE4_LEN:.1f} mm\n"
        f"  merger blend length = {MERGER_BLEND_LENGTH:.1f} mm\n"
        f"  nozzle exit (WxH)   = {NOZZLE_REAR_WIDTH} x {NOZZLE_REAR_HEIGHT} mm\n"
    )


if __name__ == "__main__":
    print(summary())
