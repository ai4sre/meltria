#!/usr/bin/env python3

""" An example of JSON layout
    {
      'containers': {
        '<container name>': [
          { 'container_name': '<container name>', 'metric_name': 'xx', 'values': [<timestamp>, '<value>'] },
             ...
        ]
        ...
      ]
      'middlewares': {
        '<container name>': [
          [ {'container_name': '<container name>'}, 'metric_name': 'xx', 'values': [<timestamp>, '<value>']],
        ],
      },
      'services': {
        '<service name>': [
          { 'service_name': '<container name>', 'metric_name': 'xx', 'values': [<timestamp>, '<value>'] } },
          ...
        ]
        ...
      },
      'nodes': {
        '<node name>': [
          [ {'node_name': 'xxx'}, 'metric_name': 'xx', 'values': [<timestamp>, <value>]],
        ],
      },
      'mappings': {
         'nodes-containers': {
           '<node name>': [ '<container name>', ... ]
         }
      }
    }
"""

import argparse
import json
import sys
from typing import Any

from targets import sockshop, trainticket

STEP = 15
DEFAULT_DURATION = "30m"


def support_set_default(obj: set):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(repr(obj) + " is not JSON serializable")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target",
                        choices=[sockshop.TARGET_APP_NAME, trainticket.TARGET_APP_NAME],
                        help="target application to collect metrics",
                        default=sockshop.TARGET_APP_NAME)
    parser.add_argument("--prometheus-url",
                        help="endpoint URL for prometheus server",
                        default="http://localhost:9090")
    parser.add_argument("--grafana-url",
                        help="endpoint URL for grafana server",
                        default="http://localhost:3000")
    parser.add_argument("--start", help="start time (UNIX or RFC 3339)", type=str)
    parser.add_argument("--end", help="end time (UNIX or RFC 3339)", type=str)
    parser.add_argument("--step", help="step seconds", type=int, default=STEP)
    parser.add_argument("--duration", help="", type=str, default=DEFAULT_DURATION)
    parser.add_argument("--chaos-injected-component", help="chaos-injected component")
    parser.add_argument("--injected-chaos-type", help="chaos type such as 'pod-cpu-hog'")
    parser.add_argument("--out", help="output path", type=str)
    args = parser.parse_args()

    match args.target:
        case sockshop.TARGET_APP_NAME:
            try:
                result: dict[str, Any] = sockshop.collect_metrics(
                    prometheus_url=args.prometheus_url,
                    grafana_url=args.grafana_url,
                    start_time=args.start,
                    end_time=args.end,
                    chaos_param={
                        'chaos_injected_component': args.chaos_injected_component,
                        'injected_chaos_type': args.injected_chaos_type,
                    },
                    duration=args.duration,
                    step=args.step,
                )
            except ValueError as e:
                print("parsing timestamp error:", e, file=sys.stderr)
                parser.print_help()
                exit(-1)
        case trainticket.TARGET_APP_NAME:
            result = trainticket.collect_metrics(
                prometheus_url=args.prometheus_url,
                grafana_url=args.grafana_url,
                start_time=args.start,
                end_time=args.end,
                chaos_param={
                    'chaos_injected_component': args.chaos_injected_component,
                    'injected_chaos_type': args.injected_chaos_type,
                },
                duration=args.duration,
                step=args.step,
            )
        case _:
            raise ValueError("Unknown target: {}".format(args.target))

    data = json.dumps(result, default=support_set_default)
    if args.out is None:
        print(data)
    else:
        with open(args.out, mode='w') as f:
            f.write(data)


if __name__ == '__main__':
    main()
