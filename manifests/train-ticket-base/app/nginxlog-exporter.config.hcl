listen {
  port = 4040
}

namespace "nginx" {
  source = {
    files = [
      "/etc/nginxlog/access.log"
    ]
  }

  print_log = true

  labels {
    app = "default"
  }

  histogram_buckets = [.005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10]
}
