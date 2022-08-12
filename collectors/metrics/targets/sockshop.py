from multiprocessing import cpu_count
from typing import Any

from prometheus.fetcher import PromFetcher
from tsutil import tsutil

TARGET_APP_NAME = 'sock-shop'
COMPONENT_LABELS = {
    "front-end", "orders", "orders-db", "carts", "carts-db",
    "shipping", "user", "user-db", "payment", "catalogue", "catalogue-db",
    "queue-master", "rabbitmq", "session-db",
}
APP_LABEL = 'sock-shop'
APP_NODEPOOL = 'default-pool'
GRAFANA_DASHBOARD = "d/3cHU4RSMk/sock-shop-performance"


def metrics_as_result(
    container_metrics: list[Any], pod_metrics: list[Any], node_metrics: list[Any],
    throughput_metrics: list[Any], latency_metrics: list[Any], error_metrics: list[Any],
    time_meta: dict[str, Any], injected_meta: dict[str, Any],
) -> dict[str, Any]:
    start, end = time_meta['start'], time_meta['end']
    grafana_url = time_meta['grafana_url']
    dashboard_url = f"{grafana_url}/{GRAFANA_DASHBOARD}?orgId=1&from={start}000&to={end}000"

    data: dict[str, Any] = {
        'meta': {
            'target_app': TARGET_APP_NAME,
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

        values = tsutil.interpotate_time_series(metric['values'], time_meta)
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
        values = tsutil.interpotate_time_series(metric['values'], time_meta)
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
        values = tsutil.interpotate_time_series(metric['values'], time_meta)
        m = {
            'node_name': node,
            'metric_name': metric['metric']['__name__'],
            'values': values,
        }
        data['nodes'][node].append(m)

    for metric in throughput_metrics:
        service = metric['metric']['name']
        data['services'].setdefault(service, [])
        values = tsutil.interpotate_time_series(metric['values'], time_meta)
        m = {
            'service_name': metric['metric']['name'],
            'metric_name': 'throughput',
            'values': values,
        }
        data['services'][service].append(m)

    for metric in error_metrics:
        service = metric['metric']['name']
        data['services'].setdefault(service, [])
        values = tsutil.interpotate_time_series(metric['values'], time_meta)
        m = {
            'service_name': metric['metric']['name'],
            'metric_name': 'errors',
            'values': values,
        }
        data['services'][service].append(m)

    for metric in latency_metrics:
        service = metric['metric']['name']
        data['services'].setdefault(service, [])
        values = tsutil.interpotate_time_series(metric['values'], time_meta)
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


def collect_metrics(
    prometheus_url: str, grafana_url: str,
    start_time: str, end_time: str,
    chaos_param: dict[str, str],
    duration: str, step: int,
) -> dict[str, Any]:
    """
    Collect metrics API
    """

    start, end = tsutil.time_range_from_args({
        "duration": duration,
        "start": start_time,
        "end": end_time,
        "step": step,
    })
    if start > end:
        raise ValueError("start must be lower than end.")

    fetcher = PromFetcher(
        url=prometheus_url, ts_range=(start, end), step=step, concurrency=cpu_count()*10,
        additional_summarize_labels=['kubernetes_name'],
    )

    # get container metrics (cAdvisor)
    container_targets = fetcher.request_targets('job=~"kubernetes-cadvisor"')
    # add container=POD for network metrics
    # exclude metrics of argo workflow pods by removing metrics that 'instance' is gke control-pool node.
    comp_list = '|'.join(COMPONENT_LABELS)
    container_selector = f"namespace='sock-shop',container=~'{comp_list}|POD',nodepool='{APP_NODEPOOL}'"
    container_metrics = fetcher.get_metrics(container_targets, container_selector)

    # get pod metrics
    pod_selector = 'app="{}"'.format(APP_LABEL)
    pod_targets = fetcher.request_targets(pod_selector)
    pod_metrics = fetcher.get_metrics(pod_targets, pod_selector)

    # get node metrics (node-exporter)
    node_selector = f"job='monitoring/node-exporter',node=~'.+-{APP_NODEPOOL}-.+'"
    node_targets = fetcher.request_targets(node_selector)
    node_metrics = fetcher.get_metrics(node_targets, node_selector)

    # get service metrics
    throughput_metrics = fetcher.get_metrics_by_query_range(
        """
            sum by (name) (
                rate(
                    request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop",
                        status_code=~"2.."
                    }[1m]
                )
            ) or sum by (name) (
                rate(
                    http_request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop",
                        status_code=~"2.."
                    }[1m]
                )
            )
        """,
        {'metric': 'request_duration_seconds_count', 'type': 'gauge'},
    )

    error_metrics: list[Any] = fetcher.get_metrics_by_query_range(
        """
            sum by (name) (
                rate(
                    request_duration_seconds_count{
                        job="kubernetes-service-endpoints",
                        kubernetes_namespace="sock-shop",
                        status_code=~"4.+|5.+",
                    }[1m]
                )
            ) or sum by (name) (
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

    latency_metrics = fetcher.get_metrics_by_query_range(
        """
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
    latency_metrics_patch = fetcher.get_metrics_by_query_range(
        """
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
