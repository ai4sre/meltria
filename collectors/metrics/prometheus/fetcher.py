import concurrent.futures
import json
import urllib.error
import urllib.parse
import urllib.request
from logging import getLogger
from typing import Any

import urllib3
import urllib3.exceptions

PROM_API_METADATA: str = "/api/v1/targets/metadata"
PROM_API_FETCH_CONCURRENCY: int = 20
DEFAULT_SUMMARIZE_LABELS: list[str] = [
    'instance', 'job', 'node', 'container', 'pod',
]

logger = getLogger(__name__)


class PromFetcher:
    def __init__(
        self, url: str, ts_range: tuple[int, int], step: int,
        additional_summarize_labels: list[str] = [],
        concurrency: int = PROM_API_FETCH_CONCURRENCY
    ) -> None:
        self.url = url
        self.ts_start, self.ts_end = ts_range
        self.step = step
        self.concurrency = concurrency
        self.http = urllib3.PoolManager(num_pools=concurrency)
        self.summarize_labels = DEFAULT_SUMMARIZE_LABELS + additional_summarize_labels

    def request_targets(self, selector: str) -> list[dict[str, Any]]:
        encoded_params = urllib.parse.urlencode({"match_target": '{' + selector + '}'})
        r = self.http.request(
            'GET', f"{self.url}{PROM_API_METADATA}?{encoded_params}",
        )

        body = json.loads(r.data.decode('utf-8'))
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        # remove duplicate target
        for item in body["data"]:
            if item["metric"] not in seen:
                targets.append({"metric": item["metric"], "type": item["type"]})
                seen.add(item["metric"])
        return targets

    def request_query_range(self, params: dict[str, Any], target: dict[str, Any]) -> list[Any]:
        # see https://prometheus.io/docs/prometheus/latest/querying/api/#range-queries
        r = self.http.request(
            'GET', f"{self.url}/api/v1/query_range",
            fields=params,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        )
        body = json.loads(r.data.decode('utf-8'))
        metrics = body['data']['result']
        if metrics is None or len(metrics) < 1:
            return []
        for metric in metrics:
            metric['metric']['__name__'] = target['metric']
        return metrics

    def get_metrics(
        self, targets: list[dict[str, Any]], selector: str,
    ) -> list[Any]:
        """ get metrics by multiple targets.
        """
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            for target in targets:
                if target == 'node_cpu_seconds_total':
                    selector += ',mode!="idle"'
                query = '{0}{{{1}}}'.format(target['metric'], selector)
                if target['type'] == 'counter':
                    query = 'rate({}[1m])'.format(query)
                query = f"sum by ({','.join(self.summarize_labels)})({query})"
                params = {
                    "query": query,
                    "start": self.ts_start,
                    "end": self.ts_end,
                    "step": '{}s'.format(self.step),
                }
                res = executor.submit(self.request_query_range, params, target)
                futures.append(res)
            executor.shutdown()

        concated_metrics: list[Any] = []
        for future in concurrent.futures.as_completed(futures):
            metrics = future.result()
            if metrics is None:
                continue
            concated_metrics += metrics
        return concated_metrics

    def get_metrics_by_query_range(
        self, query: str, target: dict[str, Any],
    ) -> list[Any]:
        """ get metrics by query range.
        """
        params = {
            "query": query,
            "start": self.ts_start,
            "end": self.ts_end,
            "step": '{}s'.format(self.step),
        }
        return self.request_query_range(params, target)
