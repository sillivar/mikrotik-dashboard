import asyncio
import httpx
import urllib3
from fastapi.concurrency import run_in_threadpool

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MikroTikClient:
    def __init__(self, host: str, port: int, username: str, password: str, conn_type: str = "rest", snmp_community: str = "public", snmp_port: int = 161):
        self.host, self.port, self.username, self.password, self.conn_type = host, port, username, password, conn_type.strip().lower()
        self.snmp_community, self.snmp_port = snmp_community, snmp_port

    async def _req(self, m: str, ep: str) -> dict:
        url = f"https://{self.host}:{self.port}/rest/{ep}"
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            try:
                res = await client.request(m, url, auth=(self.username, self.password))
                if res.status_code == 401: raise Exception("Authentication failed")
                if res.status_code == 204 or not res.text: return {}
                if res.status_code >= 400: raise Exception(f"HTTP {res.status_code}: {res.text}")
                d = res.json()
                return d[0] if isinstance(d, list) and d else (d if isinstance(d, dict) else {})
            except httpx.RequestError as e: raise Exception(f"HTTP failed: {str(e)}")

    async def test_connection(self) -> bool: return await self.get_system_info() is not None

    async def get_system_info(self) -> dict:
        i = await self._req("GET", "system/resource")
        return {
            "uptime": i.get("uptime", "Unknown"), "version": i.get("version", "Unknown"),
            "cpu_load": str(i.get("cpu-load", i.get("cpu_load", "0"))),
            "free_memory": str(i.get("free-memory", i.get("free_memory", "0"))),
            "total_memory": str(i.get("total-memory", i.get("total_memory", "0"))),
            "board_name": i.get("board-name", i.get("board_name", "Unknown")),
        }

    async def get_updates(self) -> dict:
        try: await self._req("POST", "system/package/update/check-for-updates")
        except Exception: pass
        i = await self._req("GET", "system/package/update")
        return {
            "installed_version": i.get("installed-version", "Unknown"),
            "latest_version": i.get("latest-version", "Unknown"),
            "channel": i.get("channel", "Unknown"), "status": i.get("status", "Unknown")
        }

    async def get_ntp(self) -> dict:
        i = await self._req("GET", "system/ntp/client")
        syn = "yes" if i.get("synced") or i.get("status") == "synchronized" else "no"
        return {
            "enabled": "yes" if i.get("enabled") in (True, "yes") else "no",
            "active_server": i.get("active-server", "None"), "synced": syn, "offset": str(i.get("offset", "0"))
        }

    async def get_snmp_stats(self) -> dict:
        def snmp_work():
            from pysnmp.hlapi import SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, getCmd, nextCmd
            def s_get(oids):
                it = getCmd(SnmpEngine(), CommunityData(self.snmp_community, mpModel=1), UdpTransportTarget((self.host, self.snmp_port), timeout=2.0, retries=1), ContextData(), *[ObjectType(ObjectIdentity(oid)) for oid in oids])
                err_ind, err_stat, err_idx, var_binds = next(it)
                if err_ind: raise Exception(str(err_ind))
                if err_stat: raise Exception(f"{err_stat} at {err_idx}")
                return {str(vb[0]): vb[1] for vb in var_binds}
            def s_walk(oid_base):
                it = nextCmd(SnmpEngine(), CommunityData(self.snmp_community, mpModel=1), UdpTransportTarget((self.host, self.snmp_port), timeout=2.0, retries=1), ContextData(), ObjectType(ObjectIdentity(oid_base)), lexicographicMode=False)
                res = []
                for err_ind, err_stat, err_idx, var_binds in it:
                    if err_ind or err_stat: break
                    for vb in var_binds: res.append((str(vb[0]), vb[1]))
                return res
            b_ram = "1.3.6.1.2.1.25.2.3.1."
            sys_stats = s_get(["1.3.6.1.2.1.1.3.0", "1.3.6.1.4.1.14988.1.1.3.10.0", b_ram + "4.65536", b_ram + "5.65536", b_ram + "6.65536"])
            tot_sec = int(sys_stats.get("1.3.6.1.2.1.1.3.0", 0)) // 100
            uptime_str = f"{tot_sec // 86400}d {(tot_sec % 86400) // 3600:02d}:{(tot_sec % 3600) // 60:02d}:{tot_sec % 60:02d}"
            cpu = int(sys_stats.get("1.3.6.1.4.1.14988.1.1.3.10.0", 0))
            block_size = int(sys_stats.get(b_ram + "4.65536", 1))
            tot_units = int(sys_stats.get(b_ram + "5.65536", 0))
            used_units = int(sys_stats.get(b_ram + "6.65536", 0))
            total_mem, free_mem = tot_units * block_size, (tot_units - used_units) * block_size
            b_if = "1.3.6.1.2.1.2.2.1."
            descr, in_o, out_o = s_walk(b_if + "2"), s_walk(b_if + "10"), s_walk(b_if + "16")
            interfaces = {}
            for oid, val in descr:
                idx = oid.split(".")[-1]
                interfaces[idx] = {"name": str(val), "in_bytes": 0, "out_bytes": 0}
            for oid, val in in_o:
                idx = oid.split(".")[-1]
                if idx in interfaces: interfaces[idx]["in_bytes"] = int(val) if val else 0
            for oid, val in out_o:
                idx = oid.split(".")[-1]
                if idx in interfaces: interfaces[idx]["out_bytes"] = int(val) if val else 0
            return {
                "uptime": uptime_str, "cpu_load": cpu, "free_memory": free_mem, "total_memory": total_mem, "interfaces": list(interfaces.values())
            }
        try: return await run_in_threadpool(snmp_work)
        except Exception as e: raise Exception(f"SNMP stats query failed: {str(e)}")

