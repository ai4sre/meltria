import concurrent.futures
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PROM_API_METADATA: str = "/api/v1/targets/metadata"
PROM_API_FETCH_CONCURRENCY: int = 20


class PromFetcher:
    def __init__(
        self, url: str, ts_range: tuple[int, int], step: int,
        concurrency: int = PROM_API_FETCH_CONCURRENCY
    ) -> None:
        self.url = url
        self.ts_start, self.ts_end = ts_range
        self.step = step
        self.concurrency = concurrency

    def request_targets(self, selector: str) -> list[dict[str, Any]]:
        params = {"match_target": '{' + selector + '}'}
        req = urllib.request.Request('{}{}?{}'.format(
            self.url, PROM_API_METADATA,
            urllib.parse.urlencode(params)))
        dupcheck = {}
        targets: list[dict[str, Any]] = []
        with urllib.request.urlopen(req) as res:
            body = json.load(res)
            # remove duplicate target
            for item in body["data"]:
                if item["metric"] not in dupcheck:
                    targets.append(
                        {"metric": item["metric"], "type": item["type"]})
                    dupcheck[item["metric"]] = 1
        return targets

    def request_query_range(self, params: dict[str, Any], target: dict[str, Any]) -> list[Any]:
        bparams = urllib.parse.urlencode(params).encode('ascii')
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        try:
            # see https://prometheus.io/docs/prometheus/latest/querying/api/#range-queries
            req = urllib.request.Request(url=self.url + '/api/v1/query_range', data=bparams, headers=headers)
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
                query = 'sum by (instance,job,node,container,pod,kubernetes_name)({})'.format(
                    query)
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
