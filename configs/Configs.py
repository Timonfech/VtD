import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

from Entities.AvTrustConf import AvTrustConf
from db.DbConfig import AbstractDataHandler, FilesDBOperations
from my_io.custom_io import CustomAsyncBatchifier


class Scanner:
    name: str
    os_: str
    start_reference: str
    update_param: str

    def __init__(self, scanner_name: str, os_: str, start_reference: str, update_param: str):
        self.name = scanner_name
        self.os_ = os_
        self.start_reference = start_reference
        self.update_param = update_param

    @classmethod
    def from_dict(cls, scanner_name: str, fields: dict[str, str | List]) -> 'Scanner':
        os_ = fields.get('os_', '')
        start_reference = fields.get('start_reference', '')
        update_param = fields.get('update_param', '')
        return cls(scanner_name, os_, start_reference, update_param)


@dataclass
class BufferConf:
    buffer_destination: str
    crone_job_time: str
    fp_score_and_less: float
    malware_score_and_less: float


class Threat:
    def __init__(self, name: str, threat_data: dict):
        self.name = name
        self.significance_score = threat_data.get("significance_score", 0.0)
        self.patterns = threat_data.get("patterns", [])

    name: str
    significance_score: float
    patterns: List[str]


@dataclass
class VTFilterConf:
    threats: List[Threat]

    def __init__(self, threats: dict):
        self.threats = [Threat(name=name, threat_data=threat_fields) for name, threat_fields in threats.items()]


@dataclass()
class ExtensionsCategory:
    # ext_regex: InitVar[Dict[str, List[str]]]
    data_alias: str
    regex_list: List[re.Pattern]


@dataclass
class FiltrationConf:
    vt_filter_conf: VTFilterConf
    extensions: List[ExtensionsCategory]

    def __init__(self, vt_filter_conf: dict, extensions: dict):
        self.vt_filter_conf = VTFilterConf(**vt_filter_conf)
        # self.ext_regex = [ExtensionsCategory(category, [re.compile(ext) for ext in ext_re_list])
        #                   for category, ext_re_list in vt_filter_conf.get('ext_regex').imems()]
        self.extensions = [ExtensionsCategory(ext_alias, [re.compile(ext, re.IGNORECASE)
                                                          for ext in ext_regex_list])
                           for ext_alias, ext_regex_list in extensions.items()
                           ]


@dataclass
class Config:
    _api_key: str
    vtapi_v2_link: str
    malware_destination: str
    fp_destination: str
    excluded_provider: str
    buffer_conf: BufferConf
    scanners: List[Scanner]
    filtration_conf: FiltrationConf
    av_trust_conf: AvTrustConf
    data_source: AbstractDataHandler
    vt_batchifier: CustomAsyncBatchifier
    
    # limits to enforce physical backpressure on queues
    max_pending_files: int = 20000
    max_vt_info_lists: int = 500


def set_up_config(conf_file: Path = None) -> Config:
    def read_file(file_path: Path) -> str:
        with open(file_path, 'r') as file:
            return file.read()

    conf_str = ''
    abspath = os.path.abspath(__file__)
    if conf_file is None:
        conf_file = Path(abspath).parent.parent.parent.joinpath('conf.json')  # project root ?
        try:
            conf_str = read_file(conf_file)
        except FileNotFoundError:
            try:
                conf_file = Path(abspath).parent.parent.joinpath('Resources').joinpath(
                    'conf.json')  # project root if project is not packed ?
                conf_str = read_file(conf_file)
            except FileNotFoundError as fnf:
                raise fnf
    else:
        try:
            conf_str = read_file(conf_file)
        except FileNotFoundError as fnf:
            raise fnf

    if conf_str == '': raise FileNotFoundError("there is no conf.json file somehow!")
    conf_str = read_file(conf_file)
    json_d = json.loads(conf_str)

    config = Config(
        _api_key=json_d["api_key"],
        excluded_provider=json_d.get("excluded_provider", json_d.get("key_product", "")),
        vtapi_v2_link=json_d["vtapi_v2_link"],
        data_source=FilesDBOperations(os.getenv('data_source', json_d['data_source'])),  # DATA SOURCE!
        malware_destination=os.getenv('malware_destination', json_d["malware_destination"]),
        fp_destination=os.getenv('malware_destination', json_d["fp_destination"]),
        buffer_conf=BufferConf(**json_d["buffer_conf"]),
        scanners=[Scanner.from_dict(s_name, prop_d) for s_name, prop_d in json_d["scanners"].items()],

        filtration_conf=FiltrationConf(**json_d["filtration_conf"]),
        av_trust_conf=AvTrustConf.from_json(json_d["av_trust_conf"]),
        vt_batchifier=CustomAsyncBatchifier(
            os.getenv('malware_destination', json_d["malware_destination"]),
            json_d["vt_batchifier"]['leading_value'],
            json_d["vt_batchifier"]['leading_count'],
            json_d["vt_batchifier"]['batch_size']
        ),
        max_pending_files=json_d.get("queue_limits", {}).get("max_pending_files", 20000),
        max_vt_info_lists=json_d.get("queue_limits", {}).get("max_vt_info_lists", 500)
    )
    # pprint.pprint(config)
    return config

# if __name__ == '__main__':
#     a = set_up_config()
#     for scanner in a.scanners:
#         pprint.pprint(scanner)
#     print(isinstance(a, Config))
#     # b = a.scanners
#
#     pprint.pprint(a.filtration_conf.extensions)
