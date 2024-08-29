from collections.abc import Mapping
from dataclasses import dataclass
from typing import List


@dataclass
class Report(Mapping):
    name: str
    detection: str
    base_version: str
    base_version_date: str

    def __init__(self, key: str, value: list):
        self.name = key
        if isinstance(value, list):
            self.detection = value[0]
            self.base_version = value[1]
            self.base_version_date = value[2]
        else:
            raise ValueError(
                "Invalid value type for value (it should be list of [detection,base_version, base_version_date]")

    @classmethod
    def create(cls, name: str, detection: str | None, base_version: str, base_version_date: str):
        return cls(name, [detection, base_version, base_version_date])

    def __getitem__(self, __key):
        return self.name, [self.detection, self.base_version, self.base_version_date]

    def __len__(self):
        return 1

    def __iter__(self):
        return iter((self.name, [self.detection, self.base_version, self.base_version_date]))


@dataclass
class VTReportInfo:
    first_seen: str
    last_seen: str
    link: str
    md5: str
    name: str
    positives: int
    positives_delta: int
    report: List[Report]  # dict[str, list[str]]
    sha1: str
    sha256: str
    size: int
    source_country: str
    ssdeep: str
    source_id: str
    tags: List[str]
    timestamp: int
    total: str
    type: str
    vhash: str

    def __hash__(self):
        return hash((self.sha1, self.md5))

    @classmethod
    def from_dict(cls, data) -> 'VTReportInfo':
        instance = cls(**data)
        instance.report = [Report(name_, rep_l) for name_, rep_l in data["report"].items()]
        return instance

    @classmethod
    def from_list_of_dict(cls, data_l: List[dict]) -> List['VTReportInfo']:
        return [cls(**data) for data in data_l]

    # def __post_init__(self):
    #     all_attributes = set(self.__annotations__.keys())
    #     dataclass_fields = set(f.name for f in fields(self))
    #
    #     for attribute in all_attributes - dataclass_fields:
    #         delattr(self, attribute)
    # def get_detected_av(self) -> [Report]:
    #     av_do_detect = []
    #     for name, av_prop_l in self.report.items():
    #         report = Report(key=name, value=av_prop_l)
    #         if (report.detection is not None) or (report.detection != "" or report.detection != "null"):
    #             av_do_detect.append(report)
    #     return av_do_detect

    # def get_reports(self) -> [Report]:
    #     reports = []
    #     for name, av_prop_l in self.report.items():
    #         report = Report(key=name, value=av_prop_l)
    #         reports.append(report)
    #     return reports

    # @classmethod
    # def from_json(cls, string_from_vt: str):
    #     vt_obj = json.loads(string_from_vt)
    #     first_seen_ = vt_obj['first_seen']
    #     last_seen_ = vt_obj['last_seen']
    #     link_ = vt_obj['link']
    #     md_5 = vt_obj['md5']
    #     name_ = vt_obj['name']
    #     positives_ = vt_obj['positives']
    #     delta_ = vt_obj['positives_delta']
    #     report_dict = vt_obj['report']
    #     # [Report(name_, list_) for name, list_ in report_dict.items()]  # !!
    #     sha_1 = vt_obj['sha1']
    #     sha_256_ = vt_obj['sha256']
    #     size_ = vt_obj['size']
    #     country_ = vt_obj['source_country']
    #     source_id_ = vt_obj['source_id']
    #     ssdeep_ = vt_obj['ssdeep']
    #     tags_ = vt_obj['tags']
    #     timestamp_ = vt_obj['timestamp']
    #     total_scanned = vt_obj['total']
    #     type_ = vt_obj['type']
    #     vhash_ = vt_obj['vhash']
    #     cls(first_seen_, last_seen_, link_, md_5, name_, positives_, delta_, report_, sha_1, sha_256_,
    #         size_, country_, source_id_, ssdeep_, tags_, timestamp_, total_scanned, type_, vhash_)
    #
    # def to_json(self) -> str:
    #     vt_dict = {
    #             "first_seen": self.first_seen.isoformat(),
    #             "last_seen": self.last_seen.isoformat(),
    #             "link": self.link,
    #             "md5_hash": self.md5_hash,
    #             "file_name": self.file_name,
    #             "positives": self.positives,
    #             "positives_delta": self.positives_delta,
    #             "reports": [dict(report) for report in self.reports],
    #             "sha1": self.sha1,
    #             "sha_256": self.sha_256,
    #             "size": self.size,
    #             "source_country": self.source_country,
    #             "source_id": self.source_id,
    #             "ssdeep": self.ssdeep,
    #             "tags": self.tags,
    #             "timestamp": self.timestamp,
    #             "total_scanners_count": self.total_scanners_count.isoformat(),
    #             "type_": self.type_,
    #             "vhash": self.vhash
    #         }
    #     return json.dumps(vt_dict)
