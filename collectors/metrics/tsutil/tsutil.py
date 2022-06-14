import datetime
from typing import Any

NAN = 'nan'


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


def interpotate_time_series(
    values: list[list[int]], time_meta: dict[str, Any],
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
