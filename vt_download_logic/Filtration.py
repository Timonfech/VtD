import warnings
from typing import List, Union

from Entities.AvTrustConf import AvTrust, AvTrustConf
from Entities.Vt_inf import VTReportInfo
from configs.Configs import FiltrationConf
from db.DbConfig import AbstractDataHandler


class CustomFilter:
    av_trust_config: AvTrustConf
    filter_config: FiltrationConf
    source: AbstractDataHandler

    def __init__(self, filter_config: FiltrationConf, av_trust_config: AvTrustConf,
                 adh: AbstractDataHandler):
        self.filter_config = filter_config
        self.av_trust_config = av_trust_config
        self.source = adh

    # ── SHA-1 duplicate filter ────────────────────────────────────

    def filter_by_sha1(self, vt_inf_l: List['VTReportInfo']) -> List[VTReportInfo]:
        hashes = [vt_o.sha1 for vt_o in vt_inf_l]
        exist_i = self.source.get_existing_hash_i(hashes)
        return [vt_info for i, vt_info in enumerate(vt_inf_l)
                if not any(i == ei for ei in exist_i)]

    # ── Extension filter ──────────────────────────────────────────

    def filter_by_extensions(self, vt_inf: Union[List['VTReportInfo'], 'VTReportInfo']):
        result = []
        for vt_i in vt_inf:
            should_keep = True
            for ext_cat in self.filter_config.extensions:
                if any(pattern.search(vt_i.type) for pattern in ext_cat.regex_list):
                    should_keep = False
                    break
            if should_keep:
                result.append(vt_i)
        return result

    # ── Provider exclusion filter ─────────────────────────────────

    @staticmethod
    def exclude_provider_detections(
        vt_info_l: Union[List[VTReportInfo], VTReportInfo],
        excluded_provider: str,
    ) -> Union[List[VTReportInfo], VTReportInfo, None]:
        """
        Keep only files NOT detected by excluded_provider.

        The provider name comes from Config.excluded_provider (conf.json field
        "excluded_provider"). Previously this value was hardcoded at call-site.
        """
        if isinstance(vt_info_l, list):
            return [
                vt for vt in vt_info_l
                if not any(
                    r.name.lower() == excluded_provider.lower() and r.detection is not None
                    for r in vt.report
                )
            ]
        # single-object variant
        if not any(
            r.name.lower() == excluded_provider.lower() and r.detection is not None
            for r in vt_info_l.report
        ):
            return vt_info_l
        return None

    @staticmethod
    def detection_by_filter(
        vt_info_l: Union[List[VTReportInfo], VTReportInfo],
        by: str,
    ) -> Union[List[VTReportInfo], VTReportInfo, None]:
        """
        .. deprecated::
            Use :meth:`exclude_provider_detections` instead.
            The provider name should come from ``Config.excluded_provider``
            (conf.json key ``excluded_provider``), not be hardcoded.
        """
        warnings.warn(
            "detection_by_filter() is deprecated — "
            "use exclude_provider_detections(vt_info_l, config.excluded_provider).",
            DeprecationWarning,
            stacklevel=2,
        )
        return CustomFilter.exclude_provider_detections(vt_info_l, by)

    # ── Scoring filters ───────────────────────────────────────────

    def weighted_score_filter(
        self,
        vt_info_l: List[VTReportInfo],
        excluded_provider: str = "",
    ) -> List[VTReportInfo]:
        """Normalized multi-signal scorer. All signals in [0,1], threshold from config."""
        w = self.av_trust_config.scoring_weights
        threshold = self.av_trust_config.scoring_threshold
        max_trusted = sum(av.trust_score for av in self.av_trust_config.av_trust_list) or 1.0
        result = []

        for vt_info in vt_info_l:
            trusted_score = 0.0
            has_severity = False
            counted: set = set()

            for av_trust in self.av_trust_config.av_trust_list:
                for report in vt_info.report:
                    if not av_trust.name.search(report.name):
                        continue
                    counted.add(report.name.lower())
                    if report.detection is None:
                        break
                    trusted_score += av_trust.trust_score
                    if av_trust.detection_trust_list and any(
                        kw.lower() in report.detection.lower()
                        for kw in av_trust.detection_trust_list
                    ):
                        has_severity = True
                    break

            # signal 1: trusted AV weighted ratio
            s_trusted = trusted_score / max_trusted

            # signal 2: VT platform consensus
            try:
                total = max(int(vt_info.total), 1)
            except (ValueError, TypeError):
                total = 1
            s_vt = vt_info.positives / total

            # signal 3: severity (0 = no detection, 0.5 = detected, 1.0 = known family)
            if trusted_score == 0.0:
                s_severity = 0.0
            else:
                s_severity = 1.0 if has_severity else 0.5

            # signal 4: rising detection trend
            try:
                p_delta = int(vt_info.positives_delta)
            except (ValueError, TypeError):
                p_delta = 0
            s_trend = 1.0 if p_delta > 0 else 0.0

            score = (w.trusted  * s_trusted
                   + w.vt_ratio * s_vt
                   + w.severity * s_severity
                   + w.trend    * s_trend)

            if score >= threshold:
                result.append(vt_info)

        return result

    def dumb_score_filter(self, vt_info_l: List[VTReportInfo]) -> List[VTReportInfo]:
        """
        .. deprecated::
            Use :meth:`weighted_score_filter` instead.

        Known issues:
        - ``found_match``/``detection_found`` shared across AV-trust loop iterations
          → behaviour is order-dependent.
        - ``detection_trust_list`` field never used.
        """
        warnings.warn(
            "dumb_score_filter() is deprecated — "
            "use weighted_score_filter(vt_info_l, config.excluded_provider).",
            DeprecationWarning,
            stacklevel=2,
        )
        filtered = []
        for vt_info in vt_info_l:
            score = 0.0
            found_match = False
            detection_found = False
            for av_trust in self.av_trust_config.av_trust_list:
                for report in vt_info.report:
                    if av_trust.name.search(report.name):
                        if report.detection is not None:
                            score += av_trust.trust_score
                            detection_found = True
                            break
                        else:
                            detection_found = False
                        found_match = True
                        break
                    else:
                        found_match = False
            if (not found_match) and detection_found:
                score += self.av_trust_config.default_trust
            if score > self.av_trust_config.score_threshold:
                filtered.append(vt_info)
        return filtered

    @staticmethod
    def normalize(values):
        """Min-max normalisation utility"""
        min_val = min(values)
        max_val = max(values)
        if min_val == max_val:
            return [0.0] * len(values)
        return [(val - min_val) / (max_val - min_val) for val in values]
