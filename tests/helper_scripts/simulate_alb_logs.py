from datetime import datetime, timedelta
import random
import gzip

path = 'tests/test_data/s3/elasticloadbalancing.amazonaws.com/'
entry = 'http {timestamp} app/k8s-fakealb-fakealbi-ffbc3dc280/82a34fae168ba1aa {clientip}:{client_port} {elbip}:9898 0.000 0.001 0.000 200 200 137 2886 "GET http://k8s-podinfo-podinfoi-ffbc3dc280-1325129400.us-east-1.elb.amazonaws.com:80/{path} HTTP/1.1" "curl/7.79.1" - - arn:aws:elasticloadbalancing:us-east-1:012345678910:targetgroup/k8s-fakealb-frontend-b634dbe3b4/c0bcccc5dfc7c29c "Root=1-634ea0af-3a9eec810c49366e7ba37d49" "-" "-" 1 {timestamp} "forward" "-" "-" "{backend_ip}:9898" "200" "-" "-"'

client_ips = [
    "79.156.252.12",
    "79.156.252.13",
    "79.156.12.56",
    "79.16.252.77",
    "80.1.124.12",
    "80.46.88.124",
    "156.156.52.176",
    "3.222.2.67",
    "3.23.57.13"
]

elb_ips = [
    "192.168.1.222",
    "192.168.4.56",
    "192.168.8.23"
]

backend_ips = [
    "192.168.3.12",
    "192.168.7.64",
    "192.168.9.78",
]

paths = [
    "",
    "env",
    "index.html",
    "fake/my-site.php",
    "about-us",
    "contact",
    "favicon.ico"
]

timestamp = datetime.utcnow()
dif = 1

for node_ip in elb_ips:
    with gzip.open(path + node_ip + '.gz', 'wb') as f:
        for i in range(1,100000):
            timestamp += timedelta(milliseconds=random.randrange(1,5))
            d = {
                "timestamp" : timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ') ,
                "clientip": random.choice(client_ips),
                "elbip": random.choice(elb_ips),
                "backend_ip": random.choice(backend_ips),
                "client_port": random.randrange(1024,65535),
                "path": random.choice(paths)
            }
            f.write((entry.format(**d) + "\n").encode())