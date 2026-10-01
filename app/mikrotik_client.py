import asyncio
import httpx
import paramiko
import urllib3
from fastapi.concurrency import run_in_threadpool

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MikroTikClient:
    def __init__(self, host: str, port: int, username: str, password: str, conn_type: str):
        self.host, self.port, self.username, self.password, self.conn_type = host, port, username, password, conn_type.strip().lower()

    async def _rest_get(self, ep: str) -> dict:
        url = f"https://{self.host}:{self.port}/rest/{ep}"
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            try:
                res = await client.get(url, auth=(self.username, self.password))
                if res.status_code == 401:
                    raise Exception("Authentication failed")
                if res.status_code >= 400:
                    raise Exception(f"HTTP {res.status_code}: {res.text}")
                d = res.json()
                return d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})
            except httpx.RequestError as e:
                raise Exception(f"HTTP failed: {str(e)}")

    async def _ssh_run(self, cmd: str) -> str:
        def ssh_work():
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                c.connect(hostname=self.host, port=self.port, username=self.username, password=self.password, timeout=5.0)
                _, out, err = c.exec_command(cmd, timeout=5.0)
                o, e = out.read().decode('utf-8', errors='ignore'), err.read().decode('utf-8', errors='ignore')
                if e and not o:
                    raise Exception(e.strip())
                return o
            finally:
                c.close()
        try:
            return await run_in_threadpool(ssh_work)
        except Exception as e:
            raise Exception(f"SSH failed: {str(e)}")

    def _parse_ssh(self, output: str) -> dict:
        res = {}
        for line in output.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                res[k.strip()] = v.strip()
        return res

    async def test_connection(self) -> bool:
        await self.get_system_info()
        return True

    async def get_system_info(self) -> dict:
        if self.conn_type == "rest":
            i = await self._rest_get("system/resource")
            return {
                "uptime": i.get("uptime", "Unknown"),
                "version": i.get("version", "Unknown"),
                "cpu_load": str(i.get("cpu-load", i.get("cpu_load", "0"))),
                "free_memory": str(i.get("free-memory", i.get("free_memory", "0"))),
                "total_memory": str(i.get("total-memory", i.get("total_memory", "0"))),
                "board_name": i.get("board-name", i.get("board_name", "Unknown")),
            }
        p = self._parse_ssh(await self._ssh_run("/system resource print without-paging"))
        return {
            "uptime": p.get("uptime", "Unknown"),
            "version": p.get("version", "Unknown"),
            "cpu_load": p.get("cpu-load", "0").replace("%", "").strip(),
            "free_memory": p.get("free-memory", "0"),
            "total_memory": p.get("total-memory", "0"),
            "board_name": p.get("board-name", "Unknown"),
        }

    async def get_updates(self) -> dict:
        if self.conn_type == "rest":
            i = await self._rest_get("system/package/update")
            return {
                "installed_version": i.get("installed-version", "Unknown"),
                "latest_version": i.get("latest-version", "Unknown"),
                "channel": i.get("channel", "Unknown"),
                "status": i.get("status", "Unknown")
            }
        p = self._parse_ssh(await self._ssh_run("/system package update print without-paging"))
        return {
            "installed_version": p.get("installed-version", "Unknown"),
            "latest_version": p.get("latest-version", "Unknown"),
            "channel": p.get("channel", "Unknown"),
            "status": p.get("status", "Unknown")
        }

    async def get_ntp(self) -> dict:
        if self.conn_type == "rest":
            i = await self._rest_get("system/ntp/client")
            syn = "yes" if i.get("synced") or i.get("status") == "synchronized" else "no"
            return {
                "enabled": "yes" if i.get("enabled") in (True, "yes") else "no",
                "active_server": i.get("active-server", "None"),
                "synced": syn,
                "offset": str(i.get("offset", "0"))
            }
        p = self._parse_ssh(await self._ssh_run("/system ntp client print without-paging"))
        syn = "yes" if p.get("synced") == "yes" or p.get("status") == "synchronized" else "no"
        return {
            "enabled": p.get("enabled", "no"),
            "active_server": p.get("active-server", "None"),
            "synced": syn,
            "offset": p.get("offset", "0")
        }
