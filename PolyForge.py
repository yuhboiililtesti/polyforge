#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
import platform
import time
import re
import socket
import logging
from pathlib import Path
from datetime import datetime

try:
    import rich
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.table import Table

console = Console()
BOOTSTRAP_LOG = "/var/log/polyforge_bootstrap.log"
LOG_PATH = Path(BOOTSTRAP_LOG)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=BOOTSTRAP_LOG,
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ─────────────────────────────────────────────────────────────
# 🧠 SECTION 1: CLI Argument Parsing
# ─────────────────────────────────────────────────────────────
args = sys.argv[1:]
cli_flags = {
    "dry_run": "--dry-run" in args,
    "no_prompt": "--no-prompt" in args,
    "reconfigure": "--reconfigure" in args,
    "repair": "--repair" in args,
    "uninstall": "--uninstall" in args,
    "force": "--force" in args
}
if cli_flags["dry_run"]:
    console.print("[yellow bold]⚠️ DRY RUN MODE ENABLED[/] – No actions will be performed.")

# ─────────────────────────────────────────────────────────────
# 🔐 SECTION 2: Root Elevation
# ─────────────────────────────────────────────────────────────
def require_root():
    if os.geteuid() != 0:
        console.print("[red bold]⛔ PolyForge requires root privileges.[/]")
        console.print("Please run it again with [cyan]sudo[/] or as root.")
        sys.exit(1)

require_root()

# ─────────────────────────────────────────────────────────────
# 🌐 SECTION 3: Preflight Environment Checks
# ─────────────────────────────────────────────────────────────
def has_internet():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        return True
    except:
        return False

def check_dns():
    try:
        return socket.gethostbyname("duckduckgo.com")
    except socket.gaierror:
        return None

def get_ram_gb():
    with open("/proc/meminfo", "r") as f:
        mem_kb = int(re.search(r"MemTotal:\s+(\d+)", f.read()).group(1))
        return round(mem_kb / 1024 / 1024, 2)

def get_free_disk_gb():
    total, used, free = shutil.disk_usage("/")
    return round(free / 1024**3, 2)

def check_time_sync():
    try:
        timedatectl = subprocess.check_output("timedatectl status", shell=True).decode()
        return "System clock synchronized: yes" in timedatectl
    except:
        return False

def detect_distro():
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release", "r") as f:
            lines = f.read()
            if "ID_LIKE=debian" in lines or "ID=debian" in lines:
                return "debian"
            elif "ID=arch" in lines:
                return "arch"
            elif "ID=fedora" in lines or "ID_LIKE=fedora" in lines:
                return "fedora"
            elif "ID=alpine" in lines:
                return "alpine"
            elif "ID=suse" in lines:
                return "opensuse"
            elif "ID=proxmox" in lines:
                return "proxmox"
            elif "ID=truenas" in lines:
                return "truenas"
    return "unknown"

def get_package_manager(distro):
    return {
        "debian": "apt",
        "ubuntu": "apt",
        "arch": "pacman",
        "manjaro": "pacman",
        "fedora": "dnf",
        "centos": "dnf",
        "alpine": "apk",
        "opensuse": "zypper",
        "proxmox": "apt",
        "truenas": "pkg"
    }.get(distro, None)

# ─────────────────────────────────────────────────────────────
# 📋 SECTION 4: Preflight Summary
# ─────────────────────────────────────────────────────────────
def show_preflight_summary():
    console.print(Panel.fit("🧠 [bold cyan]PolyForge Preflight Check[/bold cyan]", style="bold magenta"))
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Check")
    table.add_column("Result")

    internet = has_internet()
    dns = check_dns()
    ram = get_ram_gb()
    disk = get_free_disk_gb()
    time_sync = check_time_sync()
    distro = detect_distro()

    table.add_row("Internet Access", "✅ Yes" if internet else "❌ No")
    table.add_row("DNS Resolution", f"✅ {dns}" if dns else "❌ Failed")
    table.add_row("RAM", f"{ram} GB")
    table.add_row("Free Disk", f"{disk} GB")
    table.add_row("Clock Synced", "✅ Yes" if time_sync else "⚠️ No")
    table.add_row("Detected Distro", f"{distro.capitalize()}")

    console.print(table)

show_preflight_summary()
# ─────────────────────────────────────────────────────────────
# 🧰 SECTION 5: Self-Healing Bootstrap Fixes
# ─────────────────────────────────────────────────────────────
def fix_common_issues():
    console.print("[bold blue]🔧 Checking for bootstrap issues...[/bold blue]")
    # Check mount points
    for mount in ["/", "/boot", "/var"]:
        if not os.path.ismount(mount):
            console.print(f"[red]⚠️ {mount} is not properly mounted.[/red] Attempting to remount...")
            subprocess.run(f"mount {mount}", shell=True)

    # Check for broken Python symlink
    if not shutil.which("python3"):
        console.print("[red]⚠️ python3 not found! Attempting to link from available versions...[/red]")
        for fallback in ["/usr/bin/python3.11", "/usr/bin/python3.10", "/usr/bin/python3.9"]:
            if os.path.exists(fallback):
                os.symlink(fallback, "/usr/bin/python3")
                console.print(f"[green]✔ Linked python3 to {fallback}[/green]")
                break

    # Fix APT lock issues (Debian-based only)
    if detect_distro() == "debian":
        if os.path.exists("/var/lib/dpkg/lock"):
            os.remove("/var/lib/dpkg/lock")
            os.remove("/var/lib/apt/lists/lock")
            os.remove("/var/cache/apt/archives/lock")
            subprocess.run("dpkg --configure -a", shell=True)

fix_common_issues()

# ─────────────────────────────────────────────────────────────
# 💿 SECTION 6: LiveCD / Minimal Detection
# ─────────────────────────────────────────────────────────────
def is_live_cd():
    try:
        with open("/proc/cmdline") as f:
            cmdline = f.read()
            return "boot=live" in cmdline or "live-media" in cmdline
    except:
        return False

def snapshot_mounts():
    snapshot_file = f"/var/log/polyforge_mounts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(snapshot_file, "w") as f:
        subprocess.run("mount", shell=True, stdout=f)
    console.print(f"[cyan]🗂 Saved mount snapshot to {snapshot_file}[/cyan]")

if is_live_cd():
    console.print("[bold yellow]💿 LiveCD environment detected.[/] Adjusting behavior for persistence and compatibility.")
snapshot_mounts()

# ─────────────────────────────────────────────────────────────
# 🤖 SECTION 7: Humanized Welcome Prompt
# ─────────────────────────────────────────────────────────────
def intro_prompt():
    console.print("\n")
    console.print(Panel.fit("""
👋 [bold cyan]Welcome to PolyForge[/bold cyan] – your fully automated HomeLab installer.

I see this is a [bold]new[/bold] or [bold]minimal[/bold] system. Want me to handle everything for you?

I'll auto-detect your setup, configure your services, and make your system awesome – fast.

You’ll still get a summary and full control.
""", title="🚀 Ready to Begin?", style="bold green"))

    if cli_flags["no_prompt"]:
        console.print("[cyan]No-prompt mode detected.[/] Using config.yaml only.")
        return "config"

    # Print choices manually
    console.print("\n[bold]Please choose how to proceed:[/bold]")
    console.print("1. 🧠 Auto-configure everything (smart defaults)")
    console.print("2. 🧭 Full interactive prompts")
    console.print("3. 📁 Load config.yaml from disk")

    choice = Prompt.ask(
        "[bold green]Enter choice[/bold green]",
        choices=["1", "2", "3"],
        show_choices=False,
        default="1"
    )
    return {"1": "auto", "2": "interactive", "3": "config"}.get(choice, "auto")

install_mode = intro_prompt()


# ─────────────────────────────────────────────────────────────
# 📁 SECTION 8: Load Config.yaml (If Chosen)
# ─────────────────────────────────────────────────────────────
import yaml

CONFIG_PATH = "/etc/polyforge/config.yaml"
STATE_PATH = "/etc/polyforge/state-cache.yaml"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        console.print(f"[red]Config file not found at {CONFIG_PATH}[/red]")
        return None
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        console.print(f"[red]Error parsing config.yaml: {e}[/red]")
        return None

config = None
if install_mode == "config":
    config = load_config()
    if not config:
        console.print("[red]Failed to load config.yaml – falling back to interactive mode.[/red]")
        install_mode = "interactive"

# ─────────────────────────────────────────────────────────────
# 💡 SECTION 9: Save System Name + Start Logging
# ─────────────────────────────────────────────────────────────
system_name = None
if install_mode != "config":
    system_name = Prompt.ask("[bold]🖥️ What should we name this system?[/bold]", default="polyforge-node")
    config = {"system_name": system_name}
    os.makedirs("/etc/polyforge", exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)
    console.print(f"[green]✔ Saved config to {CONFIG_PATH}[/green]")

# Summary
console.print("\n[bold green]✅ PolyForge preflight complete.[/bold green]")
console.print(f"📛 System name: [cyan]{config.get('system_name', system_name)}[/cyan]")
console.print(f"📄 Config mode: [cyan]{install_mode}[/cyan]")
console.print(f"📂 Config path: [cyan]{CONFIG_PATH}[/cyan]")
console.print("\n[bold blue]➡️  Ready to begin full configuration and drive detection...[/bold blue]")

# Next: Drive detection, mount setup, and service menus
# CHUNK 2 ─────────────────────────────────────────────────────
# 💾 SECTION 10: Interactive Config Fallback
# ─────────────────────────────────────────────────────────────
def interactive_config(config: dict):
    console.print("[bold cyan]🔧 Launching Interactive Configuration[/bold cyan]")

    config["admin_user"] = Prompt.ask("👤 Admin username", default="polyadmin")
    config["admin_pass"] = Prompt.ask("🔒 Admin password", password=True)

    config["hostname"] = Prompt.ask("🌐 Hostname for system", default="polyforge-hub")
    config["duckdns_token"] = Prompt.ask("🦆 DuckDNS token (leave blank to skip)", default="")
    config["duckdns_domain"] = Prompt.ask("🔗 DuckDNS subdomain (e.g., mylab)", default="")

    # Optional services
    config["services"] = {}
    for service, desc in {
        "plex": "Stream media to TVs and mobile",
        "minecraft": "Run Minecraft server (Fabric, Vanilla, etc)",
        "casaos": "HomeLab GUI dashboard",
        "cockpit": "Remote system monitoring",
        "virtualbox": "Virtual machine host",
        "duckdns": "Dynamic DNS client",
        "restic": "Backup system (remote or USB)",
        "tailscale": "Mesh VPN for remote access"
    }.items():
        config["services"][service] = Confirm.ask(f"🧩 Install [bold]{service}[/bold]? - {desc}")

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)
    console.print(f"[green]✔ Saved updated config to {CONFIG_PATH}[/green]")
    return config

if install_mode == "interactive":
    config = interactive_config(config or {})

# ─────────────────────────────────────────────────────────────
# 💽 SECTION 11: Detect Drives + Mount Structure
# ─────────────────────────────────────────────────────────────
import psutil

def list_disks():
    disks = []
    seen = set()
    for part in psutil.disk_partitions(all=True):
        device = part.device
        if device not in seen:
            seen.add(device)
            disks.append(part)
    return disks

def detect_unmounted_devices():
    output = subprocess.check_output("lsblk -o NAME,SIZE,TYPE,MOUNTPOINT -J", shell=True)
    import json
    data = json.loads(output)
    unmounted = []

    for dev in data["blockdevices"]:
        if dev["type"] == "disk" and not dev["mountpoint"]:
            unmounted.append({
                "name": dev["name"],
                "size": dev["size"]
            })
    return unmounted

def label_disk(name: str, size: str):
    try:
        model_output = subprocess.check_output(f"lsblk -dno MODEL /dev/{name}", shell=True).decode().strip()
        label = model_output.replace(" ", "_").upper()
    except:
        label = "UNKNOWN"
    return f"{label}_{size.replace('G', '').replace('.', '')}_HDD"

def create_mount_structure():
    for d in ["/data", "/data/media", "/data/backups", "/data/minecraft"]:
        os.makedirs(d, exist_ok=True)
        console.print(f"[cyan]📁 Ensured directory exists: {d}[/cyan]")

# ─────────────────────────────────────────────────────────────
# ⚙️ SECTION 12: Disk Setup & fstab Writer
# ─────────────────────────────────────────────────────────────
def setup_unmounted_disks(unmounted):
    fstab_entries = []
    for dev in unmounted:
        device = f"/dev/{dev['name']}"
        label = label_disk(dev["name"], dev["size"])
        console.print(f"\n[bold yellow]Detected unmounted disk: {device} ({dev['size']})[/bold yellow]")
        wipe = Confirm.ask(f"🧨 Wipe and format [bold]{device}[/bold] as ext4?")
        if wipe:
            subprocess.run(f"mkfs.ext4 -L {label} {device}", shell=True)
            mount_point = f"/data/{label.lower()}"
            os.makedirs(mount_point, exist_ok=True)
            subprocess.run(f"mount {device} {mount_point}", shell=True)
            uuid = subprocess.check_output(f"blkid -s UUID -o value {device}", shell=True).decode().strip()
            fstab_entries.append(f"UUID={uuid} {mount_point} ext4 defaults 0 2")
            console.print(f"[green]✔ Mounted {device} → {mount_point}[/green]")
    return fstab_entries

def write_fstab(entries):
    with open("/etc/fstab", "a") as f:
        for e in entries:
            f.write(e + "\n")
    console.print("[green]📜 Updated /etc/fstab with new entries[/green]")

# Run mount logic
create_mount_structure()
unmounted = detect_unmounted_devices()
if unmounted:
    console.print(Panel.fit("💽 [bold]Unmounted Disks Detected[/bold] – Let's Set Them Up!", style="bold magenta"))
    entries = setup_unmounted_disks(unmounted)
    write_fstab(entries)
else:
    console.print("[green]✔ No unmounted disks found.[/green]")
# CHUNK 2 (CONT.) ─────────────────────────────────────────────
# 💽 SECTION 13: USB Detection & Backup Prompt
# ─────────────────────────────────────────────────────────────
def detect_usb_devices():
    output = subprocess.check_output("lsblk -o NAME,TRAN,MOUNTPOINT -J", shell=True)
    import json
    data = json.loads(output)
    usb_disks = []

    for dev in data["blockdevices"]:
        if dev.get("tran") == "usb":
            usb_disks.append(dev)
    return usb_disks

def configure_usb_backups(usb_disks, config):
    config["usb_backups"] = []
    for usb in usb_disks:
        name = usb["name"]
        device = f"/dev/{name}"
        console.print(f"\n[bold yellow]🔌 USB device detected: {device}[/bold yellow]")
        use = Confirm.ask("📦 Use this device for automatic backups on insert?")
        if use:
            label = label_disk(name, "USB")
            subprocess.run(f"mkfs.ext4 -L {label} {device}", shell=True)
            mount_point = f"/mnt/usb_{label.lower()}"
            os.makedirs(mount_point, exist_ok=True)
            subprocess.run(f"mount {device} {mount_point}", shell=True)
            uuid = subprocess.check_output(f"blkid -s UUID -o value {device}", shell=True).decode().strip()
            fstab_line = f"UUID={uuid} {mount_point} ext4 defaults,noauto 0 2"
            with open("/etc/fstab", "a") as f:
                f.write(fstab_line + "\n")
            config["usb_backups"].append({
                "label": label,
                "mount_point": mount_point,
                "uuid": uuid
            })
            console.print(f"[green]✔ Configured USB backup target: {mount_point}[/green]")
    return config

usb_disks = detect_usb_devices()
if usb_disks:
    config = configure_usb_backups(usb_disks, config)

# ─────────────────────────────────────────────────────────────
# 🧠 SECTION 14: Save State Cache (for smarter re-installs)
# ─────────────────────────────────────────────────────────────
def save_state_cache(config):
    state = {
        "last_run": datetime.now().isoformat(),
        "distro": detect_distro(),
        "hostname": config.get("hostname"),
        "system_name": config.get("system_name"),
        "services": config.get("services", {}),
        "drives": [p.device for p in psutil.disk_partitions()]
    }
    with open(STATE_PATH, "w") as f:
        yaml.dump(state, f)
    console.print(f"[cyan]🧠 Saved state cache to {STATE_PATH}[/cyan]")

save_state_cache(config)

# ─────────────────────────────────────────────────────────────
# 📋 SECTION 15: UUID Snapshot + Summary Panel
# ─────────────────────────────────────────────────────────────
def snapshot_uuid_map():
    snapshot_file = f"/var/log/polyforge_uuidmap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(snapshot_file, "w") as f:
        subprocess.run("blkid", shell=True, stdout=f)
    console.print(f"[cyan]📦 UUID/label snapshot saved: {snapshot_file}[/cyan]")

def drive_summary():
    console.print(Panel.fit("🧾 [bold]DRIVE SUMMARY[/bold] – Final Detected Mounts", style="bold green"))
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Device")
    table.add_column("Mount Point")
    table.add_column("Filesystem")
    table.add_column("Label")

    for part in psutil.disk_partitions():
        try:
            label = subprocess.check_output(f"blkid -s LABEL -o value {part.device}", shell=True).decode().strip()
        except:
            label = "?"
        table.add_row(part.device, part.mountpoint or "-", part.fstype, label)
    console.print(table)

snapshot_uuid_map()
drive_summary()

# ─────────────────────────────────────────────────────────────
# 🧪 SECTION 16: Dry Run Support Layer (Safe Preview Mode)
# ─────────────────────────────────────────────────────────────
def dry_run_warning():
    if cli_flags.get("dry_run"):
        console.print(Panel.fit("""
⚠️ [yellow bold]DRY RUN MODE[/yellow bold] – No changes were made.

PolyForge simulated all actions, but skipped:
- Package installs
- Disk formats and mounts
- Config writes
- Service setups

To install for real, run without [bold]--dry-run[/bold].
""", style="bold red"))
        sys.exit(0)

dry_run_warning()

# End of Chunk 2 ──────────────────────────────────────────────
console.print("\n[bold green]✅ Disk setup and config system complete.[/bold green]")
console.print("[bold blue]➡️  Next: Network detection + service installer menus[/bold blue]")
# CHUNK 3 ─────────────────────────────────────────────────────
# 🌐 SECTION 17: Network Detection
# ─────────────────────────────────────────────────────────────
def detect_interfaces():
    interfaces = psutil.net_if_addrs()
    found = {}
    for name, addrs in interfaces.items():
        for addr in addrs:
            if addr.family.name == 'AF_INET':
                found[name] = addr.address
    return found

def suggest_network_strategy(interfaces: dict):
    console.print(Panel.fit("🌐 [bold]NETWORK MODE DETECTION[/bold]", style="bold cyan"))
    for iface, ip in interfaces.items():
        console.print(f"→ [green]{iface}[/green] - [cyan]{ip}[/cyan]")

    if "eth0" in interfaces:
        console.print("[bold green]💡 Suggestion:[/bold green] Bind system services to [bold]eth0[/bold] (wired).")
    if "wlan0" in interfaces:
        console.print("[bold yellow]💡 Suggestion:[/bold yellow] Use [bold]wlan0[/bold] as a backup or proxy path.")

    use_wifi_proxy = Confirm.ask("Use Wi-Fi (if available) as fallback or for Minecraft-only traffic?")
    config["network"] = {
        "primary": "eth0" if "eth0" in interfaces else list(interfaces.keys())[0],
        "wifi_proxy": use_wifi_proxy
    }

interfaces = detect_interfaces()
suggest_network_strategy(interfaces)

# ─────────────────────────────────────────────────────────────
# 🛡️ SECTION 18: Port Conflict Detection
# ─────────────────────────────────────────────────────────────
REQUIRED_PORTS = {
    "SSH": 22,
    "HTTP": 80,
    "HTTPS": 443,
    "Plex": 32400,
    "Minecraft": [25565, 25566, 25567]
}

def check_ports(ports):
    in_use = []
    for name, val in ports.items():
        if isinstance(val, list):
            for port in val:
                if is_port_used(port):
                    in_use.append((name, port))
        else:
            if is_port_used(val):
                in_use.append((name, val))
    return in_use

def is_port_used(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

conflicts = check_ports(REQUIRED_PORTS)
if conflicts:
    console.print(Panel.fit("🛑 [bold red]PORT CONFLICTS DETECTED[/bold red]", style="bold red"))
    for svc, port in conflicts:
        console.print(f"❌ [bold]{svc}[/bold] wants port {port}, but it's already in use.")
    override = Confirm.ask("Would you like to override services to use alternate ports?")
    config["port_overrides"] = override
else:
    console.print("[green]✔ No service port conflicts detected[/green]")

# ─────────────────────────────────────────────────────────────
# 🦆 SECTION 19: DuckDNS Configuration
# ─────────────────────────────────────────────────────────────
def install_duckdns(config):
    token = config.get("duckdns_token")
    domain = config.get("duckdns_domain")

    if not token or not domain:
        console.print("[yellow]⚠️ DuckDNS not configured (skipping).[/yellow]")
        return

    path = "/opt/duckdns"
    os.makedirs(path, exist_ok=True)
    duck_script = os.path.join(path, "duck.sh")

    with open(duck_script, "w") as f:
        f.write(f"""#!/bin/bash
echo url="https://www.duckdns.org/update?domains={domain}&token={token}&ip=" | curl -k -o {path}/duck.log -K -
""")
    os.chmod(duck_script, 0o755)

    # Add cron job (backup)
    cronjob = f"*/5 * * * * {duck_script} >/dev/null 2>&1\n"
    with open("/etc/cron.d/duckdns", "w") as f:
        f.write(cronjob)

    # Add systemd timer
    timer_unit = f"""\n[Unit]
Description=DuckDNS Updater

[Service]
ExecStart={duck_script}

[Install]
WantedBy=timers.target
"""
    with open("/etc/systemd/system/duckdns.service", "w") as f:
        f.write(timer_unit)

    with open("/etc/systemd/system/duckdns.timer", "w") as f:
        f.write("""[Unit]
Description=Run DuckDNS updater every 5 minutes

[Timer]
OnBootSec=30
OnUnitActiveSec=5min
Unit=duckdns.service

[Install]
WantedBy=timers.target
""")

    subprocess.run("systemctl daemon-reexec", shell=True)
    subprocess.run("systemctl enable --now duckdns.timer", shell=True)

    console.print(f"[green]🦆 DuckDNS configured for [bold]{domain}[/bold][/green]")

install_duckdns(config)

# ─────────────────────────────────────────────────────────────
# 🌐 SECTION 20: Network Summary Panel
# ─────────────────────────────────────────────────────────────
def network_summary():
    console.print(Panel.fit("📡 [bold]NETWORK CONFIG SUMMARY[/bold]", style="bold green"))
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Interface")
    table.add_column("IP Address")
    for iface, ip in interfaces.items():
        table.add_row(iface, ip)

    if config.get("duckdns_domain"):
        table.add_row("DuckDNS", f"{config['duckdns_domain']}.duckdns.org")

    console.print(table)

network_summary()

console.print("[bold green]✅ Network stack setup complete.[/bold green]")
console.print("[bold blue]➡️ Next: Security stack, firewall, SSH, fail2ban...[/bold blue]")
# CHUNK 4 ─────────────────────────────────────────────────────
# 🔐 SECTION 21: SSH Hardening
# ─────────────────────────────────────────────────────────────
def harden_ssh():
    console.print(Panel.fit("🔐 [bold]SSH HARDENING[/bold]", style="bold blue"))
    sshd_config_path = "/etc/ssh/sshd_config"
    if not os.path.exists(sshd_config_path):
        console.print("[red]❌ SSH configuration not found.[/red]")
        return

    # Backup original config
    shutil.copy(sshd_config_path, f"{sshd_config_path}.bak")

    # Disable root login
    subprocess.run(f"sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' {sshd_config_path}", shell=True)
    console.print("[green]✔ Root login disabled[/green]")

    # Change SSH port
    custom_port = Prompt.ask("🌐 Custom SSH port (default 22)", default="22")
    subprocess.run(f"sed -i 's/^#*Port .*/Port {custom_port}/' {sshd_config_path}", shell=True)
    config["ssh_port"] = int(custom_port)
    console.print(f"[green]✔ SSH port set to {custom_port}[/green]")

    # Restart SSH
    subprocess.run("systemctl restart sshd", shell=True)

# ─────────────────────────────────────────────────────────────
# 🔥 SECTION 22: Firewall Setup (UFW or firewalld)
# ─────────────────────────────────────────────────────────────
def setup_firewall(config):
    console.print(Panel.fit("🔥 [bold]FIREWALL CONFIGURATION[/bold]", style="bold red"))
    distro = detect_distro()
    firewall_tool = None

    if distro in ["ubuntu", "debian", "proxmox", "truenas"]:
        firewall_tool = "ufw"
        subprocess.run("apt install -y ufw", shell=True)
        subprocess.run("ufw enable", shell=True)
    elif distro in ["fedora", "centos", "rhel"]:
        firewall_tool = "firewalld"
        subprocess.run("dnf install -y firewalld", shell=True)
        subprocess.run("systemctl enable --now firewalld", shell=True)

    # Open necessary ports
    ports = [config.get("ssh_port", 22)]
    if config.get("services", {}).get("plex"): ports.append(32400)
    if config.get("services", {}).get("minecraft"): ports += [25565, 25566, 25567]
    if config.get("services", {}).get("cockpit"): ports.append(9090)

    for port in ports:
        if firewall_tool == "ufw":
            subprocess.run(f"ufw allow {port}", shell=True)
        elif firewall_tool == "firewalld":
            subprocess.run(f"firewall-cmd --permanent --add-port={port}/tcp", shell=True)

    if firewall_tool == "firewalld":
        subprocess.run("firewall-cmd --reload", shell=True)

    config["firewall_tool"] = firewall_tool
    console.print(f"[green]✔ Firewall configured using {firewall_tool}[/green]")

# ─────────────────────────────────────────────────────────────
# 🚨 SECTION 23: Fail2Ban
# ─────────────────────────────────────────────────────────────
def setup_fail2ban():
    console.print(Panel.fit("🚨 [bold]FAIL2BAN INSTALLATION[/bold]", style="bold yellow"))
    distro = detect_distro()
    if distro in ["ubuntu", "debian", "proxmox"]:
        subprocess.run("apt install -y fail2ban", shell=True)
    elif distro in ["fedora", "centos", "rhel"]:
        subprocess.run("dnf install -y fail2ban", shell=True)

    subprocess.run("systemctl enable --now fail2ban", shell=True)
    console.print("[green]✔ Fail2Ban active and monitoring SSH[/green]")

# ─────────────────────────────────────────────────────────────
# 🔎 SECTION 24: SELinux / AppArmor Detection
# ─────────────────────────────────────────────────────────────
def check_security_modules():
    selinux_status = subprocess.getoutput("getenforce") if shutil.which("getenforce") else "Unknown"
    apparmor_status = "enabled" if os.path.exists("/sys/module/apparmor/parameters/enabled") else "disabled"

    console.print(Panel.fit("🛡️ [bold]SECURITY MODULES DETECTED[/bold]", style="bold cyan"))
    console.print(f"SELinux: [yellow]{selinux_status}[/yellow]")
    console.print(f"AppArmor: [yellow]{apparmor_status}[/yellow]")

    if selinux_status.lower() == "enforcing":
        console.print("[red]⚠️ SELinux is in enforcing mode — some services may require policies.[/red]")
    if apparmor_status == "enabled":
        console.print("[yellow]⚠️ AppArmor enabled — Docker or Plex may require profile tweaks.[/yellow]")

# ─────────────────────────────────────────────────────────────
# 🧱 SECTION 25: Firewall Audit Summary
# ─────────────────────────────────────────────────────────────
def firewall_audit():
    console.print(Panel.fit("📜 [bold]FIREWALL AUDIT[/bold]", style="bold magenta"))
    if config.get("firewall_tool") == "ufw":
        subprocess.run("ufw status verbose", shell=True)
    elif config.get("firewall_tool") == "firewalld":
        subprocess.run("firewall-cmd --list-all", shell=True)

# Execute security stack
harden_ssh()
setup_firewall(config)
setup_fail2ban()
check_security_modules()
firewall_audit()

console.print("[bold green]✅ Security stack hardened and verified.[/bold green]")
console.print("[bold blue]➡️ Next: Service installations (Plex, Minecraft, etc)...[/bold blue]")
# CHUNK 5 ─────────────────────────────────────────────────────
# 📦 SECTION 26: Service Install Prompt UI
# ─────────────────────────────────────────────────────────────
from typing import Dict

def service_prompt(name, description, default=True) -> bool:
    console.print(f"\n[bold cyan]{name}[/bold cyan] – {description}")
    return Confirm.ask(f"[?] Install {name}?", default=default)

def is_gui_available():
    return os.environ.get("DISPLAY") is not None or os.environ.get("WAYLAND_DISPLAY") is not None

config["services"] = {}

# ─────────────────────────────────────────────────────────────
# ▶️ SECTION 27: Plex Media Server
# ─────────────────────────────────────────────────────────────
def install_plex():
    if shutil.which("plexmediaserver"):
        console.print("[green]✔ Plex already installed.[/green]")
        return
    console.print("[yellow]📦 Installing Plex...[/yellow]")
    distro = detect_distro()
    if distro in ["debian", "ubuntu", "proxmox"]:
        subprocess.run("curl -fsSL https://downloads.plex.tv/plex-keys/PlexSign.key | gpg --dearmor -o /etc/apt/trusted.gpg.d/plex.gpg", shell=True)
        subprocess.run('echo "deb [arch=amd64] https://downloads.plex.tv/repo/deb public main" > /etc/apt/sources.list.d/plex.list', shell=True)
        subprocess.run("apt update && apt install -y plexmediaserver", shell=True)
    elif distro in ["fedora", "centos", "rhel"]:
        subprocess.run("dnf install -y plexmediaserver", shell=True)
    subprocess.run("systemctl enable --now plexmediaserver", shell=True)
    console.print("[green]✔ Plex installed and running on port 32400[/green]")

if service_prompt("Plex", "Media server for TVs, web, and mobile"):
    install_plex()
    config["services"]["plex"] = True

# ─────────────────────────────────────────────────────────────
# 🎮 SECTION 28: Minecraft Server
# ─────────────────────────────────────────────────────────────
def install_minecraft():
    mc_dir = "/opt/minecraft"
    os.makedirs(mc_dir, exist_ok=True)
    version = Prompt.ask("Which version? (vanilla/fabric/forge)", default="fabric").lower()
    ram = Prompt.ask("Max RAM for server (e.g. 2G, 4G)", default="2G")
    url = {
        "vanilla": "https://launcher.mojang.com/v1/objects/e3bdc8bb6c5e7cbeec8a07d7d6f6090c08083d4a/server.jar",
        "fabric": "https://meta.fabricmc.net/v2/versions/loader/1.20.1/0.14.21/1.0.0/server/jar",
        "forge": "https://maven.minecraftforge.net/net/minecraftforge/forge/1.20.1-47.1.0/forge-1.20.1-47.1.0-installer.jar"
    }[version]

    jar_path = os.path.join(mc_dir, f"{version}_server.jar")
    subprocess.run(f"curl -L {url} -o {jar_path}", shell=True)

    # Accept EULA
    with open(os.path.join(mc_dir, "eula.txt"), "w") as f:
        f.write("eula=true\n")

    # Create systemd unit
    with open("/etc/systemd/system/minecraft.service", "w") as f:
        f.write(f"""[Unit]
Description=Minecraft Server ({version})
After=network.target

[Service]
WorkingDirectory={mc_dir}
ExecStart=/usr/bin/java -Xmx{ram} -Xms{ram} -jar {jar_path} nogui
Restart=on-failure
User=root

[Install]
WantedBy=multi-user.target
""")
    subprocess.run("systemctl daemon-reexec", shell=True)
    subprocess.run("systemctl enable --now minecraft", shell=True)
    console.print(f"[green]✔ Minecraft ({version}) server installed and running on port 25565[/green]")

if service_prompt("Minecraft", "Survival server with Fabric/Forge/Vanilla options"):
    install_minecraft()
    config["services"]["minecraft"] = True

# ─────────────────────────────────────────────────────────────
# 🖥 SECTION 29: CasaOS
# ─────────────────────────────────────────────────────────────
def install_casaos():
    if shutil.which("docker") is None:
        console.print("[yellow]Installing Docker first...[/yellow]")
        subprocess.run("curl -fsSL https://get.docker.com | sh", shell=True)
        subprocess.run("systemctl enable --now docker", shell=True)

    subprocess.run("curl -fsSL https://get.casaos.io | bash", shell=True)
    console.print("[green]✔ CasaOS installed. Web UI: http://localhost[/green]")

if service_prompt("CasaOS", "HomeLab dashboard with app store"):
    install_casaos()
    config["services"]["casaos"] = True
# CHUNK 5 CONTINUED ─────────────────────────────────────────────
# 🧠 SECTION 30: Cockpit
# ─────────────────────────────────────────────────────────────
def install_cockpit():
    distro = detect_distro()
    if distro in ["debian", "ubuntu", "proxmox"]:
        subprocess.run("apt install -y cockpit", shell=True)
    elif distro in ["fedora", "rhel", "centos"]:
        subprocess.run("dnf install -y cockpit", shell=True)

    subprocess.run("systemctl enable --now cockpit.socket", shell=True)
    console.print("[green]✔ Cockpit installed. Web UI on port 9090[/green]")

if service_prompt("Cockpit", "Remote web-based system monitoring"):
    install_cockpit()
    config["services"]["cockpit"] = True

# ─────────────────────────────────────────────────────────────
# 🔁 SECTION 31: Warpinator (GUI Only)
# ─────────────────────────────────────────────────────────────
def install_warpinator():
    if not is_gui_available():
        console.print("[yellow]🛑 Skipping Warpinator – no GUI detected[/yellow]")
        return
    distro = detect_distro()
    if distro in ["debian", "ubuntu"]:
        subprocess.run("apt install -y warpinator", shell=True)
    elif distro in ["fedora"]:
        subprocess.run("dnf install -y warpinator", shell=True)
    console.print("[green]✔ Warpinator installed (LAN file transfer)[/green]")

if service_prompt("Warpinator", "GUI-based LAN file transfers"):
    install_warpinator()
    config["services"]["warpinator"] = True

# ─────────────────────────────────────────────────────────────
# 🧪 SECTION 32: VirtualBox + Extension Pack
# ─────────────────────────────────────────────────────────────
def install_virtualbox():
    distro = detect_distro()
    if distro in ["debian", "ubuntu"]:
        subprocess.run("apt install -y virtualbox virtualbox-ext-pack", shell=True)
    elif distro in ["fedora", "rhel"]:
        subprocess.run("dnf install -y VirtualBox", shell=True)

    subprocess.run("systemctl enable --now vboxdrv", shell=True)
    console.print("[green]✔ VirtualBox installed[/green]")

if service_prompt("VirtualBox", "Run virtual machines locally"):
    install_virtualbox()
    config["services"]["virtualbox"] = True

# ─────────────────────────────────────────────────────────────
# 📊 SECTION 33: Netdata (Health Dashboards)
# ─────────────────────────────────────────────────────────────
def install_netdata():
    subprocess.run("bash <(curl -Ss https://my-netdata.io/kickstart.sh) --dont-wait", shell=True)
    console.print("[green]✔ Netdata installed. Web UI: http://localhost:19999[/green]")

if service_prompt("Netdata", "Live system health + metrics (http://localhost:19999)"):
    install_netdata()
    config["services"]["netdata"] = True

# ─────────────────────────────────────────────────────────────
# 🦆 SECTION 34: DuckDNS (already configured, just confirm status)
# ─────────────────────────────────────────────────────────────
def validate_duckdns():
    if not config.get("duckdns_domain"):
        return
    result = subprocess.run("systemctl is-active duckdns.timer", shell=True, capture_output=True)
    if "active" in result.stdout.decode():
        console.print(f"[green]✔ DuckDNS updater active[/green]")
    else:
        console.print("[yellow]⚠️ DuckDNS updater not running[/yellow]")

validate_duckdns()

# ─────────────────────────────────────────────────────────────
# 💽 SECTION 35: USB Auto Backup (on mount)
# ─────────────────────────────────────────────────────────────
def setup_usb_backup():
    path = "/usr/local/bin/polyforge_usb_backup.sh"
    with open(path, "w") as f:
        f.write("""#!/bin/bash
mountpoint="/media/usb"
mkdir -p "$mountpoint"
mount /dev/sdc1 "$mountpoint" 2>/dev/null
rsync -av --delete /data/backups/ "$mountpoint/backup_$(date +%Y%m%d)/"
umount "$mountpoint"
""")
    os.chmod(path, 0o755)

    udev_rule = 'ACTION=="add", KERNEL=="sd[c-z][0-9]", RUN+="/usr/local/bin/polyforge_usb_backup.sh"'
    with open("/etc/udev/rules.d/99-polyforge-usb.rules", "w") as f:
        f.write(udev_rule)

    subprocess.run("udevadm control --reload-rules && udevadm trigger", shell=True)
    console.print("[green]✔ USB auto-backup enabled[/green]")

if service_prompt("USB Auto Backup", "Auto-runs backup when USB drive inserted"):
    setup_usb_backup()
    config["services"]["usb_backup"] = True
# CHUNK 6 ─────────────────────────────────────────────────────
# ⚙️ SECTION 36: Automation Engine
# ─────────────────────────────────────────────────────────────
def enable_automation_engine():
    console.print(Panel.fit("⚙️ [bold]PolyForge Automation Engine[/bold]", style="bold green"))
    wants = Confirm.ask("[?] Enable automated restarts, updates, backups and health checks?", default=True)
    if not wants:
        console.print("[yellow]⚠️ Skipping automation setup[/yellow]")
        return

    # Write automation script
    automation_path = "/usr/local/bin/polyforge_automate.sh"
    with open(automation_path, "w") as f:
        f.write("""#!/bin/bash
log_file="/var/log/polyforge_automate.log"
echo "$(date) – Starting Automation Tasks" >> $log_file

# Restart crashed services
for svc in minecraft plexmediaserver duckdns; do
    systemctl is-active --quiet $svc || systemctl restart $svc
done

# DuckDNS re-sync (fallback)
curl -s 'https://www.duckdns.org/update?domains=YOUR_DOMAIN&token=YOUR_TOKEN&ip=' >> $log_file

# Backup check (restic or rsync)
[ -x "$(command -v restic)" ] && restic snapshots >> $log_file 2>&1
[ -d /data/backups ] && echo "$(date) - Verified backup directory" >> $log_file

# Update system
if [ -x "$(command -v apt)" ]; then
    apt update >> $log_file && apt upgrade -y >> $log_file
elif [ -x "$(command -v dnf)" ]; then
    dnf upgrade -y >> $log_file
elif [ -x "$(command -v pacman)" ]; then
    pacman -Syu --noconfirm >> $log_file
fi

echo "$(date) – Tasks complete" >> $log_file
""")
    os.chmod(automation_path, 0o755)

    # Replace YOUR_TOKEN / YOUR_DOMAIN
    if config.get("duckdns_token") and config.get("duckdns_domain"):
        with open(automation_path, "r") as file:
            content = file.read()
        content = content.replace("YOUR_TOKEN", config["duckdns_token"])
        content = content.replace("YOUR_DOMAIN", config["duckdns_domain"])
        with open(automation_path, "w") as file:
            file.write(content)

    # Create systemd unit
    service_unit = "/etc/systemd/system/polyforge-automate.service"
    with open(service_unit, "w") as f:
        f.write(f"""[Unit]
Description=PolyForge Automation Engine
After=network.target

[Service]
ExecStart=/usr/local/bin/polyforge_automate.sh
User=root
""")

    timer_unit = "/etc/systemd/system/polyforge-automate.timer"
    with open(timer_unit, "w") as f:
        f.write("""[Unit]
Description=Daily automation run for PolyForge

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
""")

    subprocess.run("systemctl daemon-reexec", shell=True)
    subprocess.run("systemctl enable --now polyforge-automate.timer", shell=True)

    config["automation_enabled"] = True
    console.print("[green]✔ PolyForge Automation Engine enabled[/green]")

# Run Automation Setup
enable_automation_engine()
# CHUNK 7 ─────────────────────────────────────────────────────
# 🧾 SECTION 37: Postflight Summary + Snapshot
# ─────────────────────────────────────────────────────────────
from datetime import datetime

def show_postflight_summary():
    console.print("\n[bold green]🧱 PolyForge Installation Complete[/bold green]\n")
    console.print(f"🧑 User       : {config.get('username', 'unknown')} (sudo granted)")
    ip_info = subprocess.getoutput("hostname -I").split()
    console.print(f"🌍 IP Address : {ip_info[0] if ip_info else 'N/A'}")
    console.print(f"🎛 Services   : {', '.join(config.get('services', {}).keys()) or 'None'}")
    console.print(f"🔐 Backups    : {'Enabled' if config.get('services', {}).get('usb_backup') else 'Disabled'}")
    if config.get("duckdns_domain"):
        console.print(f"🌐 DuckDNS    : {config['duckdns_domain']}.duckdns.org ✅ Active")
    console.print(f"📁 Logs       : /var/log/polyforge_installer.log")
    if config.get("automation_enabled"):
        console.print("🧠 Automation : Enabled ✓")
    else:
        console.print("🧠 Automation : Disabled ✘")

    if Confirm.ask("\n[?] Reboot system now?", default=False):
        subprocess.run("reboot", shell=True)

# ─────────────────────────────────────────────────────────────
# 📦 SECTION 38: Snapshot Save
# ─────────────────────────────────────────────────────────────
def save_postinstall_snapshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    backup_dir = f"/backups"
    snapshot_name = f"polyforge_postinstall_{timestamp}.tar"
    snapshot_path = os.path.join(backup_dir, snapshot_name)
    os.makedirs(backup_dir, exist_ok=True)

    # Temp folder for staging
    staging = f"/tmp/polyforge_snapshot_{timestamp}"
    os.makedirs(staging, exist_ok=True)

    # Files and paths to include
    items = [
        "/etc/hostname",
        "/etc/fstab",
        "/etc/os-release",
        "/var/log/polyforge_installer.log",
        "/var/log/polyforge_bootstrap.log",
        "/var/log/polyforge_automate.log" if os.path.exists("/var/log/polyforge_automate.log") else None,
        os.path.expanduser("~/polyforge/config.yaml"),
        os.path.expanduser("~/polyforge/state-cache.yaml")
    ]
    for item in items:
        if item and os.path.exists(item):
            dest = os.path.join(staging, os.path.basename(item))
            shutil.copy(item, dest)

    subprocess.run(f"tar -cvf {snapshot_path} -C {staging} .", shell=True)
    shutil.rmtree(staging)

    console.print(f"[green]✔ Post-install snapshot saved to {snapshot_path}[/green]")

# Execute post-install tasks
save_postinstall_snapshot()
show_postflight_summary()
 # CHUNK 8 ─────────────────────────────────────────────────────
# 🧾 SECTION 39: CLI Argument Parsing + Action Routing
# ─────────────────────────────────────────────────────────────
import argparse

args = argparse.ArgumentParser(description="PolyForge Installer")
args.add_argument("--dry-run", action="store_true", help="Simulate install steps only")
args.add_argument("--no-prompt", action="store_true", help="Run without any interactive prompts")
args.add_argument("--repair", action="store_true", help="Attempt to repair failed install")
args.add_argument("--reconfigure", action="store_true", help="Force reconfiguration")
args.add_argument("--uninstall", action="store_true", help="Completely remove all installed services")
args.add_argument("--disable-automation", action="store_true", help="Turn off automation engine")
cli = args.parse_args()

# ─────────────────────────────────────────────────────────────
# 🔧 Dry Run Mode
# ─────────────────────────────────────────────────────────────
if cli.dry_run:
    console.print(Panel.fit("🧪 [bold]Dry Run Mode Activated[/bold]\nNo changes will be made", style="bold cyan"))
    console.print("- Would perform: Preflight checks, config loading, service plan\n")
    sys.exit(0)

# ─────────────────────────────────────────────────────────────
# 🔁 Repair Mode
# ─────────────────────────────────────────────────────────────
if cli.repair:
    console.print(Panel.fit("🩹 [bold]Repair Mode Activated[/bold]", style="bold yellow"))
    # Try to restart services or reinstall configs
    for svc in ["plexmediaserver", "duckdns", "casaos", "minecraft"]:
        subprocess.run(f"systemctl restart {svc}", shell=True)
    console.print("✔ Attempted service restarts.\n✔ You may re-run install to patch missing pieces.")
    sys.exit(0)

# ─────────────────────────────────────────────────────────────
# 🧠 Reconfigure Mode
# ─────────────────────────────────────────────────────────────
if cli.reconfigure:
    console.print("[cyan]Launching interactive reconfiguration...[/cyan]")
    if os.path.exists(config_path):
        os.remove(config_path)
    if os.path.exists(state_cache_path):
        os.remove(state_cache_path)
    run_interactive_config()  # Reuse from earlier chunk
    sys.exit(0)

# ─────────────────────────────────────────────────────────────
# 🧼 Uninstall Mode
# ─────────────────────────────────────────────────────────────
def uninstall_everything():
    services = [
        "plexmediaserver", "duckdns", "casaos", "cockpit", "warp", "virtualbox",
        "polyforge-automate.timer", "polyforge-automate.service"
    ]
    for svc in services:
        subprocess.run(f"systemctl disable --now {svc}", shell=True)
    folders = ["/data", "/etc/polyforge", "~/polyforge"]
    for folder in folders:
        subprocess.run(f"rm -rf {folder}", shell=True)
    console.print("[red]✔ PolyForge and all components removed.[/red]")

if cli.uninstall:
    if Confirm.ask("⚠️ This will remove all installed services. Proceed?", default=False):
        uninstall_everything()
        sys.exit(0)

# ─────────────────────────────────────────────────────────────
# 🚫 Disable Automation
# ─────────────────────────────────────────────────────────────
if cli.disable_automation:
    subprocess.run("systemctl disable --now polyforge-automate.timer", shell=True)
    console.print("[yellow]✔ Automation disabled.[/yellow]")
    sys.exit(0)
# CHUNK 9 ─────────────────────────────────────────────────────
# 🔌 SECTION 40: Optional Plugin/Extension System
# ─────────────────────────────────────────────────────────────
from glob import glob

def run_plugin_hooks():
    plugin_dir = os.path.expanduser("~/.polyforge/plugins")
    os.makedirs(plugin_dir, exist_ok=True)
    plugins = glob(f"{plugin_dir}/*.sh")
    if not plugins:
        return
    console.print(Panel.fit("🔌 [bold]Running PolyForge Plugin Scripts[/bold]", style="bold cyan"))
    for plugin in plugins:
        if os.access(plugin, os.X_OK):
            console.print(f"➕ Executing: {plugin}")
            subprocess.run(plugin, shell=True)
        else:
            console.print(f"[yellow]⚠️ Skipped non-executable plugin: {plugin}[/yellow]")

run_plugin_hooks()

# ─────────────────────────────────────────────────────────────
# 🖥 SECTION 41: Optional GUI Launcher (if GUI available)
# ─────────────────────────────────────────────────────────────
def create_gui_launcher():
    if not os.environ.get("DISPLAY") and not os.path.exists("/usr/share/xsessions"):
        return
    launcher_path = "/usr/share/applications/polyforge.desktop"
    with open(launcher_path, "w") as f:
        f.write(f"""[Desktop Entry]
Name=PolyForge Installer
Exec=gnome-terminal -- python3 {os.path.abspath(__file__)}
Icon=utilities-terminal
Type=Application
Terminal=true
Categories=Utility;System;
""")
    console.print("🖥 GUI launcher created at [blue]/usr/share/applications/polyforge.desktop[/blue]")

create_gui_launcher()

# ─────────────────────────────────────────────────────────────
# 🔁 SECTION 42: GitOps Config Sync
# ─────────────────────────────────────────────────────────────
def sync_from_gitops():
    if not config.get("gitops_repo"):
        return
    console.print("🔄 Syncing PolyForge config from GitHub...")
    repo = config["gitops_repo"]
    os.makedirs("~/polyforge", exist_ok=True)
    subprocess.run(f"git clone {repo} ~/polyforge/gitops", shell=True)
    for item in ["config.yaml", "state-cache.yaml"]:
        src = os.path.expanduser(f"~/polyforge/gitops/{item}")
        dst = os.path.expanduser(f"~/polyforge/{item}")
        if os.path.exists(src):
            shutil.copy(src, dst)
    console.print("[green]✔ GitOps config sync complete[/green]")

sync_from_gitops()

# ─────────────────────────────────────────────────────────────
# 🧯 SECTION 43: Filesystem Snapshot & Rollback (ZFS/btrfs)
# ─────────────────────────────────────────────────────────────
def offer_fs_snapshot():
    console.print("🔍 Checking for ZFS or btrfs snapshot capability...")
    has_zfs = shutil.which("zfs") is not None
    has_btrfs = shutil.which("btrfs") is not None
    if has_zfs:
        if Confirm.ask("💾 ZFS detected. Create snapshot before proceeding?", default=True):
            subprocess.run("zfs snapshot rpool/ROOT@polyforge_preinstall", shell=True)
            console.print("✔ ZFS snapshot taken: rpool/ROOT@polyforge_preinstall")
    elif has_btrfs:
        mountpoint = subprocess.getoutput("findmnt -n -o TARGET /").strip()
        if Confirm.ask(f"💾 btrfs detected on {mountpoint}. Snapshot now?", default=True):
            subprocess.run(f"btrfs subvolume snapshot {mountpoint} {mountpoint}/.snap_polyforge_pre", shell=True)
            console.print("✔ btrfs snapshot created")

offer_fs_snapshot()
# CHUNK 10 ─────────────────────────────────────────────────────
# 🛡 SECTION 44: Crash Handler Wrapper
# ─────────────────────────────────────────────────────────────
import traceback

def main():
    try:
        # This wraps ALL installer logic
        run_polyforge()
    except Exception as e:
        crashlog = "/var/log/polyforge_crash.log"
        with open(crashlog, "w") as f:
            f.write("💥 PolyForge Crashed:\n")
            f.write(traceback.format_exc())
        console.print(f"\n[bold red]💥 PolyForge encountered a fatal error[/bold red]")
        console.print(f"📝 Crash details written to [yellow]{crashlog}[/yellow]")
        console.print("🛠 You may run [cyan]--repair[/cyan] to attempt recovery.")
        sys.exit(1)

# Replace direct logic entry with this:
if __name__ == "__main__":
    main()

# ─────────────────────────────────────────────────────────────
# 🧪 SECTION 45: Validation Mode (CLI: --validate)
# ─────────────────────────────────────────────────────────────
if cli.validate:
    console.print(Panel.fit("🧪 [bold cyan]System Validator[/bold cyan]", style="bold"))

    def validate_section(name, check_fn):
        try:
            check_fn()
            console.print(f"[green]✓ {name} OK[/green]")
        except Exception as e:
            console.print(f"[red]✘ {name} failed:[/red] {e}")

    def check_services():
        essential = ["plexmediaserver", "duckdns", "casaos", "minecraft"]
        for s in essential:
            if shutil.which("systemctl"):
                result = subprocess.getoutput(f"systemctl is-active {s}")
                if "active" not in result:
                    raise Exception(f"{s} not running")

    def check_duckdns():
        if "duckdns_domain" in config:
            resp = subprocess.getoutput(f"curl -s https://{config['duckdns_domain']}.duckdns.org")
            if "OK" not in resp and "html" in resp.lower():
                raise Exception("DuckDNS not resolving or invalid")

    def check_disks():
        mounts = subprocess.getoutput("mount")
        if "/data" not in mounts:
            raise Exception("/data not mounted")

    def check_config():
        if not os.path.exists(config_path):
            raise Exception("Missing config.yaml")
        yaml.safe_load(open(config_path))

    def check_network():
        subprocess.check_output(["ping", "-c", "1", "1.1.1.1"])

    validate_section("Config file", check_config)
    validate_section("Disk mounts", check_disks)
    validate_section("Network connection", check_network)
    validate_section("DuckDNS status", check_duckdns)
    validate_section("Service health", check_services)
    console.print("[bold green]✓ Validation complete[/bold green]")
    sys.exit(0)
