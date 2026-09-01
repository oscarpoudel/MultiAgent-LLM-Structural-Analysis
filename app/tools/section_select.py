"""Steel section selection (AISC 360-16).

Deterministic closed-form calculations. No LLM involvement.

References:
- AISC 360-16, Chapter F (Flexural Members) -- LTB per F2
- AISC 360-16, Chapter V (Shear) -- V15
- AISC 360-16, Chapter E (Compression Members) -- E3

All internal calculations in mm and MPa (N/mm^2); outputs converted to kN / kN-m.
"""
from __future__ import annotations

import math

from app.models import BeamSelectionInputs, ColumnSelectionInputs
from app.tools.sections import _W_SHAPES, SteelSection

E_STEEL_MPA = 200000.0


def _section_props(s: SteelSection) -> tuple[float, float, float]:
    """Return (J [mm4], Cw [mm6], h0 [mm])."""
    d = s.d_mm
    bf = s.bf_mm
    tf = s.tf_mm
    tw = s.tw_mm
    ix = s.ix_m4 * 1e12  # mm4
    # Torsion constant (open I-section approximation)
    j = (1.0 / 3.0) * (2.0 * bf * tf**3 + (d - 2.0 * tf) * tw**3)
    # Warping constant
    cw = (ix * bf**2) / 4.0
    h0 = d - tf
    return j, cw, h0


def _compact(s: SteelSection, fy_mpa: float) -> bool:
    """Flange and web compactness (AISC Table B4.1b)."""
    d, bf, tf, tw = s.d_mm, s.bf_mm, s.tf_mm, s.tw_mm
    flange_slender = bf / (2.0 * tf)
    lambda_pf = 0.38 * math.sqrt(E_STEEL_MPA / fy_mpa) * (bf / (2.0 * tf))
    web_slender = d / tw
    lambda_pw = 1.49 * math.sqrt(E_STEEL_MPA / fy_mpa)
    return (flange_slender <= lambda_pf) and (web_slender <= lambda_pw)


def _ltb_capacity(s: SteelSection, fy_mpa: float, lb_m: float, cb: float = 1.0) -> float:
    """Nominal flexural strength Mn (kN-m) with LTB per AISC 360 F2."""
    z = s.zx_m3 * 1e9  # mm3
    sx = s.sx_m3 * 1e9  # mm3
    ix = s.ix_m4 * 1e12  # mm4
    j, cw, h0 = _section_props(s)

    mp = fy_mpa * z / 1e6  # kN-m
    mf = fy_mpa * sx / 1e6  # kN-m

    if lb_m <= 0:
        return mp if _compact(s, fy_mpa) else mf

    lb = lb_m * 1000.0  # mm
    rts = math.sqrt(ix / sx)  # mm
    lp = 1.76 * rts * math.sqrt(E_STEEL_MPA / fy_mpa)  # mm
    term = (j * h0) / (2.0 * sx * rts**2)
    lr = 1.95 * rts * (E_STEEL_MPA / fy_mpa) * (
        term + math.sqrt(term**2 + 6.76 * (cw / sx**2) * (fy_mpa / E_STEEL_MPA) ** 2)
    )  # mm

    if lb <= lp:
        mn = mp
    elif lb <= lr:
        mn = cb * (mp - (mp - 0.7 * mf) * (lb - lp) / (lr - lp))
        mn = min(mn, mp)
    else:
        fcr = (
            cb
            * math.pi**2
            * E_STEEL_MPA
            * j
            * math.sqrt(1.0 + (lb * h0 / (2.0 * math.pi * rts)) ** 2)
            / (lb**2 * (sx / rts**2))
        )
        fcr = min(fcr, 0.7 * fy_mpa)
        mn = fcr * sx / 1e6

    if not _compact(s, fy_mpa):
        mn = min(mn, mf)
    return mn


def _shear_capacity(s: SteelSection, fy_mpa: float) -> float:
    """Nominal shear strength Vn (kN) per AISC 360 V15."""
    d, tw, tf = s.d_mm, s.tw_mm, s.tf_mm
    h = d - 2.0 * tf
    aw = d * tw  # mm2
    htw = h / tw
    lambda_w = htw / (1.10 * math.sqrt(3.0 * E_STEEL_MPA / fy_mpa))
    if lambda_w <= 1.10:
        vn = 0.60 * fy_mpa * aw
    elif lambda_w <= 1.37:
        vn = (1.0 - (fy_mpa / (5.0 * math.sqrt(3.0) * E_STEEL_MPA)) * htw**2) * 0.60 * fy_mpa * aw
    else:
        kv = 5.0 + 2.0 / htw**2
        vn = 1.10 * math.sqrt(3.0) * kv * E_STEEL_MPA / htw * aw
    return vn / 1000.0  # kN


def _column_capacity(s: SteelSection, fy_mpa: float, kl_m: float) -> float:
    """Nominal compressive strength Pn (kN) per AISC 360 E3."""
    a = s.area_m2 * 1e6  # mm2
    ry = s.ry_m * 1000.0  # mm
    if ry <= 0:
        return 0.0
    klr = kl_m * 1000.0 / ry
    fe = math.pi**2 * E_STEEL_MPA / (klr**2)
    if klr <= 4.71 * math.sqrt(E_STEEL_MPA / fy_mpa):
        fc = 0.658 ** (fy_mpa / fe) * fy_mpa
    else:
        fc = 0.877 * fe
    return fc * a / 1000.0  # kN


def select_beam(inputs: BeamSelectionInputs) -> dict:
    """Select lightest W-shape adequate for Mu, Vu, Lb (AISC 360)."""
    warnings: list[str] = []
    phi_b = 0.90
    phi_v = 0.90

    candidates = []
    for s in sorted(_W_SHAPES.values(), key=lambda x: x.weight_kg_per_m):
        mn = _ltb_capacity(s, inputs.fy_mpa, inputs.unbraced_length_m, inputs.cb)
        vn = _shear_capacity(s, inputs.fy_mpa)
        if phi_b * mn >= inputs.moment_kn_m and phi_v * vn >= inputs.shear_kn:
            candidates.append({
                "name": s.name,
                "weight_kg_per_m": s.weight_kg_per_m,
                "depth_mm": s.d_mm,
                "phi_mn_kn_m": round(phi_b * mn, 2),
                "phi_vn_kn": round(phi_v * vn, 2),
                "flex_util": round(inputs.moment_kn_m / (phi_b * mn), 3),
                "shear_util": round(inputs.shear_kn / (phi_v * vn), 3),
            })

    if not candidates:
        warnings.append("No W-shape in database is adequate for the given loads.")
        return {
            "method": "AISC 360-16 section selection (flexure + shear)",
            "code_reference": "AISC 360-16 Chapters F, V",
            "selected": None,
            "candidates": [],
            "warnings": warnings,
        }

    return {
        "method": "AISC 360-16 section selection (flexure + shear)",
        "code_reference": "AISC 360-16 Chapters F, V",
        "selected": candidates[0],
        "candidates": candidates[:5],
        "warnings": warnings,
    }


def select_column(inputs: ColumnSelectionInputs) -> dict:
    """Select lightest W-shape adequate for Pu, KL (AISC 360 E3)."""
    warnings: list[str] = []
    phi_c = 0.90

    candidates = []
    for s in sorted(_W_SHAPES.values(), key=lambda x: x.weight_kg_per_m):
        pn = _column_capacity(s, inputs.fy_mpa, inputs.kl_m)
        if phi_c * pn >= inputs.axial_load_kn:
            candidates.append({
                "name": s.name,
                "weight_kg_per_m": s.weight_kg_per_m,
                "depth_mm": s.d_mm,
                "phi_pn_kn": round(phi_c * pn, 2),
                "util": round(inputs.axial_load_kn / (phi_c * pn), 3),
            })

    if not candidates:
        warnings.append("No W-shape in database is adequate for the given load.")
        return {
            "method": "AISC 360-16 column section selection (E3)",
            "code_reference": "AISC 360-16 Chapter E",
            "selected": None,
            "candidates": [],
            "warnings": warnings,
        }

    return {
        "method": "AISC 360-16 column selection (E3)",
        "code_reference": "AISC 360-16 Chapter E",
        "selected": candidates[0],
        "candidates": candidates[:5],
        "warnings": warnings,
    }
