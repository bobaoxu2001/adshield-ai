from src.risk.public_evidence import public_evidence_registry
from src.risk.taxonomy import CATEGORY_NAMES


def test_uw_perception_by_category_is_present_and_sane() -> None:
    uw = public_evidence_registry()["uw_summary"]
    rows = uw["perception_by_content_category"]
    assert rows, "expected per-category perception rows"
    # Every reported category meets the minimum-cell size and carries bounded shares.
    for row in rows:
        assert row["ad_count"] >= 15
        for key in ("mean_deceptive_share", "mean_clickbait_share", "mean_manipulative_share"):
            assert 0.0 <= row[key] <= 1.0
    # Rows are ordered by perceived deception + clickbait (descending).
    scores = [row["mean_deceptive_share"] + row["mean_clickbait_share"] for row in rows]
    assert scores == sorted(scores, reverse=True)


def test_uw_taxonomy_alignment_maps_to_real_categories() -> None:
    uw = public_evidence_registry()["uw_summary"]
    mapped = {row["mapped_risk_category"] for row in uw["perception_by_content_category"] if row["mapped_risk_category"]}
    assert mapped, "expected at least one UW category mapped to the taxonomy"
    assert mapped.issubset(set(CATEGORY_NAMES))
    # The most risk-relevant human-perceived categories must include the health and
    # deceptive-claims areas the taxonomy prioritizes.
    aligned = uw["taxonomy_alignment"]["risk_relevant_mapped_categories"]
    assert "Health / Weight Loss / Pharmaceuticals Risk" in aligned
    assert "Deceptive / Misleading Claims" in aligned


def test_uw_alignment_confers_no_promotion_eligibility() -> None:
    """External perception evidence must never read as enforcement ground truth."""
    uw = public_evidence_registry()["uw_summary"]
    assert uw["promotion_gate_effect"] == "informative_only"
    readout = uw["taxonomy_alignment"]["readout"].lower()
    assert "not per-ad enforcement" in readout
