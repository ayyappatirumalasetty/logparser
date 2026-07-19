import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Today's date (current local date)
today = datetime.now()

# Time progression function
def get_next_timestamp(current_dt):
    r = random.random()
    if r < 0.35:  # 35% chance of milliseconds difference (same second)
        ms = random.randint(1, 500)
        return current_dt + timedelta(milliseconds=ms)
    elif r < 0.70:  # 35% chance of few seconds difference
        sec = random.randint(1, 5)
        ms = random.randint(0, 999)
        return current_dt + timedelta(seconds=sec, milliseconds=ms)
    elif r < 0.85:  # 15% chance of 10-15 seconds difference
        sec = random.randint(10, 15)
        ms = random.randint(0, 999)
        return current_dt + timedelta(seconds=sec, milliseconds=ms)
    elif r < 0.97:  # 12% chance of 1-3 minutes difference
        minutes = random.randint(1, 3)
        sec = random.randint(0, 59)
        return current_dt + timedelta(minutes=minutes, seconds=sec)
    else:  # 3% chance of 5-15 minutes difference
        minutes = random.randint(5, 15)
        return current_dt + timedelta(minutes=minutes)

# Formatter
def format_timestamp(dt, format_type):
    if format_type == 'A':
        return dt.strftime("%Y/%m/%d %H:%M:%S:") + f"{dt.microsecond // 1000:03d}"
    elif format_type in ('B', 'C'):
        return dt.strftime("%Y-%m-%dT%H:%M:%S,") + f"{dt.microsecond // 1000:03d}"
    elif format_type == 'D':
        return dt.strftime("%Y-%m-%d %H:%M:%S,") + f"{dt.microsecond // 1000:03d}"
    elif format_type == 'E':
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return dt.isoformat()

# Fields
ENDPOINTS = ["/api/v1/auth/login", "/api/v1/backup/create", "/api/v2/restore", "/api/v1/system/status", "/metrics", "/api/v1/users", "/api/v1/reports", "/api/v2/jobs"]
CFG_FILES = ["appsettings.json", "web.config", "database.yml", "server.xml", "logging.properties"]
VOLUMES = ["C:", "D:", "E:"]

# Padding/Context helper
def pad_line_with_context(line, bytes_needed):
    if bytes_needed <= 0:
        return line
    if bytes_needed <= 3:
        return line + " " * bytes_needed
    
    bytes_needed -= 3
    ips = ["192.168.1.50", "10.0.0.12", "172.16.254.1", "192.168.2.115"]
    endpoints = ["/api/v1/auth/login", "/api/v1/backup/create", "/api/v2/restore", "/api/v1/system/status", "/metrics"]
    callers = ["BackupAgent", "WebServiceHelper", "TomcatAccessFilter", "DbConnector", "ConfigManager"]
    
    parts = []
    if random.random() < 0.5:
        parts.append(f"req_id={uuid.uuid4().hex[:12]}")
    if random.random() < 0.5:
        parts.append(f"ip={random.choice(ips)}")
    if random.random() < 0.5:
        parts.append(f"endpoint={random.choice(endpoints)}")
    if random.random() < 0.5:
        parts.append(f"caller={random.choice(callers)}")
    if random.random() < 0.5:
        parts.append(f"cpu_util={random.randint(10, 85)}%")
    if random.random() < 0.5:
        parts.append(f"mem_util={random.randint(30, 90)}%")
        
    meta_str = " ".join(parts)
    if not meta_str:
        meta_str = f"trace_id={uuid.uuid4().hex[:16]}"
        
    if len(meta_str) < bytes_needed:
        extra_len = bytes_needed - len(meta_str) - 8
        if extra_len > 0:
            extra_chars = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(extra_len))
            meta_str += f" extra='{extra_chars}'"
        else:
            meta_str += " " * (bytes_needed - len(meta_str))
    elif len(meta_str) > bytes_needed:
        meta_str = meta_str[:bytes_needed]
        
    return line + " | " + meta_str

def make_base_line(template, line_index):
    placeholders = {
        'thread': f"{random.randint(1000, 20000):05d}",
        'endpoint': random.choice(ENDPOINTS),
        'status': random.choice(["200", "200", "200", "304", "204", "404"]),
        'ms': str(random.randint(10, 250)),
        'cfg_file': random.choice(CFG_FILES),
        'volume': random.choice(VOLUMES),
        'block': str(random.randint(1000, 100000)),
        'cpu_temp': str(random.randint(35, 65)),
        'net_in': str(random.randint(50, 2500)),
        'net_out': str(random.randint(50, 2500)),
        'mem_pct': str(random.randint(30, 85)),
        'disk_c': str(random.randint(60, 92)),
        'db_dur': str(random.randint(2, 60)),
        'db_dur_high': str(random.randint(1800, 4500)),
        'active_conn': str(random.randint(5, 50)),
        'idle_conn': str(random.randint(2, 25)),
    }
    
    try:
        return template.format(**placeholders)
    except Exception as e:
        return template

FILES_CONFIG = {
    "tomcat_access.log": {
        "format": "B",
        "templates_normal": [
            " [http-nio-8080-exec-{thread}] - [INFO] org.apache.catalina.core.ContainerBase.log - Request: GET {endpoint} HTTP/1.1 200",
            " [http-nio-8080-exec-{thread}] - [INFO] org.apache.catalina.core.ContainerBase.log - Request: POST {endpoint} HTTP/1.1 200",
            " [http-nio-8080-exec-{thread}] - [INFO] org.apache.catalina.core.ContainerBase.log - Request: GET {endpoint} HTTP/1.1 304",
            " [http-nio-8080-exec-{thread}] - [INFO] org.apache.catalina.core.ContainerBase.log - Request: GET {endpoint} HTTP/1.1 204",
            " [http-nio-8080-exec-{thread}] - [WARN] org.apache.catalina.core.ContainerBase.log - Request: GET {endpoint} HTTP/1.1 404",
        ],
        "templates_failure": [
            " [http-nio-8080-exec-{thread}] - [WARN] org.apache.catalina.connector.CoyoteAdapter.checkRecycled - Exception while writing access logs or response buffer",
            " [http-nio-8080-exec-{thread}] - [ERROR] org.apache.catalina.core.StandardWrapperValve.invoke - Servlet.service() for servlet [dispatcherServlet] in context with path [] threw exception: java.io.IOException: There is not enough space on the disk",
            " [http-nio-8080-exec-{thread}] - [ERROR] org.apache.catalina.valves.AccessLogValve.log - Failed to write access log entry: java.io.IOException: There is not enough space on the disk"
        ]
    },
    "tomcat.stdout": {
        "format": "C",
        "templates_normal": [
            " (TomcatPool) exec-{thread} [INFO] [][TomcatAccessFilter]doFilter(): Incoming request verified successfully",
            " (TomcatPool) exec-{thread} [INFO] []in method: generateLicensseDetailsData",
            " (TomcatPool) exec-{thread} [INFO] []In the method loadPropertiesFile",
            " (TomcatPool) exec-{thread} [INFO] [][LicenseModuleWrapper]getExpiryTime():GetLicenseQuery SUCCEEDED: RC=0",
        ],
        "templates_failure": [
            " (TomcatPool) exec-{thread} [WARN] [][TomcatAccessFilter]doFilter(): Disk usage exceeds 95% warning threshold",
            " (TomcatPool) exec-{thread} [ERROR] [][LicenseModuleWrapper]getExpiryTime():GetLicenseQuery FAILED: RC=7399",
            " (TomcatPool) exec-{thread} [ERROR] [][TempFileManager]createTempFile(): Failed to write temp buffer file: java.io.IOException: There is not enough space on the disk"
        ]
    },
    "tomcat-stderr.txt": {
        "format": "B",
        "templates_normal": [
            " [GC-Thread-{thread}] - [INFO] GC cleanup completed in {ms}ms",
            " [http-nio-8080-exec-{thread}] - [WARN] org.apache.tomcat.util.threads.LimitLatch.countUp - Close to maxConnections limit",
            " [http-nio-8080-exec-{thread}] - [INFO] org.apache.tomcat.util.threads.ThreadPoolExecutor - Thread pool scale up successful",
        ],
        "templates_failure": [
            " [http-nio-8080-exec-{thread}] - [ERROR] org.apache.catalina.connector.OutputBuffer.realWriteBytes - Failed to write response bytes to buffer: java.io.IOException: There is not enough space on the disk",
            " [Thread-{thread}] - [ERROR] org.apache.tomcat.util.net.NioEndpoint$Acceptor.run - Socket accept failed: java.io.IOException: There is not enough space on the disk"
        ]
    },
    "WebServiceHelper.log": {
        "format": "A",
        "templates_normal": [
            "   00   17844   {thread}             ] WebServiceHelper::Helper: Processing request from client   {{WebServiceHelper.exe::Helper.dll(1.2.3)}}",
            "   00   17844   {thread}             ] WebServiceHelper::Helper: Resource cached locally   {{WebServiceHelper.exe::Helper.dll(1.2.3)}}",
            "   00   17844   {thread}             ] WebServiceHelper::Helper: Connection request to backend succeeded   {{WebServiceHelper.exe::Helper.dll(1.2.3)}}"
        ],
        "templates_failure": [
            "   00   17844   {thread}   0X00000002] WebServiceHelper::Helper: Write operation failed to temp location   {{WebServiceHelper.exe::Helper.dll(1.2.3)}}",
            "   00   17844   {thread}   0X00000070] WebServiceHelper::Helper: Failed to allocate write buffer: EC=112 There is not enough space on the disk   {{WebServiceHelper.exe::Helper.dll(1.2.3)}}"
        ]
    },
    "WebServiceAPI.txt": {
        "format": "A",
        "templates_normal": [
            "   00   12345   {thread}             ] WebServiceAPI::API: Received HTTP request status code 200   {{WebServiceAPI.exe::API.dll(1.2.3)}}",
            "   00   12345   {thread}             ] WebServiceAPI::API: Parsing user authorization claims   {{WebServiceAPI.exe::API.dll(1.2.3)}}",
            "   00   12345   {thread}             ] WebServiceAPI::API: Token refreshed successfully   {{WebServiceAPI.exe::API.dll(1.2.3)}}"
        ],
        "templates_failure": [
            "   00   12345   {thread}   0X00000001] WebServiceAPI::API: Database write connection lost or failed. EC=112   {{WebServiceAPI.exe::API.dll(1.2.3)}}",
            "   00   12345   {thread}   0X00000070] WebServiceAPI::API: Failed to serialize session state: EC=112 There is not enough space on the disk   {{WebServiceAPI.exe::API.dll(1.2.3)}}"
        ]
    },
    "WebService_auth.log": {
        "format": "D",
        "templates_normal": [
            " [INFO] WebServiceAuth: User authenticated successfully",
            " [INFO] WebServiceAuth: Checking LDAP credentials for domain user",
            " [INFO] WebServiceAuth: Token validation passed, signature matches",
            " [WARN] WebServiceAuth: Slow LDAP response for user domain\\admin"
        ],
        "templates_failure": [
            " [WARN] WebServiceAuth: Token cache failed to persist to directory: java.io.IOException: There is not enough space on the disk",
            " [ERROR] WebServiceAuth: Failed to write security audit logs. EC=112"
        ]
    },
    "Backup-Database.log": {
        "format": "A",
        "templates_normal": [
            "   00   15000   {thread}   0X00000000] BackupEngine::DbBackup: Successfully backed up block {block}   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000000] BackupEngine::DbBackup: Verifying checksum for block {block}   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000000] BackupEngine::DbBackup: Table snapshot verified   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}"
        ],
        "templates_failure": [
            "   00   15000   {thread}   0X00000001] BackupEngine::DbBackup: Block write error: EC=112 There is not enough space on the disk   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000070] BackupEngine::DbBackup: Database backup failed due to insufficient space on target drive. EC=112   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}"
        ]
    },
    "Backup-Config.log": {
        "format": "A",
        "templates_normal": [
            "   00   15000   {thread}   0X00000000] BackupEngine::ConfigBackup: Archiving config file {cfg_file}   {{BackupEngine.exe::ConfigBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000000] BackupEngine::ConfigBackup: Compressing registry keys   {{BackupEngine.exe::ConfigBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000000] BackupEngine::ConfigBackup: Serializing system settings   {{BackupEngine.exe::ConfigBackup.dll(2.0.0)}}"
        ],
        "templates_failure": [
            "   00   15000   {thread}   0X00000001] BackupEngine::ConfigBackup: Failed to write configuration archive. EC=112   {{BackupEngine.exe::ConfigBackup.dll(2.0.0)}}"
        ]
    },
    "Backup-Server.log": {
        "format": "A",
        "templates_normal": [
            "   00   15000   {thread}   0X00000000] BackupEngine::ServerBackup: Processing volume backup for {volume}   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000000] BackupEngine::ServerBackup: Snapshot session opened successfully   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000000] BackupEngine::ServerBackup: Read volume boot sector details   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}"
        ],
        "templates_failure": [
            "   00   15000   {thread}   0X00000001] BackupEngine::ServerBackup: Warning, Failed to SetEndOfFile, EC:112 @CSlice::Create:103   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}",
            "   00   15000   {thread}             ] BackupEngine::ServerBackup: WriteToDisk: m_pCurDisk->Write failed. dwBytesToWrite[512], dwWritten[0], DiskSize[107374182400]   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}",
            "   00   15000   {thread}             ] BackupEngine::ServerBackup: Write: WriteToDisk failed. EC=112   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000001] BackupEngine::ServerBackup: BLISession.Write failed, EC=112 @CAFSession::Write:268   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}",
            "   00   15000   {thread}   0X00000001] BackupEngine::ServerBackup: ASyncWrite failed. EC=112 @CDynamicVHD2::_WriteBySliceFormat:5161   {{BackupEngine.exe::ServerBackup.dll(2.0.0)}}"
        ]
    },
    "system.log.1": {
        "format": "E",
        "templates_normal": [
            " [INFO] SystemMonitor: CPU temperature {cpu_temp}C, fan speed 2400 RPM",
            " [INFO] SystemMonitor: Network traffic inbound {net_in} KB/s, outbound {net_out} KB/s",
            " [INFO] SystemMonitor: Memory allocation is normal: {mem_pct}% used",
            " [WARN] SystemMonitor: Disk usage on volume C: is {disk_c}%"
        ],
        "templates_failure": [
            " [WARN] SystemMonitor: Disk space on volume D: is low. Remaining: 850 MB.",
            " [WARN] SystemMonitor: Disk space on volume D: is critical. Remaining: 120 MB.",
            " [ERROR] SystemMonitor: Disk space depleted on volume D:. 0 bytes available. EC=112",
            " [FATAL] SystemMonitor: Write check failed. Disk D: is read-only or full. EC=112"
        ]
    },
    "application.log": {
        "format": "D",
        "templates_normal": [
            " [INFO] ApplicationService: Handled request successfully in {db_dur}ms",
            " [INFO] ApplicationService: Connection pool status: active={active_conn}, idle={idle_conn}",
            " [INFO] ApplicationService: Cleaned up expired user cache items",
            " [WARN] ApplicationService: Connection pool expansion threshold reached"
        ],
        "templates_failure": [
            " [WARN] ApplicationService: Database write latency exceeded threshold: {db_dur_high}ms",
            " [ERROR] ApplicationService: Failed to process task. Exception: java.io.IOException: There is not enough space on the disk (EC=112)"
        ]
    },
    "db_backup.log.bak": {
        "format": "A",
        "templates_normal": [
            "   00   16000   {thread}   0X00000000] BackupEngine::DbBackup: DB block metadata verified   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}",
            "   00   16000   {thread}   0X00000000] BackupEngine::DbBackup: Starting checkpoint save   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}",
            "   00   16000   {thread}   0X00000000] BackupEngine::DbBackup: Flushed transaction log buffer   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}"
        ],
        "templates_failure": [
            "   00   16000   {thread}   0X00000001] BackupEngine::DbBackup: Block serialization aborted due to out-of-disk condition. EC=112   {{BackupEngine.exe::DbBackup.dll(2.0.0)}}"
        ]
    }
}

def generate_file(filename, config, output_dir):
    num_lines = random.randint(1000, 1120)
    target_size = random.randint(188 * 1024, 193 * 1024)
    failure_start_idx = num_lines - random.randint(80, 120)
    
    current_dt = today.replace(hour=1, minute=0, second=0, microsecond=0) + timedelta(minutes=random.randint(0, 15))
    timestamps = []
    for _ in range(num_lines):
        timestamps.append(current_dt)
        current_dt = get_next_timestamp(current_dt)
        
    lines = []
    for i in range(num_lines):
        dt = timestamps[i]
        ts_str = format_timestamp(dt, config["format"])
        
        if i < failure_start_idx:
            tpl = random.choice(config["templates_normal"])
        else:
            tpl = random.choice(config["templates_failure"])
            
        base_msg = make_base_line(tpl, i)
        
        if config["format"] == 'A':
            line = f"[{ts_str}{base_msg}"
        else:
            line = f"{ts_str}{base_msg}"
            
        lines.append(line)
        
    current_bytes = sum(len(line.encode("utf-8")) + 1 for line in lines)
    
    if current_bytes < target_size:
        bytes_needed = target_size - current_bytes
        pad_per_line = bytes_needed // num_lines
        remainder = bytes_needed % num_lines
        
        padded_lines = []
        for i, line in enumerate(lines):
            needed = pad_per_line + (1 if i < remainder else 0)
            padded_line = pad_line_with_context(line, needed)
            padded_lines.append(padded_line)
        lines = padded_lines
    
    final_content = "\n".join(lines) + "\n"
    final_bytes = len(final_content.encode("utf-8"))
    
    out_path = Path(output_dir) / filename
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(final_content)
        
    print(f"Generated {filename}: {num_lines} lines, {final_bytes / 1024:.2f} KB (Target: {target_size/1024:.2f} KB)")

def main():
    output_dir = Path(r"D:\loganalyser\demo\generated")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for filename, config in FILES_CONFIG.items():
        generate_file(filename, config, output_dir)

if __name__ == "__main__":
    main()
