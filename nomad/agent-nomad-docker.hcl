job "noia-agent" {

  type = "system"
  datacenters = ["dc1"]  
  constraint {
     attribute = "${attr.kernel.name}"
     value     = "linux"
   }

  group "agent" {
    count = 1
    restart {
      attempts = 20
      interval = "30m"
      delay = "15s"
      mode = "fail"
    }

    task "noia-agent" {
      driver = "docker"
      resources {
        memory = 900
        cpu    = 2000
      }
    config {
      image = "noia/agent:latest"
      force_pull = true
      network_mode = "host"
      volumes = [
       "/var/run/docker.sock:/var/run/docker.sock:ro"
        ]
      devices = [
    {
      host_path = "/dev/net/tun"
      container_path = "/dev/net/tun"
    }
        ]
      cap_add = [
        "SYS_MODULE",
    "NET_ADMIN"
        ]

      }
    env {
        NOIA_API_KEY='xxxxxxxIE0VZAaX0coxxxxxxxxx'
        NOIA_CONTROLLER_URL='app-controller-platform-agents.noia.network'

    }

    }
  }
}
