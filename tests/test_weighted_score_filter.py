"""
Tests for CustomFilter.weighted_score_filter.

Setup:
  - HighTrust AV: trust_score=0.8, detection_trust_list=["Trojan", "Backdoor"]
  - LowTrust  AV: trust_score=0.2, detection_trust_list=[]
  - max_trusted = 1.0
  - weights: trusted=0.50, vt_ratio=0.25, severity=0.15, trend=0.10
  - scoring_threshold = 0.50
"""
import re

import pytest
from unittest.mock import MagicMock

from Entities.AvTrustConf import AvTrust, AvTrustConf, ScoringWeights
from Entities.Vt_inf import VTReportInfo, Report
from vt_download_logic.Filtration import CustomFilter


# ── Helpers ───────────────────────────────────────────────────────────────────

def _report(name: str, detection: str | None) -> Report:
    return Report.create(name=name, detection=detection,
                         base_version="", base_version_date="")


def _vti(positives: int, total: int, delta: int, reports: list) -> VTReportInfo:
    return VTReportInfo(
        first_seen="", last_seen="", link="", md5="", name="",
        positives=positives, positives_delta=delta,
        report=reports,
        sha1="", sha256="", size=1, source_country="", ssdeep="",
        source_id="", tags=[], timestamp=0, total=str(total), type="", vhash=""
    )


@pytest.fixture
def cf() -> CustomFilter:
    high = AvTrust(name=re.compile("HighTrust", re.I), trust_score=0.8,
                   detection_trust_list=["Trojan", "Backdoor"])
    low  = AvTrust(name=re.compile("LowTrust",  re.I), trust_score=0.2,
                   detection_trust_list=[])
    w    = ScoringWeights(trusted=0.50, vt_ratio=0.25, severity=0.15, trend=0.10)
    conf = AvTrustConf(av_trust_list=[high, low], default_trust=0.05,
                       score_threshold=2.84, scoring_threshold=0.50, scoring_weights=w)
    return CustomFilter(MagicMock(), conf, MagicMock())


# ── Cannot-pass cases ─────────────────────────────────────────────────────────

def test_trend_alone_cannot_pass(cf):
    """trend=1.0 contributes max 0.10 — far below threshold 0.50."""
    vti = _vti(1, 70, 1, [_report("UnknownAV", "SomeThreat")])
    assert cf.weighted_score_filter([vti]) == []


def test_max_score_without_trusted_av_is_below_threshold(cf):
    """Theoretical ceiling w/o trusted: vt_ratio(0.25) + trend(0.10) = 0.35 < 0.50."""
    vti = _vti(70, 70, 5, [_report("UnknownAV", "SomeThreat")])
    assert cf.weighted_score_filter([vti]) == []


def test_low_trust_av_plus_full_trend_cannot_pass(cf):
    """LowTrust(0.2)+high vt_ratio+trend = 0.10+0.07+0.075+0.10 = 0.35 < 0.50."""
    vti = _vti(20, 70, 1, [_report("LowTrust", "Generic")])
    assert cf.weighted_score_filter([vti]) == []


def test_trusted_av_present_but_clean_cannot_pass(cf):
    """Trusted AV in report with no detection → s_trusted=0, s_severity=0."""
    vti = _vti(0, 70, 0, [_report("HighTrust", None)])
    assert cf.weighted_score_filter([vti]) == []


def test_excluded_provider_detection_ignored(cf):
    """Excluded provider's detection must not contribute to score."""
    vti = _vti(1, 70, 1, [_report("OurProvider", "Trojan")])
    assert cf.weighted_score_filter([vti], excluded_provider="OurProvider") == []


# ── Must-pass cases ───────────────────────────────────────────────────────────

def test_high_trust_with_severity_and_trend_passes(cf):
    """HighTrust(0.8)+severity+vt_ratio(50/70)+trend = 0.40+0.179+0.15+0.10 = 0.83."""
    vti = _vti(50, 70, 1, [_report("HighTrust", "Trojan.Gen.Win32")])
    assert len(cf.weighted_score_filter([vti])) == 1


def test_high_trust_with_severity_no_trend_still_passes(cf):
    """High signals on 3 dimensions are enough: 0.40+0.179+0.15 = 0.73 > 0.50."""
    vti = _vti(50, 70, 0, [_report("HighTrust", "Trojan.Gen.Win32")])
    assert len(cf.weighted_score_filter([vti])) == 1


# ── Mixed list ────────────────────────────────────────────────────────────────

def test_mixed_list_only_good_survives(cf):
    good = _vti(50, 70, 1, [_report("HighTrust", "Trojan.Win32")])
    bad  = _vti(1,  70, 1, [_report("UnknownAV", "Generic")])
    result = cf.weighted_score_filter([good, bad])
    assert len(result) == 1
    assert result[0] is good
