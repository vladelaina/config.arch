#!/usr/bin/env python3

import json
import signal
import shutil
import subprocess
import threading
import time
import traceback
import warnings
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("GtkLayerShell", "0.1")

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, GtkLayerShell

warnings.filterwarnings("ignore", category=DeprecationWarning)

BAR_HEIGHT = 24
TOP_OFFSET = 0
SIDE_MARGIN = 8
STATUS_INTERVAL_SECONDS = 10
EXTERNAL_BRIGHTNESS_INTERVAL_SECONDS = 60
COMMAND_TIMEOUT_SECONDS = 2
NIRI_COMMAND_TIMEOUT_SECONDS = 3
POWERPROFILESCTL = "/usr/bin/powerprofilesctl"
BACKLIGHT_DEVICE = "nvidia_0"
BRIGHTNESS_STEP = 5
VOLUME_STEP = 5
DDCUTIL_BUSES = None
TRAY_ICON_SIZE = 16
WORKSPACE_NAMES_PATH = Path.home() / ".config" / "niri-appbar" / "workspaces.json"
SNI_WATCHER_XML = """
<node>
  <interface name="org.kde.StatusNotifierWatcher">
    <method name="RegisterStatusNotifierItem">
      <arg name="service" type="s" direction="in"/>
    </method>
    <method name="RegisterStatusNotifierHost">
      <arg name="service" type="s" direction="in"/>
    </method>
    <property name="RegisteredStatusNotifierItems" type="as" access="read"/>
    <property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
    <property name="ProtocolVersion" type="i" access="read"/>
    <signal name="StatusNotifierItemRegistered">
      <arg name="service" type="s"/>
    </signal>
    <signal name="StatusNotifierItemUnregistered">
      <arg name="service" type="s"/>
    </signal>
    <signal name="StatusNotifierHostRegistered"/>
  </interface>
</node>
"""

APP_ID_MAP = {
    "firefox": "firefox.desktop",
    "org.mozilla.firefox": "firefox.desktop",
    "kitty": "kitty.desktop",
    "org.gnome.Nautilus": "org.gnome.Nautilus.desktop",
    "nautilus": "org.gnome.Nautilus.desktop",
    "code": "code.desktop",
    "Code": "code.desktop",
    "codium": "codium.desktop",
    "VSCodium": "codium.desktop",
    "org.telegram.desktop": "org.telegram.desktop.desktop",
    "obsidian": "obsidian.desktop",
    "clash-verge": "Clash Verge.desktop",
    "clash-verge-service": "Clash Verge.desktop",
    "fcitx": "org.fcitx.Fcitx5.desktop",
    "input method": "org.fcitx.Fcitx5.desktop",
}


def run_niri(*args):
    try:
        return subprocess.check_output(
            ["niri", "msg", *args],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=NIRI_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return ""


def run_niri_json(*args):
    try:
        return json.loads(run_niri("--json", *args))
    except (json.JSONDecodeError, TypeError):
        return None


def choose_output():
    outputs = run_niri_json("outputs") or {}
    return "DP-9" if "DP-9" in outputs else "eDP-2"


def output_position(output_name):
    output = (run_niri_json("outputs") or {}).get(output_name, {})
    logical = output.get("logical")
    if logical:
        return int(logical["x"]), int(logical["y"])
    return None


def output_workspaces(output_name):
    workspaces = run_niri_json("workspaces") or []
    items = [
        {
            "id": int(workspace["id"]),
            "idx": int(workspace["idx"]),
            "active": bool(workspace.get("is_active")),
        }
        for workspace in workspaces
        if workspace.get("output") == output_name
    ]
    return sorted(items, key=lambda workspace: workspace["idx"])


def active_workspace(workspaces):
    for workspace in workspaces:
        if workspace["active"]:
            return workspace
    return None


def current_windows(workspaces):
    workspace = active_workspace(workspaces)
    if not workspace:
        return []
    workspace_id = workspace["id"]

    def sort_key(window):
        position = window.get("layout", {}).get("pos_in_scrolling_layout") or [9999, 9999]
        return (position[0], position[1], window["id"])

    return sorted(
        [window for window in (run_niri_json("windows") or []) if window.get("workspace_id") == workspace_id],
        key=sort_key,
    )


def desktop_app_for(app_id):
    if not isinstance(app_id, str) or not app_id:
        return None
    if app_id in desktop_app_for.cache:
        return desktop_app_for.cache[app_id]
    candidates = []
    mapped = APP_ID_MAP.get(app_id)
    if mapped:
        candidates.append(mapped)
    candidates.extend(
        [
            f"{app_id}.desktop",
            f"{app_id.lower()}.desktop",
            app_id.replace(".", "-") + ".desktop",
        ]
    )
    for candidate in candidates:
        try:
            app = Gio.DesktopAppInfo.new(candidate)
        except TypeError:
            app = None
        if app:
            desktop_app_for.cache[app_id] = app
            return app
    desktop_app_for.cache[app_id] = None
    return None


desktop_app_for.cache = {}


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def write_json(path, value):
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        traceback.print_exc()


def cpu_times():
    parts = read_text("/proc/stat").splitlines()[0].split()[1:]
    values = [int(value) for value in parts]
    idle = values[3] + values[4]
    total = sum(values)
    return idle, total


def memory_percent():
    values = {}
    for line in read_text("/proc/meminfo").splitlines():
        key, value = line.split(":", 1)
        values[key] = int(value.strip().split()[0])
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    if not total:
        return 0
    return round((total - available) * 100 / total)


def battery_text():
    for supply in Path("/sys/class/power_supply").glob("BAT*"):
        capacity = read_text(supply / "capacity")
        status = read_text(supply / "status")
        if not capacity.isdigit():
            continue
        percent = int(capacity)
        if percent >= 99 and status not in {"Charging", "Discharging"}:
            return ""
        if status == "Charging":
            icon = ""
        else:
            icon = ["", "", "", "", ""][min(percent // 25, 4)]
        return f"{percent}% {icon}"
    return ""


def volume_percent():
    try:
        result = subprocess.run(
            ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
            text=True,
            capture_output=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None, False
    if result.returncode != 0:
        return None, False
    parts = result.stdout.strip().split()
    if len(parts) < 2:
        return None, False
    try:
        percent = round(float(parts[1]) * 100)
    except ValueError:
        return None, False
    return percent, "MUTED" in result.stdout


def volume_icon(percent, muted):
    if muted:
        return "󰝟"
    if percent is None:
        return "󰖀"
    if percent <= 0:
        return "󰕿"
    if percent < 20:
        return "󰕿·"
    if percent < 40:
        return "󰖀"
    if percent < 60:
        return "󰖀·"
    if percent < 80:
        return "󰕾"
    return "󰕾·"


def set_volume_percent(percent):
    percent = clamp(round(percent), 0, 100)
    spawn_silent([
        "sh",
        "-c",
        f"wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 && wpctl set-volume @DEFAULT_AUDIO_SINK@ {percent}%",
    ])


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def backlight_percent():
    base = Path("/sys/class/backlight") / BACKLIGHT_DEVICE
    brightness = read_text(base / "brightness")
    max_brightness = read_text(base / "max_brightness")
    if brightness.isdigit() and max_brightness.isdigit() and int(max_brightness) > 0:
        return round(int(brightness) * 100 / int(max_brightness))

    try:
        result = subprocess.run(
            ["brightnessctl", "--device", BACKLIGHT_DEVICE, "info"],
            text=True,
            capture_output=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if "(" not in line or "%)" not in line:
            continue
        try:
            return int(line.split("(", 1)[1].split("%", 1)[0])
        except ValueError:
            return None
    return None


def brightness_icon(percent):
    icons = ["", "", "", "", "", "", "", "", ""]
    if percent is None:
        return ""
    index = clamp(round(percent * (len(icons) - 1) / 100), 0, len(icons) - 1)
    return icons[index]


def set_backlight_percent(percent):
    percent = clamp(round(percent), 1, 100)
    spawn_silent(["brightnessctl", "--quiet", "--device", BACKLIGHT_DEVICE, "set", f"{percent}%"])


def set_external_brightness_percent(percent):
    if not shutil.which("ddcutil"):
        return
    for bus in ddcutil_external_buses():
        spawn_silent([
            "ddcutil",
            "--bus",
            str(bus),
            "--noverify",
            "--skip-ddc-checks",
            "--sleep-multiplier",
            ".1",
            "setvcp",
            "10",
            str(percent),
        ])


def external_brightness_percent():
    global DDCUTIL_BUSES
    buses = ddcutil_external_buses()
    if not buses:
        return None
    try:
        result = subprocess.run(
            [
                "ddcutil",
                "--bus",
                str(buses[0]),
                "--skip-ddc-checks",
                "--sleep-multiplier",
                ".1",
                "getvcp",
                "10",
            ],
            text=True,
            capture_output=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        DDCUTIL_BUSES = None
        return None
    if result.returncode != 0:
        DDCUTIL_BUSES = None
        return None
    for line in result.stdout.splitlines():
        if "current value" not in line:
            continue
        try:
            value = line.split("current value =", 1)[1].split(",", 1)[0].strip()
            return int(value)
        except (IndexError, ValueError):
            return None
    return None


def ddcutil_external_buses():
    global DDCUTIL_BUSES
    if DDCUTIL_BUSES is not None:
        return DDCUTIL_BUSES

    try:
        result = subprocess.run(
            ["ddcutil", "detect", "--brief"],
            text=True,
            capture_output=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if result.returncode != 0:
        return []

    buses = []
    current_bus = None
    current_connector = ""
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("Display "):
            if current_bus is not None and current_connector and "-eDP-" not in current_connector:
                buses.append(current_bus)
            current_bus = None
            current_connector = ""
        elif line.startswith("I2C bus:"):
            bus_path = line.split(":", 1)[1].strip()
            try:
                current_bus = int(bus_path.rsplit("-", 1)[1])
            except (IndexError, ValueError):
                current_bus = None
        elif line.startswith("DRM connector:"):
            current_connector = line.split(":", 1)[1].strip()
        elif line.startswith("Invalid display"):
            if current_bus is not None and current_connector and "-eDP-" not in current_connector:
                buses.append(current_bus)
            current_bus = None
            current_connector = ""

    if current_bus is not None and current_connector and "-eDP-" not in current_connector:
        buses.append(current_bus)
    DDCUTIL_BUSES = buses
    return DDCUTIL_BUSES


def network_text():
    iface = ""
    for line in read_text("/proc/net/route").splitlines()[1:]:
        fields = line.split()
        if len(fields) > 1 and fields[1] == "00000000":
            iface = fields[0]
            break
    if not iface:
        return "󰤭 offline"
    if iface.startswith(("wl", "wifi")):
        return "󰤨"
    return "󰈀 wired"


def wifi_enabled():
    nmcli = shutil.which("nmcli")
    if not nmcli:
        return None
    try:
        result = subprocess.run(
            [nmcli, "radio", "wifi"],
            text=True,
            capture_output=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    state = result.stdout.strip().lower()
    if state == "enabled":
        return True
    if state == "disabled":
        return False
    return None


def set_wifi_enabled(enabled):
    nmcli = shutil.which("nmcli")
    if nmcli:
        spawn_silent([nmcli, "radio", "wifi", "on" if enabled else "off"])


def open_network_manager():
    editor = shutil.which("nm-connection-editor")
    if editor:
        spawn_silent([editor])
        return

    nmtui = shutil.which("nmtui")
    kitty = shutil.which("kitty")
    if nmtui and kitty:
        spawn_silent([kitty, "--class", "nmtui-network", "-e", nmtui])
        return

    if nmtui:
        spawn_silent([nmtui])


def variant_unpacked(value):
    if isinstance(value, GLib.Variant):
        return value.unpack()
    return value


def bluetooth_objects():
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        result = connection.call_sync(
            "org.bluez",
            "/",
            "org.freedesktop.DBus.ObjectManager",
            "GetManagedObjects",
            None,
            GLib.VariantType.new("(a{oa{sa{sv}}})"),
            Gio.DBusCallFlags.NONE,
            500,
            None,
        )
    except Exception:
        return None
    return result.unpack()[0]


def bluetooth_state():
    objects = bluetooth_objects()
    if not objects:
        return None

    adapters = []
    connected = 0
    for path, interfaces in objects.items():
        adapter = interfaces.get("org.bluez.Adapter1")
        if adapter is not None:
            adapters.append(
                {
                    "path": path,
                    "powered": bool(variant_unpacked(adapter.get("Powered", False))),
                }
            )

        device = interfaces.get("org.bluez.Device1")
        if device is not None and bool(variant_unpacked(device.get("Connected", False))):
            connected += 1

    if not adapters:
        return None

    powered = any(adapter["powered"] for adapter in adapters)
    if not powered:
        return {"text": "󰂲", "powered": False, "connected": 0, "adapters": adapters}
    if connected:
        return {"text": "󰂱", "powered": True, "connected": connected, "adapters": adapters}
    return {"text": "󰂯", "powered": True, "connected": 0, "adapters": adapters}


def set_bluetooth_power(powered):
    objects = bluetooth_objects()
    if not objects:
        return
    try:
        connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        for path, interfaces in objects.items():
            if "org.bluez.Adapter1" not in interfaces:
                continue
            connection.call_sync(
                "org.bluez",
                path,
                "org.freedesktop.DBus.Properties",
                "Set",
                GLib.Variant(
                    "(ssv)",
                    ("org.bluez.Adapter1", "Powered", GLib.Variant("b", powered)),
                ),
                None,
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
    except Exception:
        traceback.print_exc()


def open_bluetooth_manager():
    for command in ("blueman-manager", "overskride", "blueberry"):
        path = shutil.which(command)
        if path:
            spawn_silent([path])
            return
    control_center = shutil.which("gnome-control-center")
    if control_center:
        spawn_silent([control_center, "bluetooth"])


def bluetooth_manager_windows():
    windows = run_niri_json("windows") or []
    matches = []
    for window in windows:
        app_id = str(window.get("app_id", "")).lower()
        title = str(window.get("title", "")).lower()
        if (
            app_id.startswith("blueman")
            or app_id in {"overskride", "blueberry", "org.gnome.controlcenter"}
            or "bluetooth" in title
        ):
            matches.append(window)
    matches.sort(
        key=lambda window: (
            bool(window.get("is_focused")),
            window.get("focus_timestamp", {}).get("secs", 0),
            window.get("focus_timestamp", {}).get("nanos", 0),
        ),
        reverse=True,
    )
    return matches


def toggle_bluetooth_manager():
    windows = bluetooth_manager_windows()
    if windows:
        window_id = windows[0].get("id")
        if window_id is not None:
            spawn_silent(["niri", "msg", "action", "close-window", "--id", str(window_id)])
            return
    open_bluetooth_manager()


def spawn_silent(command):
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def power_profile():
    try:
        result = subprocess.run(
            [POWERPROFILESCTL, "get"],
            text=True,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
        profile = result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        profile = ""
    icons = {
        "performance": "",
        "balanced": "",
        "power-saver": "",
    }
    return profile, icons.get(profile, "")


def variant_value(proxy, name):
    value = proxy.get_cached_property(name)
    if value is not None:
        return value.unpack()
    try:
        value = proxy.call_sync(
            "org.freedesktop.DBus.Properties.Get",
            GLib.Variant("(ss)", ("org.kde.StatusNotifierItem", name)),
            Gio.DBusCallFlags.NONE,
            500,
            None,
        )
        return value.unpack()[0].unpack()
    except Exception:
        return None


def pixbuf_from_sni_pixmap(pixmaps):
    if not pixmaps:
        return None
    width, height, data = min(
        pixmaps,
        key=lambda item: abs(item[0] - TRAY_ICON_SIZE) + abs(item[1] - TRAY_ICON_SIZE),
    )
    raw = bytes(data)
    if width <= 0 or height <= 0 or len(raw) < width * height * 4:
        return None

    rgba = bytearray(width * height * 4)
    for index in range(width * height):
        src = index * 4
        alpha, red, green, blue = raw[src : src + 4]
        rgba[src : src + 4] = bytes((red, green, blue, alpha))

    pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(bytes(rgba)),
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        width,
        height,
        width * 4,
    )
    if width == TRAY_ICON_SIZE and height == TRAY_ICON_SIZE:
        return pixbuf
    return pixbuf.scale_simple(TRAY_ICON_SIZE, TRAY_ICON_SIZE, GdkPixbuf.InterpType.BILINEAR)


def pixbuf_from_icon_name(icon_name):
    if not icon_name:
        return None
    if icon_name.startswith("/") and Path(icon_name).exists():
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(
                icon_name,
                TRAY_ICON_SIZE,
                TRAY_ICON_SIZE,
                True,
            )
        except Exception:
            return None
    return None


def unpack_value(value):
    return value.unpack() if hasattr(value, "unpack") else value


def unpack_layout_child(child):
    return child.unpack() if hasattr(child, "unpack") else child


def dbus_methods(connection, bus_name, object_path, interface_name):
    try:
        xml = connection.call_sync(
            bus_name,
            object_path,
            "org.freedesktop.DBus.Introspectable",
            "Introspect",
            None,
            GLib.VariantType.new("(s)"),
            Gio.DBusCallFlags.NONE,
            500,
            None,
        ).unpack()[0]
    except Exception:
        return set()

    marker = f'interface name="{interface_name}"'
    if marker not in xml:
        return set()
    methods = set()
    for line in xml.splitlines():
        line = line.strip()
        if line.startswith("<method name="):
            methods.add(line.split('"')[1])
    return methods


class StatusNotifierItem:
    def __init__(self, watcher, bus_name, object_path):
        self.watcher = watcher
        self.bus_name = bus_name
        self.object_path = object_path
        self.key = f"{bus_name}{object_path}"
        self.proxy = Gio.DBusProxy.new_sync(
            watcher.connection,
            Gio.DBusProxyFlags.NONE,
            None,
            bus_name,
            object_path,
            "org.kde.StatusNotifierItem",
            None,
        )
        self.methods = dbus_methods(
            watcher.connection,
            bus_name,
            object_path,
            "org.kde.StatusNotifierItem",
        )
        self.menu_path = None
        self.menu_proxy = None
        self.open_menu = None
        self.title = ""
        self.item_id = ""
        self.desktop_entry = ""
        self.widget = Gtk.Button()
        self.widget.set_can_focus(False)
        self.widget.set_focus_on_click(False)
        self.widget.set_relief(Gtk.ReliefStyle.NONE)
        self.widget.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.widget.get_style_context().add_class("tray-item")
        self.image = Gtk.Image()
        self.image.set_pixel_size(TRAY_ICON_SIZE)
        self.widget.add(self.image)
        self.widget.connect("button-press-event", self.button_pressed)
        self.signal_ids = [
            watcher.connection.signal_subscribe(
                bus_name,
                "org.kde.StatusNotifierItem",
                None,
                object_path,
                None,
                Gio.DBusSignalFlags.NONE,
                self.item_signal,
            ),
            watcher.connection.signal_subscribe(
                bus_name,
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                object_path,
                "org.kde.StatusNotifierItem",
                Gio.DBusSignalFlags.NONE,
                self.item_signal,
            ),
        ]
        self.refresh()

    def destroy(self):
        for signal_id in self.signal_ids:
            self.watcher.connection.signal_unsubscribe(signal_id)
        self.widget.destroy()

    def item_signal(self, *_args):
        GLib.idle_add(self.refresh)

    def refresh(self):
        try:
            if variant_value(self.proxy, "Status") == "Passive":
                self.widget.hide()
                return False

            icon_name = variant_value(self.proxy, "IconName")
            pixmaps = variant_value(self.proxy, "IconPixmap")
            self.menu_path = variant_value(self.proxy, "Menu")
            self.title = str(variant_value(self.proxy, "Title") or "")
            self.item_id = str(variant_value(self.proxy, "Id") or "")
            self.desktop_entry = str(variant_value(self.proxy, "DesktopEntry") or "")
            pixbuf = pixbuf_from_sni_pixmap(pixmaps)
            if pixbuf:
                self.image.set_from_pixbuf(pixbuf)
            elif icon_name:
                icon_pixbuf = pixbuf_from_icon_name(icon_name)
                if icon_pixbuf:
                    self.image.set_from_pixbuf(icon_pixbuf)
                else:
                    self.image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
                self.image.set_pixel_size(TRAY_ICON_SIZE)
            else:
                self.set_fallback_icon()

            self.widget.show_all()
        except Exception:
            traceback.print_exc()
        return False

    def set_fallback_icon(self):
        for app_id in (self.item_id, self.title, self.item_id.lower(), self.title.lower()):
            app = desktop_app_for(app_id)
            if app and app.get_icon():
                self.image.set_from_gicon(app.get_icon(), Gtk.IconSize.MENU)
                self.image.set_pixel_size(TRAY_ICON_SIZE)
                return
        self.image.set_from_icon_name("application-x-executable", Gtk.IconSize.MENU)
        self.image.set_pixel_size(TRAY_ICON_SIZE)

    def call_item(self, method_name, event):
        x, y = self.event_position(event)
        self.proxy.call(
            method_name,
            GLib.Variant("(ii)", (x, y)),
            Gio.DBusCallFlags.NONE,
            1000,
            None,
            self.call_item_finished,
            method_name,
        )

    def event_position(self, event):
        output_x, output_y = output_position(self.watcher.appbar.output_name) or (0, 0)
        allocation = self.widget.get_allocation()
        translated = self.widget.translate_coordinates(
            self.watcher.appbar,
            allocation.width // 2,
            allocation.height // 2,
        )
        if translated:
            local_x, local_y = translated
            return output_x + int(local_x), output_y + int(local_y)

        x = int(getattr(event, "x_root", 0) or 0)
        y = int(getattr(event, "y_root", 0) or 0)
        return output_x + x, output_y + y

    def call_item_finished(self, proxy, result, method_name):
        try:
            proxy.call_finish(result)
        except Exception as error:
            print(f"niri-appbar: tray {method_name} failed for {self.key}: {error}", flush=True)

    def candidate_app_ids(self):
        candidates = []
        for value in (self.desktop_entry, self.item_id, self.title):
            value = str(value or "").strip()
            if not value:
                continue
            candidates.append(value)
            if value.endswith(".desktop"):
                candidates.append(value[:-8])
            mapped = APP_ID_MAP.get(value) or APP_ID_MAP.get(value.lower())
            if mapped:
                candidates.append(mapped)
                if mapped.endswith(".desktop"):
                    candidates.append(mapped[:-8])

        bus_tail = self.bus_name.rsplit(".", 1)[-1]
        if bus_tail and not bus_tail.isdigit():
            candidates.append(bus_tail)

        normalized = []
        seen = set()
        for candidate in candidates:
            candidate = candidate.strip().lower()
            if not candidate:
                continue
            for prefix in ("org.", "com.", "net.", "io."):
                if candidate.startswith(prefix):
                    normalized.append(candidate)
                    break
            normalized.append(candidate)
            if "-" in candidate:
                normalized.append(candidate.replace("-", "_"))
            if "_" in candidate:
                normalized.append(candidate.replace("_", "-"))

        result = []
        for candidate in normalized:
            if candidate and candidate not in seen:
                seen.add(candidate)
                result.append(candidate)
        return result

    def focus_existing_window(self):
        candidates = self.candidate_app_ids()
        if not candidates:
            return False

        windows = run_niri_json("windows") or []
        matched = []
        for window in windows:
            app_id = str(window.get("app_id", "")).lower()
            title = str(window.get("title", "")).lower()
            for candidate in candidates:
                if (
                    app_id == candidate
                    or app_id.endswith(f".{candidate}")
                    or candidate in app_id
                    or (len(candidate) >= 4 and candidate in title)
                ):
                    matched.append(window)
                    break

        if not matched:
            return False

        matched.sort(
            key=lambda window: (
                bool(window.get("is_focused")),
                window.get("focus_timestamp", {}).get("secs", 0),
                window.get("focus_timestamp", {}).get("nanos", 0),
            ),
            reverse=True,
        )
        window_id = matched[0].get("id")
        if window_id is None:
            return False
        spawn_silent(["niri", "msg", "action", "focus-window", "--id", str(window_id)])
        return True

    def button_pressed(self, _widget, event):
        # Stop GTK from treating the following release as a separate click target.
        return self.activate_button(event)

    def activate_button(self, event):
        try:
            if event.button == 1:
                if self.focus_existing_window():
                    return True
                if "Activate" in self.methods and not variant_value(self.proxy, "ItemIsMenu"):
                    self.call_item("Activate", event)
                return True
            if event.button == 2:
                if "SecondaryActivate" in self.methods:
                    self.call_item("SecondaryActivate", event)
                return True
            if event.button == 3:
                if self.menu_path:
                    self.show_dbus_menu(event)
                elif "ContextMenu" in self.methods:
                    self.call_item("ContextMenu", event)
                return True
        except Exception:
            traceback.print_exc()
        return False

    def dbus_menu_proxy(self):
        if not self.menu_path:
            return None
        if self.menu_proxy is None:
            self.menu_proxy = Gio.DBusProxy.new_sync(
                self.watcher.connection,
                Gio.DBusProxyFlags.NONE,
                None,
                self.bus_name,
                self.menu_path,
                "com.canonical.dbusmenu",
                None,
            )
        return self.menu_proxy

    def show_dbus_menu(self, event):
        proxy = self.dbus_menu_proxy()
        if proxy is None:
            return
        try:
            self.close_open_menu()
            proxy.call_sync(
                "AboutToShow",
                GLib.Variant("(i)", (0,)),
                Gio.DBusCallFlags.NONE,
                500,
                None,
            )
            result = proxy.call_sync(
                "GetLayout",
                GLib.Variant("(iias)", (0, -1, [])),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            _revision, root = result.unpack()
            menu = self.build_menu(root)
            if not menu.get_children():
                return
            self.open_menu = menu
            menu.connect("deactivate", self.menu_deactivated)
            menu.show_all()
            menu.popup_at_pointer(event)
        except Exception:
            traceback.print_exc()

    def build_menu(self, layout):
        menu = Gtk.Menu()
        _item_id, _props, children = layout
        for child_variant in children:
            child = unpack_layout_child(child_variant)
            item = self.menu_item_from_layout(child)
            if item:
                menu.append(item)
        return menu

    def menu_item_from_layout(self, layout):
        item_id, props, children = layout
        visible = props.get("visible")
        if visible is not None and not unpack_value(visible):
            return None

        item_type = props.get("type")
        if item_type is not None and unpack_value(item_type) == "separator":
            return Gtk.SeparatorMenuItem()

        label = props.get("label")
        label_text = str(unpack_value(label)) if label is not None else ""
        label_text = label_text.replace("_", "__")
        item = Gtk.MenuItem(label=label_text or " ")

        enabled = props.get("enabled")
        if enabled is not None:
            item.set_sensitive(bool(unpack_value(enabled)))

        if children:
            submenu = Gtk.Menu()
            for child_variant in children:
                child = unpack_layout_child(child_variant)
                child_item = self.menu_item_from_layout(child)
                if child_item:
                    submenu.append(child_item)
            if submenu.get_children():
                item.set_submenu(submenu)
        else:
            item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
            item.connect("button-release-event", self.menu_item_released, item_id, label_text)

        return item

    def menu_item_released(self, item, event, item_id, label_text):
        if event.button != 1:
            return False
        self.activate_menu_item(item, item_id, label_text)
        return True

    def activate_menu_item(self, _item, item_id, label_text):
        proxy = self.dbus_menu_proxy()
        if proxy is None:
            return
        timestamp = int(time.time() * 1000) & 0xFFFFFFFF
        self.close_open_menu()
        proxy.call(
            "Event",
            GLib.Variant("(isvu)", (int(item_id), "clicked", GLib.Variant("i", 0), timestamp)),
            Gio.DBusCallFlags.NONE,
            1000,
            None,
            self.menu_event_finished,
            (item_id, label_text),
        )

    def menu_event_finished(self, proxy, result, item_info):
        item_id, label_text = item_info
        try:
            proxy.call_finish(result)
        except Exception as error:
            print(
                f"niri-appbar: menu event failed {self.key} id={item_id} label={label_text}: {error}",
                flush=True,
            )

    def close_open_menu(self):
        if self.open_menu is None:
            return
        menu = self.open_menu
        self.open_menu = None
        menu.popdown()
        GLib.idle_add(menu.destroy)

    def menu_deactivated(self, menu):
        if self.open_menu is menu:
            self.open_menu = None
            menu.destroy()


class StatusNotifierWatcher:
    def __init__(self, appbar):
        self.appbar = appbar
        self.items = {}
        self.hosts = set()
        self.node_info = Gio.DBusNodeInfo.new_for_xml(SNI_WATCHER_XML)
        self.interface_info = self.node_info.interfaces[0]
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.registration_id = self.connection.register_object(
            "/StatusNotifierWatcher",
            self.interface_info,
            self.method_call,
            self.get_property,
            None,
        )
        self.owner_id = Gio.bus_own_name_on_connection(
            self.connection,
            "org.kde.StatusNotifierWatcher",
            Gio.BusNameOwnerFlags.NONE,
            self.name_acquired,
            self.name_lost,
        )
        self.name_owner_signal_id = self.connection.signal_subscribe(
            "org.freedesktop.DBus",
            "org.freedesktop.DBus",
            "NameOwnerChanged",
            "/org/freedesktop/DBus",
            None,
            Gio.DBusSignalFlags.NONE,
            self.name_owner_changed,
        )
        self.discover_existing_items()

    def name_acquired(self, *_args):
        self.connection.emit_signal(
            None,
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            "StatusNotifierHostRegistered",
            None,
        )

    def name_lost(self, *_args):
        print("niri-appbar: could not own org.kde.StatusNotifierWatcher")

    def registered_services(self):
        return sorted(item.key for item in self.items.values())

    def get_property(self, _connection, _sender, _object_path, _interface_name, property_name):
        if property_name == "RegisteredStatusNotifierItems":
            return GLib.Variant("as", self.registered_services())
        if property_name == "IsStatusNotifierHostRegistered":
            return GLib.Variant("b", True)
        if property_name == "ProtocolVersion":
            return GLib.Variant("i", 0)
        return None

    def method_call(
        self,
        _connection,
        sender,
        _object_path,
        _interface_name,
        method_name,
        parameters,
        invocation,
    ):
        try:
            service = parameters.unpack()[0]
            if method_name == "RegisterStatusNotifierItem":
                self.register_item(service, sender)
                invocation.return_value(GLib.Variant("()", ()))
                return
            if method_name == "RegisterStatusNotifierHost":
                self.hosts.add(service or sender)
                invocation.return_value(GLib.Variant("()", ()))
                return
        except Exception:
            traceback.print_exc()
        invocation.return_dbus_error(
            "org.kde.StatusNotifierWatcher.Error.Failed",
            f"Unsupported method {method_name}",
        )

    def register_item(self, service, sender=None):
        bus_name = sender if service.startswith("/") else service
        object_path = service if service.startswith("/") else "/StatusNotifierItem"
        if not bus_name:
            return
        key = f"{bus_name}{object_path}"
        if key in self.items:
            return
        try:
            item = StatusNotifierItem(self, bus_name, object_path)
        except Exception:
            traceback.print_exc()
            return
        self.items[key] = item
        self.appbar.add_tray_item(item)
        self.connection.emit_signal(
            None,
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            "StatusNotifierItemRegistered",
            GLib.Variant("(s)", (key,)),
        )

    def remove_item(self, key):
        item = self.items.pop(key, None)
        if not item:
            return
        self.appbar.remove_tray_item(item)
        item.destroy()
        self.connection.emit_signal(
            None,
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            "StatusNotifierItemUnregistered",
            GLib.Variant("(s)", (key,)),
        )

    def name_owner_changed(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        _signal_name,
        parameters,
        _user_data=None,
    ):
        name, _old_owner, new_owner = parameters.unpack()
        if new_owner:
            return
        for key, item in list(self.items.items()):
            if item.bus_name == name:
                self.remove_item(key)

    def discover_existing_items(self):
        try:
            result = self.connection.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ListNames",
                None,
                GLib.VariantType.new("(as)"),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            for name in result.unpack()[0]:
                if name.startswith("org.kde.StatusNotifierItem-"):
                    self.register_item(name)
        except Exception:
            traceback.print_exc()


class AppBar(Gtk.Window):
    def __init__(self):
        super().__init__(title="niri-appbar")
        self.output_name = choose_output()
        self.prev_cpu = None
        self.brightness_percent = backlight_percent()
        self.external_brightness_percent = None
        self.external_brightness_available = False
        self.external_brightness_apply_source = 0
        self.volume_percent, self.volume_muted = volume_percent()
        self.bluetooth_state = bluetooth_state()
        self.power_profile_cache = ("balanced", "")
        self.workspace_names = read_json(WORKSPACE_NAMES_PATH, {})
        self.workspace_rename_window = None
        self.update_queued = False
        self.tray_expanded = False
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_app_paintable(True)
        self.set_accept_focus(False)
        self.set_focus_on_map(False)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_namespace(self, "niri-appbar")
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, TOP_OFFSET)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, SIDE_MARGIN)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, SIDE_MARGIN)
        GtkLayerShell.set_exclusive_zone(self, BAR_HEIGHT + TOP_OFFSET)
        self.set_size_request(-1, BAR_HEIGHT)

        self.apply_monitor()

        self.root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.root.set_size_request(-1, BAR_HEIGHT)
        self.root.get_style_context().add_class("appbar")
        self.add(self.root)

        self.left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.left_box.set_valign(Gtk.Align.CENTER)
        self.right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.right_box.set_valign(Gtk.Align.CENTER)
        self.tray_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tray_box.set_valign(Gtk.Align.CENTER)
        self.tray_items_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.tray_items_box.set_valign(Gtk.Align.CENTER)
        self.tray_revealer = Gtk.Revealer()
        self.tray_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.tray_revealer.set_transition_duration(160)
        self.tray_revealer.set_reveal_child(False)
        self.tray_revealer.add(self.tray_items_box)
        self.tray_toggle = Gtk.Button(label="<")
        self.tray_toggle.set_can_focus(False)
        self.tray_toggle.set_focus_on_click(False)
        self.tray_toggle.set_relief(Gtk.ReliefStyle.NONE)
        self.tray_toggle.set_no_show_all(True)
        self.tray_toggle.get_style_context().add_class("tray-toggle")
        self.tray_toggle.connect("clicked", self.toggle_tray)
        self.tray_box.pack_start(self.tray_revealer, False, False, 0)
        self.tray_box.pack_start(self.tray_toggle, False, False, 0)
        self.status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.status_box.set_valign(Gtk.Align.CENTER)
        self.root.pack_start(self.left_box, False, False, 0)
        self.root.pack_start(Gtk.Box(), True, True, 0)
        self.root.pack_end(self.right_box, False, False, 0)
        self.right_box.pack_start(self.tray_box, False, False, 0)
        self.right_box.pack_start(self.status_box, False, False, 0)

        css = b"""
        window {
            background: transparent;
        }
        .appbar {
            background: transparent;
            min-height: 24px;
        }
        .appbar label,
        .appbar button,
        .appbar image {
            color: #a4e1a0;
        }
        .workspace-item,
        .app-item,
        .tray-item,
        .status-item {
            background: transparent;
            margin: 0;
            padding: 0;
            min-height: 24px;
        }
        .workspace-label,
        .status-label {
            color: #a4e1a0;
            font-family: Cantarell, "Font Awesome 6 Free", "JetBrainsMono Nerd Font", "Symbols Nerd Font", "Noto Sans CJK SC", sans-serif;
            font-size: 14px;
            padding: 0 2px;
            margin: 0;
        }
        .status-button {
            all: unset;
            background: transparent;
            border: none;
            box-shadow: none;
            color: #a4e1a0;
            font-family: Cantarell, "Font Awesome 6 Free", "JetBrainsMono Nerd Font", "Symbols Nerd Font", "Noto Sans CJK SC", sans-serif;
            font-size: 14px;
            padding: 0 2px;
            margin: 0;
            min-height: 24px;
        }
        .tray-item {
            background: transparent;
            border: none;
            box-shadow: none;
            padding: 0 2px;
            margin: 0;
            min-height: 24px;
            min-width: 20px;
        }
        .tray-toggle {
            all: unset;
            background: transparent;
            border: none;
            box-shadow: none;
            color: #a4e1a0;
            font-family: Cantarell, "Font Awesome 6 Free", "JetBrainsMono Nerd Font", "Symbols Nerd Font", "Noto Sans CJK SC", sans-serif;
            font-size: 14px;
            padding: 0 2px;
            margin: 0;
            min-height: 24px;
            min-width: 12px;
        }
        .tray-item:hover,
        .tray-item:active,
        .tray-item:checked,
        .tray-toggle:hover,
        .tray-toggle:active,
        .tray-toggle:checked {
            background: transparent;
            border: none;
            box-shadow: none;
        }
        .cpu-label,
        .memory-label {
            min-width: 48px;
        }
        .volume-label {
            min-width: 24px;
        }
        .workspace-label {
            padding: 0 5px;
        }
        .workspace-name-entry {
            background: rgba(20, 20, 20, 0.92);
            color: #a4e1a0;
            border: 1px solid rgba(255, 255, 255, 0.35);
            border-radius: 6px;
            padding: 5px 8px;
            font-family: Cantarell, "Noto Sans CJK SC", sans-serif;
            font-size: 14px;
            min-width: 180px;
        }
        .workspace-active .workspace-label {
            font-weight: 900;
            font-size: 17px;
        }
        .app-item {
            margin-left: 3px;
            padding: 0 3px;
        }
        .app-stack {
            margin: 0;
            padding: 0;
        }
        .app-underline {
            min-height: 2px;
            margin: 1px 1px 0 1px;
            background-color: transparent;
        }
        .app-underline-active {
            background-color: #a4e1a0;
        }
        image {
            margin: 0;
            padding: 0;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.update()
        self.update_status_safe()
        self.tray_watcher = StatusNotifierWatcher(self)
        self.show_all()
        threading.Thread(target=self.watch_niri, daemon=True).start()
        threading.Thread(target=self.refresh_power_profile, daemon=True).start()
        threading.Thread(target=self.watch_external_brightness, daemon=True).start()
        GLib.timeout_add_seconds(STATUS_INTERVAL_SECONDS, self.update_status_safe)

    def apply_monitor(self):
        position = output_position(self.output_name)
        if position is None:
            return
        display = Gdk.Display.get_default()
        for index in range(display.get_n_monitors()):
            monitor = display.get_monitor(index)
            geometry = monitor.get_geometry()
            if (geometry.x, geometry.y) == position:
                GtkLayerShell.set_monitor(self, monitor)
                return

    def clear(self):
        for child in list(self.left_box.get_children()):
            self.left_box.remove(child)

    def clear_status(self):
        for child in list(self.status_box.get_children()):
            self.status_box.remove(child)

    def add_tray_item(self, item):
        self.tray_items_box.pack_end(item.widget, False, False, 0)
        self.tray_toggle.show()
        self.tray_revealer.show()
        item.widget.show_all()
        self.tray_items_box.show_all()
        self.tray_revealer.show_all()
        self.tray_box.show_all()
        self.update_tray_visibility()

    def remove_tray_item(self, item):
        if item.widget.get_parent() == self.tray_items_box:
            self.tray_items_box.remove(item.widget)
        self.update_tray_visibility()

    def toggle_tray(self, _button):
        self.tray_expanded = not self.tray_expanded
        self.tray_revealer.set_reveal_child(self.tray_expanded)
        self.tray_toggle.set_label(">" if self.tray_expanded else "<")
        if self.tray_expanded:
            self.tray_items_box.show_all()
            self.tray_revealer.show_all()

    def update_tray_visibility(self):
        has_items = bool(self.tray_items_box.get_children())
        self.tray_toggle.set_visible(has_items)
        self.tray_revealer.set_visible(has_items)
        if has_items:
            self.tray_toggle.show()
            self.tray_revealer.show()
        if not has_items:
            self.tray_expanded = False
            self.tray_revealer.set_reveal_child(False)
            self.tray_toggle.set_label("<")

    def update(self):
        try:
            self.output_name = choose_output()
            self.apply_monitor()
            self.clear()

            workspaces = output_workspaces(self.output_name)
            for workspace in workspaces:
                number = workspace["idx"]
                label_text = self.workspace_label(number)
                item = Gtk.EventBox()
                item.set_can_focus(False)
                item.set_visible_window(False)
                item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
                item.get_style_context().add_class("workspace-item")
                label = Gtk.Label(label=label_text)
                label.get_style_context().add_class("workspace-label")
                label.set_yalign(0.0)
                label.set_valign(Gtk.Align.START)
                item.add(label)
                if workspace["active"]:
                    item.get_style_context().add_class("workspace-active")
                item.connect("button-press-event", self.workspace_button_pressed, number)
                item.connect("scroll-event", self.scroll_workspace)
                self.left_box.pack_start(item, False, False, 0)

            for window in current_windows(workspaces):
                item = Gtk.EventBox()
                item.set_can_focus(False)
                item.set_visible_window(False)
                item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
                item.get_style_context().add_class("app-item")
                stack = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                stack.get_style_context().add_class("app-stack")
                image = self.image_for_app(window.get("app_id"))
                image.set_valign(Gtk.Align.START)
                underline = Gtk.Box()
                underline.get_style_context().add_class("app-underline")
                if window.get("is_focused"):
                    underline.get_style_context().add_class("app-underline-active")
                stack.pack_start(image, False, False, 0)
                stack.pack_start(underline, False, False, 0)
                item.add(stack)
                item.connect("button-release-event", self.app_button_released, window["id"])
                self.left_box.pack_start(item, False, False, 0)

            self.show_all()
            self.update_tray_visibility()
        except Exception:
            traceback.print_exc()
        finally:
            self.update_queued = False
        return False

    def queue_update(self):
        if self.update_queued:
            return False
        self.update_queued = True
        GLib.timeout_add(30, self.update)
        return False

    def status_item(self, text, callback=None, css_class=None):
        if callback:
            button = Gtk.Button(label=text)
            button.set_can_focus(False)
            button.set_focus_on_click(False)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.get_style_context().add_class("status-button")
            if css_class:
                button.get_style_context().add_class(css_class)
            button.connect("clicked", callback)
            return button

        item = Gtk.EventBox()
        item.set_can_focus(False)
        item.set_visible_window(False)
        item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        item.get_style_context().add_class("status-item")
        label = Gtk.Label(label=text)
        label.get_style_context().add_class("status-label")
        if css_class:
            label.get_style_context().add_class(css_class)
        item.add(label)
        if callback:
            item.connect("button-press-event", callback)
        return item

    def brightness_item(self, target):
        text = brightness_icon(self.brightness_value(target))
        item = Gtk.EventBox()
        item.set_can_focus(False)
        item.set_visible_window(False)
        item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        item.get_style_context().add_class("status-item")
        label = Gtk.Label(label=text)
        label.get_style_context().add_class("status-label")
        item.add(label)
        item.connect("button-press-event", self.brightness_button_pressed, target)
        item.connect("scroll-event", self.brightness_scrolled, target)
        return item

    def brightness_value(self, target):
        if target == "external":
            return self.external_brightness_percent
        return self.brightness_percent

    def volume_item(self):
        item = Gtk.EventBox()
        item.set_can_focus(False)
        item.set_visible_window(False)
        item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.SCROLL_MASK)
        item.get_style_context().add_class("status-item")
        label = Gtk.Label(label=volume_icon(self.volume_percent, self.volume_muted))
        label.get_style_context().add_class("status-label")
        label.get_style_context().add_class("volume-label")
        label.set_xalign(0.5)
        item.add(label)
        item.connect("button-press-event", self.volume_button_pressed)
        item.connect("scroll-event", self.volume_scrolled)
        return item

    def bluetooth_item(self):
        item = Gtk.EventBox()
        item.set_can_focus(False)
        item.set_visible_window(False)
        item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        item.get_style_context().add_class("status-item")
        label = Gtk.Label(label=self.bluetooth_state["text"])
        label.get_style_context().add_class("status-label")
        item.add(label)
        item.connect("button-press-event", self.bluetooth_button_pressed)
        return item

    def network_item(self, text):
        item = Gtk.EventBox()
        item.set_can_focus(False)
        item.set_visible_window(False)
        item.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        item.get_style_context().add_class("status-item")
        label = Gtk.Label(label=text)
        label.get_style_context().add_class("status-label")
        item.add(label)
        item.connect("button-press-event", self.network_button_pressed)
        return item

    def update_status(self):
        self.clear_status()
        items = []
        self.brightness_percent = backlight_percent()
        self.volume_percent, self.volume_muted = volume_percent()
        self.bluetooth_state = bluetooth_state()
        network = network_text()
        if network:
            items.append(self.network_item(network))
        if self.bluetooth_state:
            items.append(self.bluetooth_item())
        if self.brightness_percent is not None:
            items.append(self.brightness_item("internal"))
        if self.external_brightness_available:
            items.append(self.brightness_item("external"))
        if self.volume_percent is not None:
            items.append(self.volume_item())
        if shutil.which("hyprpicker"):
            items.append(self.status_item("", self.color_picker_button_pressed))
        _profile, power_icon = self.power_profile_cache
        items.append(self.status_item(power_icon, self.power_button_pressed))
        items.append(self.status_item(f"{self.cpu_percent()}% ", css_class="cpu-label"))
        items.append(self.status_item(f"{memory_percent()}% ", css_class="memory-label"))
        battery = battery_text()
        if battery:
            items.append(self.status_item(battery))
        items.append(self.status_item(time.strftime("%a %b %-d %-I:%M%p")))
        for item in items:
            self.status_box.pack_start(item, False, False, 0)
        self.show_all()
        self.update_tray_visibility()
        return True

    def change_brightness(self, target, delta):
        if target == "external":
            if not self.external_brightness_available:
                return
            current = self.external_brightness_percent if self.external_brightness_percent is not None else 50
            self.external_brightness_percent = clamp(current + delta, 1, 100)
            if not self.external_brightness_apply_source:
                self.external_brightness_apply_source = GLib.timeout_add(80, self.apply_external_brightness)
            GLib.timeout_add(80, self.update_status_once)
            return

        current = self.brightness_percent
        if current is None:
            current = backlight_percent()
        if current is None:
            return
        self.brightness_percent = clamp(current + delta, 1, 100)
        set_backlight_percent(self.brightness_percent)
        GLib.timeout_add(120, self.update_status_once)

    def apply_external_brightness(self):
        self.external_brightness_apply_source = 0
        if self.external_brightness_percent is not None:
            set_external_brightness_percent(self.external_brightness_percent)
        return False

    def brightness_button_pressed(self, _button, event, target):
        if event.button == 1:
            self.change_brightness(target, BRIGHTNESS_STEP)
            return True
        if event.button == 3:
            self.change_brightness(target, -BRIGHTNESS_STEP)
            return True
        return False

    def brightness_scrolled(self, _button, event, target):
        if event.direction == Gdk.ScrollDirection.UP:
            self.change_brightness(target, BRIGHTNESS_STEP)
            return True
        if event.direction == Gdk.ScrollDirection.DOWN:
            self.change_brightness(target, -BRIGHTNESS_STEP)
            return True
        return False

    def change_volume(self, delta):
        current = self.volume_percent
        if current is None:
            current, _muted = volume_percent()
        if current is None:
            return
        self.volume_percent = clamp(current + delta, 0, 100)
        self.volume_muted = False
        set_volume_percent(self.volume_percent)
        GLib.timeout_add(80, self.update_status_once)

    def volume_button_pressed(self, _button, event):
        if event.button == 1:
            self.change_volume(VOLUME_STEP)
            return True
        if event.button == 3:
            self.change_volume(-VOLUME_STEP)
            return True
        if event.button == 2:
            spawn_silent(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
            GLib.timeout_add(80, self.update_status_once)
            return True
        return False

    def volume_scrolled(self, _button, event):
        if event.direction == Gdk.ScrollDirection.UP:
            self.change_volume(VOLUME_STEP)
            return True
        if event.direction == Gdk.ScrollDirection.DOWN:
            self.change_volume(-VOLUME_STEP)
            return True
        return False

    def bluetooth_button_pressed(self, _button, event):
        if event.button == 1:
            toggle_bluetooth_manager()
            return True
        if event.button in {2, 3} and self.bluetooth_state:
            set_bluetooth_power(not self.bluetooth_state["powered"])
            GLib.timeout_add(250, self.update_status_once)
            return True
        return False

    def network_button_pressed(self, _button, event):
        if event.button == 1:
            open_network_manager()
            return True
        if event.button in {2, 3}:
            enabled = wifi_enabled()
            if enabled is not None:
                set_wifi_enabled(not enabled)
                GLib.timeout_add(500, self.update_status_once)
                return True
        return False

    def color_picker_button_pressed(self, _button):
        spawn_silent([
            "hyprpicker",
            "--autocopy",
            "--format",
            "hex",
            "--lowercase-hex",
            "--notify",
        ])

    def update_status_safe(self):
        try:
            self.update_status()
        except Exception:
            traceback.print_exc()
            return True
        return True

    def update_status_once(self):
        self.update_status_safe()
        return False

    def cpu_percent(self):
        current = cpu_times()
        if self.prev_cpu is None:
            self.prev_cpu = current
            return 0
        prev_idle, prev_total = self.prev_cpu
        idle, total = current
        self.prev_cpu = current
        total_delta = total - prev_total
        idle_delta = idle - prev_idle
        if total_delta <= 0:
            return 0
        return round((1 - idle_delta / total_delta) * 100)

    def image_for_app(self, app_id):
        app = desktop_app_for(app_id)
        if app and app.get_icon():
            image = Gtk.Image.new_from_gicon(app.get_icon(), Gtk.IconSize.MENU)
        else:
            image = Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.MENU)
        image.set_pixel_size(16)
        return image

    def workspace_label(self, number):
        return str(self.workspace_names.get(str(number)) or number)

    def save_workspace_name(self, number, name):
        key = str(number)
        name = name.strip()
        if name and name != key:
            self.workspace_names[key] = name
        else:
            self.workspace_names.pop(key, None)
        write_json(WORKSPACE_NAMES_PATH, self.workspace_names)
        self.update()

    def open_workspace_rename(self, number):
        if self.workspace_rename_window is not None:
            self.workspace_rename_window.destroy()

        window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        window.set_title(f"Rename workspace {number}")
        window.set_decorated(False)
        window.set_resizable(False)
        window.set_accept_focus(True)
        window.set_focus_on_map(True)
        window.set_app_paintable(True)

        GtkLayerShell.init_for_window(window)
        GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_namespace(window, "niri-appbar-workspace-rename")
        GtkLayerShell.set_keyboard_mode(window, GtkLayerShell.KeyboardMode.ON_DEMAND)
        GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(window, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.TOP, TOP_OFFSET + BAR_HEIGHT + 6)
        GtkLayerShell.set_margin(window, GtkLayerShell.Edge.LEFT, SIDE_MARGIN)

        entry = Gtk.Entry()
        entry.set_text(str(self.workspace_names.get(str(number), "")))
        entry.set_placeholder_text(f"Workspace {number}")
        entry.set_activates_default(True)
        entry.get_style_context().add_class("workspace-name-entry")
        entry.set_width_chars(18)

        state = {"closed": False}

        def close_window(save=False):
            if state["closed"]:
                return True
            state["closed"] = True
            if save:
                self.save_workspace_name(number, entry.get_text())
            if self.workspace_rename_window is window:
                self.workspace_rename_window = None
            window.destroy()
            return True

        def window_destroyed(*_args):
            if self.workspace_rename_window is window:
                self.workspace_rename_window = None

        def save_and_close(*_args):
            return close_window(save=True)

        def key_pressed(_widget, event):
            if event.keyval == Gdk.KEY_Escape:
                return close_window()
            return False

        def focus_out(*_args):
            GLib.idle_add(save_and_close)
            return False

        window.connect("destroy", window_destroyed)
        window.connect("key-press-event", key_pressed)
        window.connect("focus-out-event", focus_out)
        entry.connect("activate", save_and_close)
        entry.connect("focus-out-event", focus_out)
        window.add(entry)
        self.workspace_rename_window = window
        window.show_all()
        entry.grab_focus()

    def focus_workspace(self, number):
        spawn_silent(["niri", "msg", "action", "focus-workspace", str(number)])

    def focus_window(self, window_id):
        spawn_silent(["niri", "msg", "action", "focus-window", "--id", str(window_id)])

    def close_window(self, window_id):
        spawn_silent(["niri", "msg", "action", "close-window", "--id", str(window_id)])

    def app_button_released(self, _button, event, window_id):
        if event.button == 2:
            self.close_window(window_id)
            return True
        if event.button == 1:
            self.focus_window(window_id)
            return True
        return False

    def workspace_button_pressed(self, _button, event, number):
        if event.button == 1:
            self.focus_workspace(number)
            return True
        if event.button == 3:
            self.open_workspace_rename(number)
            return True
        return False

    def scroll_workspace(self, _button, event):
        if event.direction == Gdk.ScrollDirection.UP:
            action = "focus-workspace-up"
        elif event.direction == Gdk.ScrollDirection.DOWN:
            action = "focus-workspace-down"
        else:
            return False
        spawn_silent(["niri", "msg", "action", action])
        return True

    def power_button_pressed(self, _button):
        profile, _icon = self.power_profile_cache
        next_profile = {
            "performance": "balanced",
            "balanced": "power-saver",
            "power-saver": "performance",
        }.get(profile, "performance")
        icons = {
            "performance": "",
            "balanced": "",
            "power-saver": "",
        }
        self.power_profile_cache = (next_profile, icons[next_profile])
        spawn_silent([POWERPROFILESCTL, "set", next_profile])
        GLib.timeout_add(200, self.update_status_once)

    def refresh_power_profile(self):
        profile = power_profile()
        if profile[0]:
            self.power_profile_cache = profile
            GLib.idle_add(self.update_status_once)

    def refresh_external_brightness(self):
        percent = external_brightness_percent()
        if percent is None:
            changed = self.external_brightness_available
            self.external_brightness_available = False
            self.external_brightness_percent = None
        else:
            changed = (
                not self.external_brightness_available
                or self.external_brightness_percent != percent
            )
            self.external_brightness_percent = percent
            self.external_brightness_available = True
        if changed:
            GLib.idle_add(self.update_status_once)

    def watch_external_brightness(self):
        while True:
            try:
                self.refresh_external_brightness()
            except Exception:
                traceback.print_exc()
            time.sleep(EXTERNAL_BRIGHTNESS_INTERVAL_SECONDS)

    def watch_niri(self):
        while True:
            try:
                process = subprocess.Popen(
                    ["niri", "msg", "event-stream"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                for line in process.stdout:
                    if line.startswith(
                        (
                            "Workspaces changed:",
                            "Windows changed:",
                            "Window opened or changed:",
                            "Window closed:",
                            "Window focus changed:",
                        )
                    ):
                        GLib.idle_add(self.queue_update)
            except Exception:
                pass
            time.sleep(1)


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    AppBar()
    Gtk.main()


if __name__ == "__main__":
    main()
