listen {
  port = 4040
}

namespace "nginx" {
  format = "$remote_addr - $remote_user [$time_local] \"$request\" $request_length $status $body_bytes_sent $request_time \"$http_referer\" \"$http_user_agent\" \"$http_x_forwarded_for\" $upstream_response_time"

  source = {
    files = [
      "/etc/nginxlog/access.log"
    ]
  }

  print_log = true

  histogram_buckets = [.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
}
