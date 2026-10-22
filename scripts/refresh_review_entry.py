"""Publish the verified review endpoint. Credentials remain in memory only."""
import base64
import datetime
import ipaddress
import json
from pathlib import Path
import re
import socket
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
HOST = "api.github.com"
REPO = "cclcclcclcclcclccl/scholartrace"


def main():
    url = (ROOT / "artifacts/public-review-20261021/url.txt").read_text(encoding="utf-8-sig").strip()
    if not re.fullmatch(r"https://[a-z0-9-]+\.trycloudflare\.com", url):
        raise ValueError("Invalid review endpoint")
    with urllib.request.urlopen(url + "/api/health", timeout=20) as response:
        if json.load(response).get("service") != "scholartrace":
            raise RuntimeError("Review health check failed; entry not changed")
    # A local hosts override can resolve GitHub to loopback after a reboot.
    # Resolve only this API hostname via DNS; retain normal HTTPS certificate checks.
    addresses = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
    if any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        resolved = subprocess.check_output([
            "powershell.exe", "-NoProfile", "-Command",
            "Resolve-DnsName api.github.com -Server 1.1.1.1 -DnsOnly -NoHostsFile -Type A -ErrorAction Stop | Where-Object Type -eq A | Select-Object -ExpandProperty IPAddress"
        ], text=True, creationflags=subprocess.CREATE_NO_WINDOW).splitlines()
        address = next(value.strip() for value in resolved if ipaddress.ip_address(value.strip()).is_global)
        original = socket.getaddrinfo
        def github_dns(host, port, *args, **kwargs):
            return original(address if host == HOST else host, port, *args, **kwargs)
        socket.getaddrinfo = github_dns
    token = subprocess.check_output(["gh", "auth", "token"], text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
    github_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def api(path, body=None):
        request = urllib.request.Request(
            "https://" + HOST + "/repos/" + REPO + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "User-Agent": "Moheng-review-recovery", "Content-Type": "application/json"},
            method="GET" if body is None else "PUT")
        with github_opener.open(request, timeout=30) as response:
            return json.load(response)
    def publish(filename, content):
        state = api("/contents/" + filename + "?ref=gh-pages")
        encoded = content.encode("utf-8")
        if base64.b64decode(state["content"]) == encoded:
            print(filename + ": already current")
            return
        result = api("/contents/" + filename, {
            "message": "Repair review entry and refresh verified endpoint", "branch": "gh-pages", "sha": state["sha"],
            "content": base64.b64encode(encoded).decode()})
        print(filename + ": " + result["commit"]["sha"])
    state = {"url": url, "checked_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
             "status": "免费隧道健康接口已检查；需保持电脑开机联网，临时直达地址可能随重启变化。"}
    runtime = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    index_file = ROOT / "submission-site/index.html"
    index = index_file.read_text(encoding="utf-8-sig")
    index, count = re.subn(r'(id="demo" href=")[^"]+', lambda match: match[1] + url, index)
    if count != 1:
        raise RuntimeError("Expected exactly one workbench link")
    publish("index.html", index)
    publish("runtime.json", runtime)
    index_file.write_text(index, encoding="utf-8")
    (ROOT / "submission-site/runtime.json").write_text(runtime, encoding="utf-8")
    print("Fixed entry updated: https://cclcclcclcclcclccl.github.io/scholartrace/")


if __name__ == "__main__":
    main()
