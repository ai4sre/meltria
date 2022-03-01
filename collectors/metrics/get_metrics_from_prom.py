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
import concurrent.futures
import datetime
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

COMPONENT_LABELS = {
    "front-end", "orders", "orders-db", "carts", "carts-db",
    "shipping", "user", "user-db", "payment", "catalogue", "catalogue-db",
    "queue-master", "rabbitmq", "session-db",
}
APP_LABEL = 'sock-shop'
APP_NODEPOOL = 'default-pool'
STEP = 15
DEFAULT_DURATION = "30m"
NAN = 'nan'
GRAFANA_DASHBOARD = "d/3cHU4RSMk/sock-shop-performance"


def get_targets(url: str, selector: str) -> list[dict[str, Any]]:
    params = {
        "match_target": '{' + selector + '}',
    }
    req = urllib.request.Request('{}{}?{}'.format(
        url, "/api/v1/targets/metadata",
        urllib.parse.urlencode(params)))
    dupcheck = {}
    targets = []
    with urllib.request.urlopen(req) as res:
        body = json.load(res)
        # remove duplicate target
        for item in body["data"]:
            if item["metric"] not in dupcheck:
                targets.append(
                    {"metric": item["metric"], "type": item["type"]})
                dupcheck[item["metric"]] = 1
        return targets


def request_query_range(url: str, params: dict[str, Any], target: dict[str, Any]) -> list[Any]:
    bparams = urllib.parse.urlencode(params).encode('ascii')
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    try:
        # see https://prometheus.io/docs/prometheus/latest/querying/api/#range-queries
        req = urllib.request.Request(url=url + '/api/v1/query_range',
                                     data=bparams, headers=headers)
        with urllib.request.urlopen(req) as res:
            body = json.load(res)
            metrics = body['data']['result']
            if metrics is None or len(metrics) < 1:
                return []
            for metric in metrics:
                metric['metric']['__name__'] = target['metric']
            return metrics
    except urllib.error.HTTPError as err:
        print(urllib.parse.unquote(bparams.decode()), file=sys.stderr)
        print(err.read().decode(), file=sys.stderr)
        raise(err)
    except urllib.error.URLError as err:
        print(err.reason, file=sys.stderr)
        raise(err)
    except Exception as e:
        raise(e)


def get_metrics(url: str, targets: list[dict[str, Any]],
                start: int, end: int, step: int, selector: str) -> list[Any]:
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        for target in targets:
            if target == 'node_cpu_seconds_total':
                selector += ',mode!="idle"'
            query = '{0}{{{1}}}'.format(target['metric'], selector)
            if target['type'] == 'counter':
                query = 'rate({}[1m])'.format(query)
            query = 'sum by (instance,job,node,container,pod,kubernetes_name)({})'.format(
                query)
            params = {
                "query": query,
                "start": start,
                "end": end,
                "step": '{}s'.format(step),
            }
            res = executor.submit(request_query_range, url, params, target)
            futures.append(res)
        executor.shutdown()

    concated_metrics: list[Any] = []
    for future in concurrent.futures.as_completed(futures):
        metrics = future.result()
        if metrics is None:
            continue
        concated_metrics += metrics
    return concated_metrics


def get_metrics_by_query_range(url: str, start: int, end: int, step: int,
                               query: str, target: dict[str, Any]) -> list[Any]:
    params = {
        "query": query,
        "start": start,
        "end": end,
        "step": '{}s'.format(step),
    }
    return request_query_range(url, params, target)


def interpotate_time_series(values: list[list[int]], time_meta: dict[str, Any]
                            ) -> list[list[float]]:
    start, end, step = time_meta['start'], time_meta['end'], time_meta['step']
    new_values = []

    # start check
    if (lost_num := int((values[0][0] - start) / step) - 1) > 0:
        for j in range(lost_num):
            new_values.append([start + step * j, NAN])

    for i, val in enumerate(values):
        if i + 1 >= len(values):
            new_values.append(val)
            break
        cur_ts, next_ts = val[0], values[i + 1][0]
        new_values.append(val)
        if (lost_num := int((next_ts - cur_ts) / step) - 1) > 0:
            for j in range(lost_num):
                new_values.append([cur_ts + step * (j + 1), NAN])

    # end check
    last_ts = values[-1][0]
    if (lost_num := int((end - last_ts) / step)) > 0:
        for j in range(lost_num):
            new_values.append([last_ts + step * (j + 1), NAN])

    return new_values


def support_set_default(obj: set):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(repr(obj) + " is not JSON serializable")


def metrics_as_result(container_metrics: list[Any], pod_metrics: list[Any], node_metrics: list[Any],
                      throughput_metrics: list[Any], latency_metrics: list[Any], error_metrics: list[Any],
                      time_meta: dict[str, Any], injected_meta: dict[str, Any]) -> dict[str, Any]:
    start, end = time_meta['start'], time_meta['end']
    grafana_url = time_meta['grafana_url']
    dashboard_url = f"{grafana_url}/{GRAFANA_DASHBOARD}?orgId=1&from={start}000&to={end}000"

    data: dict[str, Any] = {
        'meta': {
            'prometheus_url': time_meta['prometheus_url'],
            'grafana_url': grafana_url,
            'grafana_dashboard_url': dashboard_url,
            'start': start,
            'end': end,
            'step': time_meta['step'],
            'count': {
                'sum': 0,
                'containers': 0,
                'middlewares': 0,
                'services': 0,
                'nodes': 0,
            },
        },
        'mappings': {'nodes-containers': {}},
        'containers': {}, 'middlewares': {}, 'nodes': {}, 'services': {},
    }
    data['meta'].update(injected_meta)

    dupcheck: dict[str, Any] = {}
    for metric in container_metrics:
        # some metrics in results of prometheus query has no '__name__'
        labels = metric['metric']
        if '__name__' not in labels:
            continue
        # ex. pod="queue-master-85f5644bf5-wrp7q"
        container = labels['pod'].rsplit(
            "-", maxsplit=2)[0] if 'pod' in labels else labels['container']
        data['containers'].setdefault(container, [])
        metric_name = labels['__name__']

        values = interpotate_time_series(metric['values'], time_meta)
        m = {
            'container_name': container,
            'metric_name': metric_name,
            'values': values,
        }

        # 1. {container: 'POD'} => {container: 'xxx' } -> Update 'POD'
        # 2. {container: 'xxx'} => {container: 'POD' } -> Discard 'POD'
        # 3. {container: 'POD'}
        dupcheck.setdefault(container, {})
        dupcheck[container][metric_name] = False
        if labels['container'] == 'POD':
            if not dupcheck[container][metric_name]:
                data['containers'][container].append(m)
        else:
            if not dupcheck[container][metric_name]:
                uniq_metrics = [x for x in data['containers']
                                [container] if x['metric_name'] != metric_name]
                uniq_metrics.append(m)
                data['containers'][container] = uniq_metrics
                dupcheck[container][metric_name] = True

        # Update mappings for nods and containers
        data['mappings']['nodes-containers'].setdefault(
            labels['instance'], set())
        data['mappings']['nodes-containers'][labels['instance']].add(container)

    for metric in pod_metrics:
        if '__name__' not in metric['metric']:
            continue
        # TODO: want to rename 'kubernetes-name' in prometheus config because it is not intuitive.
        container = metric['metric']['kubernetes_name']
        data['middlewares'].setdefault(container, [])
        values = interpotate_time_series(metric['values'], time_meta)
        m = {
            'container_name': container,
            'metric_name': metric['metric']['__name__'],
            'values': values,
        }
        data['middlewares'][container].append(m)

    for metric in node_metrics:
        # some metrics in results of prometheus query has no '__name__'
        if '__name__' not in metric['metric']:
            continue
        node = metric['metric']['node']
        data['nodes'].setdefault(node, [])
        values = interpotate_time_series(metric['values'], time_meta)
        m = {
            'node_name': node,
            'metric_name': metric['metric']['__name__'],
            'values': values,
        }
        data['nodes'][node].append(m)

    for metric in throughput_metrics:
        service = metric['metric']['name']
        data['services'].setdefault(service, [])
        values = interpotate_time_series(metric['values'], time_meta)
        m = {
            'service_name': metric['metric']['name'],
            'metric_name': 'throughput',
            'values': values,
        }
        data['services'][service].append(m)

    for metric in error_metrics:
        service = metric['metric']['name']
        data['services'].setdefault(service, [])
        values = interpotate_time_series(metric['values'], time_meta)
        m = {
            'service_name': metric['metric']['name'],
            'metric_name': 'errors',
            'values': values,
        }
        data['services'][service].append(m)

    for metric in latency_metrics:
        service = metric['metric']['name']
        data['services'].setdefault(service, [])
        values = interpotate_time_series(metric['values'], time_meta)
        m = {
            'service_name': metric['metric']['name'],
            'metric_name': 'latency',
            'values': values,
        }
        data['services'][service].append(m)

    # Count the number of metric series.
    containers_cnt, middlewares_cnt, services_cnt, nodes_cnt = 0, 0, 0, 0
    for metrics in data['containers'].values():
        containers_cnt += len(metrics)
    for metrics in data['middlewares'].values():
        middlewares_cnt += len(metrics)
    for metrics in data['services'].values():
        services_cnt += len(metrics)
    for metrics in data['nodes'].values():
        nodes_cnt += len(metrics)
    data['meta']['count']['containers'] = containers_cnt
    data['meta']['count']['middlewares'] = middlewares_cnt
    data['meta']['count']['services'] = services_cnt
    data['meta']['count']['nodes'] = nodes_cnt
    data['meta']['count']['sum'] = containers_cnt + \
        middlewares_cnt + services_cnt + nodes_cnt

    return data


def get_unix_time(timestamp: Any) -> int:
    if timestamp.isdigit():  # check unix time
        return int(timestamp)
    if timestamp is None or not timestamp:
        return 0
    dt = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
    return int(dt.timestamp())


def time_range_from_args(params: dict[str, Any]) -> tuple[int, int]:
    """
    get unix timestamps range (start to end) from duration
    """

    duration = datetime.timedelta(seconds=0)
    dt = params["duration"]
    if dt.endswith("s") or dt.endswith("sec"):
        duration = datetime.timedelta(seconds=int(dt[:-1]))
    elif dt.endswith("m") or dt.endswith("min"):
        duration = datetime.timedelta(minutes=int(dt[:-1]))
    elif dt.endswith("h") or dt.endswith("hours"):
        duration = datetime.timedelta(hours=int(dt[:-1]))
    else:
        raise ValueError("args.duration is invalid format")

    duration = int(duration.total_seconds())
    now = int(datetime.datetime.now().timestamp())
    start, end = now - duration, now
    if params["end"] is None and params["start"] is None:
        pass
    elif params["end"] is not None and params["start"] is None:
        end = get_unix_time(params["end"])
        start = end - duration
    elif params["end"] is None and params["start"] is not None:
        start = get_unix_time(params["start"])
        end = start + duration
    elif params["end"] is not None and params["start"] is not None:
        start = get_unix_time(params["start"])
        end = get_unix_time(params["end"])
    else:
        raise ValueError("not reachable")

    start = start - start % params["step"]
    end = end - end % params["step"]
    return start, end


def collect_metrics(prometheus_url: str, grafana_url: str, start_time: str, end_time: str, chaos_param: dict[str, str],
                    duration: str = DEFAULT_DURATION, step: int = STEP) -> dict[str, Any]:
    """
    Collect metrics API
    """

    start, end = time_range_from_args({
        "duration": duration,
        "start": start_time,
        "end": end_time,
        "step": step,
    })
    if start > end:
        raise ValueError("start must be lower than end.")

    # get container metrics (cAdvisor)
    container_targets = get_targets(prometheus_url,
                                    'job=~"kubernetes-cadvisor"')
    # add container=POD for network metrics
    # exclude metrics of argo workflow pods by removing metrics that 'instance' is gke control-pool node.
    comp_list = '|'.join(COMPONENT_LABELS)
    container_selector = f"namespace='sock-shop',container=~'{comp_list}|POD',nodepool='{APP_NODEPOOL}'"
    container_metrics = get_metrics(prometheus_url, container_targets,
                                    start, end, step, container_selector)

    # get pod metrics
    pod_selector = 'app="{}"'.format(APP_LABEL)
    pod_targets = get_targets(prometheus_url, pod_selector)
    pod_metrics = get_metrics(prometheus_url, pod_targets,
                              start, end, step, pod_selector)

    # get node metrics (node-exporter)
    node_selector = f"job='monitoring/node-exporter',node=~'.+-{APP_NODEPOOL}-.+'"
    node_targets = get_targets(prometheus_url, node_selector)
    node_metrics = get_metrics(prometheus_url, node_targets,
                               start, end, step, node_selector)

    # get service metrics
    throughput_metrics = get_metrics_by_query_range(
        prometheus_url, start, end, step, """
            sum by (name) (
                rate(
                    request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop"
                    }[1m]
                )
                +
                rate(
                    http_request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop"
                    }[1m]
                )
            )
            """,
        {'metric': 'request_duration_seconds_count', 'type': 'gauge'},
    )

    error_metrics: list[Any] = get_metrics_by_query_range(
        prometheus_url, start, end, step, """
            sum by (name) (
                rate(
                    request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop",
                        status_code=~"4.+|5.+",
                    }[1m]
                )
                +
                rate(
                    http_request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop",
                        status_code=~"4.+|5.+",
                    }[1m]
                )
            )
            """,
        {'metric': 'request_duration_seconds_count', 'type': 'gauge'},
    )

    latency_metrics = get_metrics_by_query_range(
        prometheus_url, start, end, step, """
            sum by (name) (
                rate(
                    request_duration_seconds_sum{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop"
                    }[1m]
                )
            ) / sum by (name) (
                rate(
                    request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop"
                    }[1m]
                )
            )
            """,
        {'metric': 'request_duration_seconds_sum', 'type': 'gauge'},
    )

    # The labels exported by some microservices (such as orders) in sock shop have been changed from
    # request_duration_seconds_sum to http_request_duration_seconds_sum.
    latency_metrics_patch = get_metrics_by_query_range(
        prometheus_url, start, end, step, """
            sum by (name) (
                rate(
                    http_request_duration_seconds_sum{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop"
                    }[1m]
                )
            ) / sum by (name) (
                rate(
                    http_request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop"
                    }[1m]
                )
            )
            """,
        {'metric': 'request_duration_seconds_sum', 'type': 'gauge'},
    )
    latency_metrics.extend(latency_metrics_patch)

    result = metrics_as_result(
        container_metrics, pod_metrics,
        node_metrics, throughput_metrics, latency_metrics, error_metrics, {
            'start': start,
            'end': end,
            'step': step,
            'prometheus_url': prometheus_url,
            'grafana_url': grafana_url,
        }, {
            'chaos_injected_component': chaos_param['chaos_injected_component'],
            'injected_chaos_type': chaos_param['injected_chaos_type'],
        }
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prometheus-url",
                        help="endpoint URL for prometheus server",
                        default="http://localhost:9090")
    parser.add_argument("--grafana-url",
                        help="endpoint URL for grafana server",
                        default="http://localhost:3000")
    parser.add_argument(
        "--start", help="start time (UNIX or RFC 3339)", type=str)
    parser.add_argument("--end", help="end time (UNIX or RFC 3339)", type=str)
    parser.add_argument("--step", help="step seconds", type=int, default=STEP)
    parser.add_argument("--duration", help="", type=str, default=DEFAULT_DURATION)
    parser.add_argument("--chaos-injected-component",
                        help="chaos-injected component")
    parser.add_argument("--injected-chaos-type",
                        help="chaos type such as 'pod-cpu-hog'")
    parser.add_argument("--out", help="output path", type=str)
    args = parser.parse_args()

    try:
        result = collect_metrics(
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

    data = json.dumps(result, default=support_set_default)
    if args.out is None:
        print(data)
    else:
        with open(args.out, mode='w') as f:
            f.write(data)


if __name__ == '__main__':
    main()
