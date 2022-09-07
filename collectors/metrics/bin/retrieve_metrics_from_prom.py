#!/usr/bin/env python3

import argparse
import json
import logging
import os
from typing import Final

from targets import sockshop, trainticket

DEFAULT_DURATION: Final[str] = "30m"


def support_set_default(obj: set):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(repr(obj) + " is not JSON serializable")


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('metricsfiles',
                        nargs='+',
                        help='metrics output JSON file')
    parser.add_argument("--duration", help="", type=str, default=DEFAULT_DURATION)
    parser.add_argument("--target", help="target application", type=str, default=sockshop.TARGET_APP_NAME)
    parser.add_argument('destdir', help='destionation directory')
    args = parser.parse_args()

    for metrics_file in args.metricsfiles:
        logging.info(f"--> Loading {metrics_file} ...")
        with open(metrics_file) as r:
            obj = json.load(r)
            match args.target:
                case sockshop.TARGET_APP_NAME:
                    result = sockshop.collect_metrics(
                        prometheus_url=obj['meta']['prometheus_url'],
                        grafana_url=obj['meta']['grafana_url'],
                        start_time=str(obj['meta']['start']),
                        end_time=str(obj['meta']['end']),
                        step=obj['meta']['step'],
                        duration=DEFAULT_DURATION,  # FIXME: calculate duration from start and end
                        chaos_param={
                            'chaos_injected_component': obj['meta']['chaos_injected_component'],
                            'injected_chaos_type': obj['meta']['injected_chaos_type'],
                        },
                    )
                case trainticket.TARGET_APP_NAME:
                    result = trainticket.collect_metrics(
                        prometheus_url=obj['meta']['prometheus_url'],
                        grafana_url=obj['meta']['grafana_url'],
                        start_time=str(obj['meta']['start']),
                        end_time=str(obj['meta']['end']),
                        step=obj['meta']['step'],
                        duration=DEFAULT_DURATION,  # FIXME: calculate duration from start and end
                        chaos_param={
                            'chaos_injected_component': obj['meta']['chaos_injected_component'],
                            'injected_chaos_type': obj['meta']['injected_chaos_type'],
                        },
                    )
                case _:
                    raise ValueError("Unknown target: {}".format(args.target))

            dest_file = os.path.join(args.destdir, os.path.basename(metrics_file))
            logging.info(f"--> Dumping {dest_file} ...")
            with open(dest_file, mode='w') as w:
                json.dump(result, fp=w, default=support_set_default)


if __name__ == '__main__':
    main()
