from pathlib import Path

from Entities.Vt_inf import VTReportInfo


class FileProp:
    def __init__(self, name: str, vt_report: VTReportInfo, destination: Path):
        self.name = name
        self.vt_report = vt_report
        self.destination = destination

    def get_destination(self) -> Path:
        return self.destination

    def get_link(self) -> str:
        return self.vt_report.link

    def get_md5(self) -> str:
        return self.vt_report.md5

    def get_sha256(self) -> str:
        return self.vt_report.sha256

    def get_sha1(self) -> str:
        return self.vt_report.sha1
