#!/usr/bin/env python3
"""Retain Linux build diagnostics, including the daemon servicing a Nix client."""

import argparse
import base64
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


def read_optional(path):
    try:
        return {"text": path.read_text()}
    except OSError as error:
        return {"error": str(error)}


def processes():
    result = {}
    skipped = 0
    for directory in Path("/proc").iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            stat = (directory / "stat").read_text()
            fields = stat[stat.rfind(")") + 2 :].split()
            status = dict(
                line.split(":", 1)
                for line in (directory / "status").read_text().splitlines()
                if ":" in line
            )
            cmdline = (directory / "cmdline").read_bytes()
            argv = cmdline.split(b"\0")
            result[int(directory.name)] = {
                "pid": int(directory.name),
                "ppid": int(fields[1]),
                "startTicks": int(fields[19]),
                "userTicks": int(fields[11]),
                "systemTicks": int(fields[12]),
                "name": status["Name"].strip(),
                "rssKiB": int(status.get("VmRSS", "0 kB").split()[0]),
                "threads": int(status["Threads"]),
                "allowedCpus": status["Cpus_allowed_list"].strip(),
                "argv": [value.decode(errors="replace") for value in argv if value],
                "cmdlineBase64": base64.b64encode(cmdline).decode("ascii"),
                "cmdlineSha256": hashlib.sha256(cmdline).hexdigest(),
            }
        except (OSError, ValueError, KeyError, IndexError):
            # A process may exit between procfs reads. Count these missing
            # samples instead of treating them as zero resource usage.
            skipped += 1
    return result, skipped


def descendants(table, roots):
    selected = set(roots)
    while True:
        children = {pid for pid, entry in table.items() if entry["ppid"] in selected}
        new = children - selected
        if not new:
            return selected & table.keys()
        selected |= new


def nix_daemon_client(argv):
    # Nix's process-title implementation can expose the client PID either as
    # a second argument or within argv[0]. Accept only those exact titles.
    title = argv[0].split() if len(argv) == 1 else argv
    if len(title) == 2 and Path(title[0]).name == "nix-daemon" and title[1].isdecimal():
        return int(title[1])
    return None


def unified_cgroup(raw):
    if "text" not in raw:
        return None
    for line in raw["text"].splitlines():
        hierarchy, controllers, relative = line.split(":", 2)
        if hierarchy == "0" and not controllers:
            return str(Path("/sys/fs/cgroup") / relative.lstrip("/"))
    return None


def cgroup_state(path):
    return {
        "path": path,
        "files": {
            name: read_optional(Path(path) / name)
            for name in (
                "memory.current", "memory.peak", "memory.max", "memory.events",
                "memory.swap.current", "memory.swap.max", "memory.pressure",
                "cpu.max", "cpuset.cpus.effective",
            )
        },
    }


def cgroup_hierarchy(path):
    root = Path("/sys/fs/cgroup")
    leaf = Path(path)
    leaf.relative_to(root)
    return [str(leaf), *(str(parent) for parent in leaf.parents if parent == root or root in parent.parents)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--client-time", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("a command and positive sampling interval are required")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    args.client_time.parent.mkdir(parents=True, exist_ok=True)

    def write(name, value):
        (args.output_dir / name).write_text(json.dumps(value, indent=2) + "\n")

    host = os.uname()
    runner_cgroup = read_optional(Path("/proc/self/cgroup"))
    runner_group = unified_cgroup(runner_cgroup)
    write("runner.json", {
        "uname": {name: getattr(host, name) for name in ("sysname", "nodename", "release", "version", "machine")},
        "logicalCpuCount": os.cpu_count(),
        "clockTicksPerSecond": os.sysconf("SC_CLK_TCK"),
        "allowedCpus": sorted(os.sched_getaffinity(0)),
        "cpuInfo": read_optional(Path("/proc/cpuinfo")),
        "memoryInfo": read_optional(Path("/proc/meminfo")),
        "processLimits": read_optional(Path("/proc/self/limits")),
        "cgroup": runner_cgroup,
        "corePattern": read_optional(Path("/proc/sys/kernel/core_pattern")),
    })
    write("resource-scope.json", {
        "clientTiming": str(args.client_time),
        "clientTimingScope": "GNU time measures the command client and its children; Nix daemon builders are excluded.",
        "rssScope": "Sampled command descendants plus the Nix daemon whose explicit client PID belongs to this command, and that daemon's descendants.",
        "rssLimitations": "Samples may miss short-lived processes and instantaneous peaks. Summed RSS may count shared pages multiple times. Unreadable or exited processes are counted separately.",
        "intervalSeconds": args.interval,
        "cgroupScope": "Kernel counters for each observed unified cgroup and every ancestor through /sys/fs/cgroup. Ancestor limits also constrain leaves. A group may contain other processes, and memory.peak is cumulative group evidence, not this command's peak. Missing files and read errors remain explicit.",
        "processMetadataScope": "Rendered command lines, raw NUL-separated command-line bytes as base64 with SHA-256, limits and cgroup membership are captured when a process is first observed and when its command-line bytes change across exec; metadata includes the observation time and process start ticks. No environment is captured.",
    })
    write("cgroups-before.json", [cgroup_state(path) for path in cgroup_hierarchy(runner_group)] if runner_group else [])
    started = time.monotonic()
    wrapped = ["/usr/bin/time", "-v", "-o", str(args.client_time), *command]
    record = {
        "argv": command, "wrapperArgv": wrapped, "cwd": os.getcwd(),
        "startedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "running",
    }
    write("command.json", record)
    process = subprocess.Popen(wrapped, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    pump_errors = []

    def forward_output():
        output = None
        forward = True
        try:
            output = (args.output_dir / "command.log").open("wb")
        except OSError as error:
            pump_errors.append(repr(error))
        try:
            while chunk := process.stdout.read1(65536):
                if output is not None:
                    try:
                        output.write(chunk)
                        output.flush()
                    except OSError as error:
                        pump_errors.append(repr(error))
                        output.close()
                        output = None
                if forward:
                    try:
                        sys.stdout.buffer.write(chunk)
                        sys.stdout.buffer.flush()
                    except OSError as error:
                        # Keep draining the child and retaining its private log
                        # even if the caller closes its output pipe.
                        pump_errors.append(repr(error))
                        forward = False
        except Exception as error:
            pump_errors.append(repr(error))
        finally:
            if output is not None:
                output.close()

    pump = threading.Thread(target=forward_output)
    pump.start()
    known_processes = {}
    known_leaves = {runner_group} if runner_group else set()
    known_groups = set(cgroup_hierarchy(runner_group)) if runner_group else set()
    peak_rss = 0
    saw_daemon = False
    sample_count = 0
    monitor_errors = []
    with (args.output_dir / "samples.jsonl").open("w") as samples, (args.output_dir / "processes.jsonl").open("w") as metadata:
        try:
            while True:
                table, skipped = processes()
                selected = descendants(table, {process.pid})
                clients = {pid for pid in selected if table[pid]["argv"] and Path(table[pid]["argv"][0]).name == "nix"}
                daemon_roots = {
                    pid for pid, entry in table.items()
                    if nix_daemon_client(entry["argv"]) in clients
                }
                saw_daemon |= bool(daemon_roots)
                selected |= descendants(table, daemon_roots)
                rows = []
                for pid in sorted(selected):
                    entry = table[pid]
                    identity = (pid, entry["startTicks"])
                    if known_processes.get(identity) != entry["cmdlineSha256"]:
                        known_processes[identity] = entry["cmdlineSha256"]
                        cgroup = read_optional(Path(f"/proc/{pid}/cgroup"))
                        group = unified_cgroup(cgroup)
                        if group:
                            known_leaves.add(group)
                            known_groups.update(cgroup_hierarchy(group))
                        metadata.write(json.dumps({
                            **entry,
                            "observedAfterSeconds": time.monotonic() - started,
                            "limits": read_optional(Path(f"/proc/{pid}/limits")),
                            "cgroup": cgroup,
                        }) + "\n")
                    rows.append({key: entry[key] for key in (
                        "pid", "ppid", "name", "startTicks", "rssKiB",
                        "threads", "allowedCpus", "userTicks", "systemTicks",
                    )})
                rss = sum(entry["rssKiB"] for entry in rows)
                peak_rss = max(peak_rss, rss)
                samples.write(json.dumps({
                    "elapsedSeconds": time.monotonic() - started,
                    "nixClientPids": sorted(clients),
                    "nixDaemonRoots": sorted(daemon_roots),
                    "processes": rows, "aggregateRssKiB": rss,
                    "unreadableOrExitedProcesses": skipped,
                    "processLeafCgroups": sorted(known_leaves),
                    "cgroups": [cgroup_state(path) for path in sorted(known_groups)],
                }) + "\n")
                metadata.flush()
                samples.flush()
                sample_count += 1
                if process.poll() is not None:
                    break
                try:
                    process.wait(timeout=args.interval)
                except subprocess.TimeoutExpired:
                    pass
        except Exception as error:
            monitor_errors.append(repr(error))
    returncode = process.wait()
    pump.join()
    write("cgroups-after.json", [cgroup_state(path) for path in sorted(known_groups)])
    record.update({
        "commandExitCode": returncode,
        "elapsedSeconds": time.monotonic() - started,
        "finishedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sampleCount": sample_count, "sampledPeakAggregateRssKiB": peak_rss,
        "nixDaemonObserved": saw_daemon,
        "monitorErrors": monitor_errors, "outputErrors": pump_errors,
        "status": "pass" if returncode == 0 and not monitor_errors and not pump_errors else "fail",
    })
    write("command.json", record)
    if returncode != 0:
        return returncode if returncode > 0 else 128 - returncode
    return 1 if monitor_errors or pump_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
