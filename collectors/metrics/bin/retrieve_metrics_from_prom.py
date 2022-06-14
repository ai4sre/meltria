#!/usr/bin/env python3

import argparse
import json
import logging
import os

from get_metrics_from_prom import collect_metrics, support_set_default


def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s', level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('metricsfiles',
                        nargs='+',
                        help='metrics output JSON file')
    parser.add_argument('destdir', help='destionation directory')
    args = parser.parse_args()

    for metrics_file in args.metricsfiles:
        logging.info(f"--> Loading {metrics_file} ...")
        with open(metrics_file) as r:
            obj = json.load(r)
            result = collect_metrics(
                prometheus_url=obj['meta']['prometheus_url'],
                grafana_url=obj['meta']['grafana_url'],
                start_time=str(obj['meta']['start']),
                end_time=str(obj['meta']['end']),
                step=obj['meta']['step'],
                chaos_param={
                    'chaos_injected_component': obj['meta']['chaos_injected_component'],
                    'injected_chaos_type': obj['meta']['injected_chaos_type'],
                },
            )

            dest_file = os.path.join(args.destdir, os.path.basename(metrics_file))
            logging.info(f"--> Dumping {dest_file} ...")
            with open(dest_file, mode='w') as w:
                json.dump(result, fp=w, default=support_set_default)


if __name__ == '__main__':
    main()
