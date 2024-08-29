import json
import timeit
from typing import List

from Entities.Vt_inf import VTReportInfo
from configs import Configs
from vt_download_logic.Filtration import CustomFilter


def test_vtfileinfo_from_json():
    from pathlib import Path
    distribution_path = Path(__file__).parent / "distribution.json"
    with open(distribution_path, 'r') as file:
        json_data = file.read()

    json_object = json.loads(json_data)

    vt_local_reports = []
    for data in json_object:
        vt_local_reports.append(VTReportInfo.from_dict(data))
    # pprint.pprint(vt_local_reports[0])
    return vt_local_reports


def filtration_time_test():
    print(f"all -> {len(vt_inf_objs)}")

    time_detection_by_filter = timeit.timeit(
        stmt="vt_inf_objs = custom_filter.detection_by_filter(vt_inf_objs, 'zillya')",
        setup="from __main__ import custom_filter, vt_inf_objs",
        number=2
    )
    print(f"Time taken by detection_by_filter: {time_detection_by_filter:.5f} seconds"
          f"vt info left {len(vt_inf_objs)}"
          )

    time_dumb_score_filter = timeit.timeit(
        stmt="vt_inf_objs = custom_filter.dumb_score_filter(vt_inf_objs)",
        setup="from __main__ import custom_filter, vt_inf_objs",
        number=2
    )
    print(f"Time taken by dumb_score_filter: {time_dumb_score_filter:.5f} seconds"
          f"vt info left {len(vt_inf_objs)}"
          )
#generator(""'C:\\\\Users\\\\T-k\\\\PycharmProjects\\\\VtParser\\\\Resources\\\\sha1_base.txt')
    time_filter_by_sha1 = timeit.timeit(
        stmt="vt_inf_objs = custom_filter.filter_by_sha1(vt_inf_objs)",
        setup="from __main__ import custom_filter, vt_inf_objs",
        number=2,
    )
    print(f"Time taken by filter_by_sha1: {time_filter_by_sha1:.5f} seconds"
          f"vt info left {len(vt_inf_objs)}")

    time_filter_by_extensions = timeit.timeit(
        stmt="vt_inf_objs = custom_filter.filter_by_extensions(vt_inf_objs)",
        setup="from __main__ import custom_filter, vt_inf_objs",
        number=2
    )
    print(f"Time taken by filter_by_extensions: {time_filter_by_extensions:.5f} seconds"
          f"vt info left {len(vt_inf_objs)}")


def filter_end_parse(vtInfoList: List[VTReportInfo]):
    vt_inf_objs = custom_filter.filter_by_extensions(vtInfoList)
    print(f"after  filter_by_extensions ->{len(vt_inf_objs)}")
    vt_inf_objs = custom_filter.detection_by_filter(vt_inf_objs, 'zillya')
    print(f"after  detection_by_filter ->{len(vt_inf_objs)}")
    vt_inf_objs = custom_filter.dumb_score_filter(vtInfoList)
    print(f"after  dumb_score_filter ->{len(vt_inf_objs)}")
    vt_inf_objs = custom_filter.filter_by_sha1(
        vt_inf_objs)
    print(f"after  filter_by_sha1 ->{len(vt_inf_objs)}")


if __name__ == "__main__":

    conf = Configs.set_up_config()

    custom_filter = CustomFilter(conf.filtration_conf, conf.av_trust_conf, conf.data_source)

    vt_inf_objs = test_vtfileinfo_from_json()
    filter_end_parse(vt_inf_objs)
