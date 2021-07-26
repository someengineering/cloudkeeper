import cloudkeeper.logging
from collections import defaultdict
from paramiko import SSHClient
from .resources import OnpremInstance

log = cloudkeeper.logging.getLogger("cloudkeeper." + __name__)


def instance_from_ssh(
    hostname: str,
    port: int = 22,
    username: str = None,
    password: str = None,
    pkey: str = None,
    key_filename: str = None,
    auth_timeout: float = 10,
    timeout: float = 10,
    allow_agent: bool = True,
    look_for_keys: bool = True,
    passphrase: str = None,
):
    if "@" in hostname:
        username, hostname = hostname.split("@", 1)
    if ":" in hostname:
        hostname, port = hostname.split(":", 1)

    client = SSHClient()
    client.load_system_host_keys()
    client.connect(
        hostname,
        port=port,
        username=username,
        password=password,
        pkey=pkey,
        passphrase=passphrase,
        key_filename=key_filename,
        timeout=timeout,
        auth_timeout=auth_timeout,
        allow_agent=allow_agent,
        look_for_keys=look_for_keys,
    )
    meminfo = get_proc_meminfo(client)
    cpuinfo = get_proc_cpuinfo(client)
    netdev, ip4, ip6 = get_ipv4_info(client)
    client.close()
    s = OnpremInstance(hostname, {})
    s.instance_cores = len(cpuinfo)
    s.instance_memory = round(meminfo.get("MemTotal", 0) / 1024 ** 2)
    s.instance_status = "running"
    if netdev:
        s.network_device = netdev
    if ip4:
        s.network_ip4 = ip4
    if ip6:
        s.network_ip6 = ip6
    if s.instance_cores > 0:
        s.instance_type = cpuinfo.get("0", {}).get("model name")
    return s


def get_proc_meminfo(client: SSHClient):
    cmd = "cat /proc/meminfo"
    out, err = client_exec(client, cmd)
    if err:
        raise RuntimeError(f"Error while executing {cmd}: {err}")
    meminfo = {
        i[0].rstrip(":"): int(i[1]) for i in [l.split() for l in str(out).splitlines()]
    }
    return meminfo


def get_proc_cpuinfo(client: SSHClient):
    cmd = "cat /proc/cpuinfo"
    out, err = client_exec(client, cmd)
    if err:
        raise RuntimeError(f"Error while executing {cmd}: {err}")
    cpuinfo = defaultdict(dict)
    num_core = "0"
    for l in str(out).splitlines():
        if len(l) == 0:
            continue
        k, v = l.split(":", 1)
        k = k.strip()
        v = v.strip()
        if k == "processor":
            num_core = v
        else:
            cpuinfo[num_core][k] = v
    return dict(cpuinfo)


def get_ipv4_info(client: SSHClient):
    dst4 = "8.8.8.8"
    dst6 = "2001:4860:4860::8888"
    ip4 = None
    ip6 = None
    dev = None
    for dst in [dst4, dst6]:
        cmd = f"ip r g {dst}"
        out, err = client_exec(client, cmd)
        if err:
            log.error(f"Error while executing {cmd}: {err}")
            continue
        src = None
        for l in str(out).splitlines():
            l = l.strip()
            if l.startswith(dst) and "dev" in l and "src" in l:
                l = l.split()
                dev = l[l.index("dev") + 1]
                src = l[l.index("src") + 1]
                break
        if dev is None or src is None:
            raise RuntimeError("Unable to determine IPv4 interface")
        cmd = f"ip a s dev {dev}"
        out, err = client_exec(client, cmd)
        if err:
            raise RuntimeError(f"Error while executing {cmd}: {err}")
        ip = None
        for l in str(out).splitlines():
            l = l.strip()
            if l.startswith("inet") and src in l:
                l = l.split()
                ip = l[1]
                break
        if ip is None:
            raise RuntimeError("Unable to determine IP address")
        if "." in ip:
            ip4 = ip
        elif ":" in ip:
            ip6 = ip
        else:
            raise RuntimeError(f"Unable to parse IP {ip}")
    return (dev, ip4, ip6)


def client_exec(client: SSHClient, command: str, timeout: float = None):
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return (out, err)
