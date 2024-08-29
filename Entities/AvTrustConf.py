import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ScoringWeights:
    trusted: float = 0.50   # trusted-AV weighted ratio
    vt_ratio: float = 0.25  # positives / total
    severity: float = 0.15  # detection family match
    trend: float = 0.10     # rising detection count

    @classmethod
    def from_dict(cls, d: dict) -> 'ScoringWeights':
        return cls(**{k: float(v) for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AvTrust:
    name: re.Pattern
    trust_score: float
    detection_trust_list: List[str]  # Specify the type of List

    def __hash__(self):
        return hash((self.name, self.trust_score))

    def __eq__(self, other):
        if isinstance(other, AvTrust):
            return (
                    self.name == other.name and
                    self.trust_score == other.trust_score
            )
        return False

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@dataclass
class AvTrustConf:
    av_trust_list: List[AvTrust]
    default_trust: float
    score_threshold: float = 2.84          # deprecated filter absolute threshold
    scoring_threshold: float = 0.5        # normalized filter threshold [0,1]
    scoring_weights: ScoringWeights = field(default_factory=ScoringWeights)

    @classmethod
    def from_json(cls, av_trust_conf: dict) -> 'AvTrustConf':
        av_trust_list: List[AvTrust] = []
        default_trust: float = 0.0
        score_threshold: float = 2.84
        scoring_threshold: float = 0.5
        scoring_weights: ScoringWeights = ScoringWeights()
        for key_, value in av_trust_conf.items():
            if isinstance(value, dict):
                if key_ == 'weighted_scoring':
                    scoring_threshold = float(value.get('threshold', 0.5))
                    scoring_weights = ScoringWeights.from_dict(value.get('weights', {}))
                else:
                    av_trust_list.append(
                        AvTrust(
                            name=re.compile(key_, re.IGNORECASE),
                            trust_score=float(value['trust_score']),
                            detection_trust_list=list(value['detection_trust_list'])
                        ))
            elif key_ == 'score_threshold':
                score_threshold = float(value)
            elif isinstance(value, (float, int)):
                default_trust = float(value)
        return cls(
            av_trust_list=av_trust_list,
            default_trust=default_trust,
            score_threshold=score_threshold,
            scoring_threshold=scoring_threshold,
            scoring_weights=scoring_weights,
        )
