#!/usr/bin/env python3
"""Graphical installer for QUA Libraries."""

from __future__ import annotations

import logging
import os
import queue
import shutil
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from config import INSTALLER_DIR, Manifest, Modality, UiTheme, load_manifest
from install_options import InstallOptions
from install import (
    build_plan_from_options,
    default_install_location,
    repo_root_from_location,
    run_install,
    setup_logging,
)

try:
    from PIL import Image, ImageTk

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

UI_FONT_FALLBACKS = (
    "Segoe UI",
    "SF Pro Text",
    "Helvetica Neue",
    "Ubuntu",
    "Cantarell",
    "DejaVu Sans",
    "TkDefaultFont",
)


def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except OSError:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except OSError:
            pass


def _ui_scale(root: tk.Misc) -> float:
    try:
        if sys.platform == "win32":
            import ctypes

            return ctypes.windll.user32.GetDpiForSystem() / 96.0
        return root.winfo_fpixels("1i") / 96.0
    except (OSError, tk.TclError, AttributeError):
        return 1.0


LOGO_DISPLAY_WIDTH = 240
SETUP_WINDOW_WIDTH = 1000
SETUP_WINDOW_HEIGHT = 640
PROGRESS_WINDOW_WIDTH = 1000
PROGRESS_WINDOW_HEIGHT = 780
COMPLETE_WINDOW_WIDTH = 1000
COMPLETE_WINDOW_HEIGHT = 640
FAILURE_HEADING_COLOR = "#C0392B"


def _configure_tk_scaling(root: tk.Misc) -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        dpi = ctypes.windll.user32.GetDpiForSystem()
        root.tk.call("tk", "scaling", dpi / 72.0)
    except (OSError, tk.TclError, AttributeError):
        pass


def _icon_bitmap_path(path: Path) -> str:
    """Tk on Windows cannot always load icons directly from a PyInstaller bundle."""
    if not path.is_file():
        raise FileNotFoundError(path)
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        dest = Path(tempfile.gettempdir()) / "qua_libs_installer.ico"
        shutil.copy2(path, dest)
        return str(dest)
    return str(path.resolve())


def _default_ui_family() -> str:
    if sys.platform == "win32":
        return "Segoe UI"
    if sys.platform == "darwin":
        return "Helvetica Neue"
    return "Ubuntu"


def _pick_ui_family(root: tk.Misc, preferred: str) -> str:
    families = set(tkfont.families(root))
    if preferred and preferred in families:
        return preferred
    for candidate in UI_FONT_FALLBACKS:
        if candidate in families:
            return candidate
    return "TkDefaultFont"


class UiFont:
    def __init__(self, root: tk.Misc, theme: UiTheme) -> None:
        self._root = root
        self._cache: dict[tuple[int, str], tkfont.Font] = {}
        preferred = theme.font_family.strip() or _default_ui_family()
        self._family = _pick_ui_family(root, preferred)

    def get(self, size: int = 10, weight: str = "normal") -> tkfont.Font:
        key = (size, weight)
        if key not in self._cache:
            self._cache[key] = tkfont.Font(root=self._root, family=self._family, size=size, weight=weight)
        return self._cache[key]


class QueueLogHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue[str]) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        self.log_queue.put(self.format(record))


class WinPrimaryButton(tk.Label):
    """Flat primary action button (Windows installer Next-style)."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        theme: UiTheme,
        fonts: UiFont,
        command,
    ) -> None:
        super().__init__(
            parent,
            text=text,
            bg=theme.accent,
            fg="#FFFFFF",
            activebackground=theme.accent_hover,
            activeforeground="#FFFFFF",
            font=fonts.get(10),
            cursor="hand2",
            padx=22,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.theme = theme
        self._command = command
        self._state = tk.NORMAL
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def configure_state(self, state: str) -> None:
        self._state = state
        if state == tk.DISABLED:
            self.configure(bg=self.theme.accent_inactive_bg, fg=self.theme.accent_inactive_fg, cursor="")
        else:
            self.configure(bg=self.theme.accent, fg="#FFFFFF", cursor="hand2")

    def _on_enter(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        self.configure(bg=self.theme.accent_hover)

    def _on_leave(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        self.configure(bg=self.theme.accent)

    def _on_click(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        if self._command:
            self._command()


class WinSecondaryButton(tk.Label):
    """Text-style secondary action (Close / Back)."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        theme: UiTheme,
        fonts: UiFont,
        command,
        *,
        bg: str,
    ) -> None:
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=theme.ink,
            activebackground=bg,
            activeforeground=theme.ink,
            font=fonts.get(10),
            cursor="hand2",
            padx=14,
            pady=8,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.theme = theme
        self._command = command
        self._state = tk.NORMAL
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def configure_state(self, state: str) -> None:
        self._state = state
        self.configure(
            fg=self.theme.ink if state == tk.NORMAL else self.theme.muted,
            cursor="hand2" if state == tk.NORMAL else "",
        )

    def _on_enter(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        self.configure(fg=self.theme.link)

    def _on_leave(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        self.configure(fg=self.theme.ink)

    def _on_click(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        if self._command:
            self._command()


class LinkButton(tk.Label):
    """Inline link with chevron."""

    def __init__(self, parent: tk.Misc, text: str, theme: UiTheme, fonts: UiFont, command, *, bg: str) -> None:
        super().__init__(
            parent,
            text=f"{text}  >",
            bg=bg,
            fg=theme.link,
            font=fonts.get(10),
            cursor="hand2",
        )
        self.theme = theme
        self._command = command
        self._state = tk.NORMAL
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def configure_state(self, state: str) -> None:
        self._state = state
        self.configure(fg=self.theme.link if state == tk.NORMAL else self.theme.muted)

    def _on_enter(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        self.configure(fg=self.theme.link_hover)

    def _on_leave(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        self.configure(fg=self.theme.link)

    def _on_click(self, _event: object) -> None:
        if self._state == tk.DISABLED:
            return
        self._command()


class InstallerApp:
    def __init__(self, root: tk.Tk, manifest: Manifest) -> None:
        self.root = root
        self.manifest = manifest
        self.settings = manifest.settings
        self.theme = manifest.settings.ui
        self.fonts = UiFont(root, self.theme)
        self.install_thread: threading.Thread | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._logo_image: tk.PhotoImage | None = None
        self._icon_image: tk.PhotoImage | None = None
        self._poll_after_id: str | None = None
        self._closing = False

        self._setup_ttk()
        root.title("QUA Libraries Installer")
        root.configure(bg=self.theme.surface)
        root.minsize(860, 560)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.content = tk.Frame(root, bg=self.theme.surface)
        self.content.pack(fill=tk.BOTH, expand=True)

        pad = self.theme.content_padding
        self.setup_page = tk.Frame(self.content, bg=self.theme.surface, padx=pad, pady=pad)
        self.progress_page = tk.Frame(self.content, bg=self.theme.surface, padx=pad, pady=pad)
        self.complete_page = tk.Frame(self.content, bg=self.theme.surface, padx=pad, pady=pad)

        self._build_setup_page(self.setup_page)
        self._build_progress_page(self.progress_page)
        self._build_complete_page(self.complete_page)

        self._show_page("setup")
        self._on_modality_selected()
        self._poll_log_queue()
        self.root.after_idle(self._finalize_window)

    def _finalize_window(self) -> None:
        self._set_window_icon(self.root)
        page = (
            "complete"
            if self.complete_page.winfo_ismapped()
            else "progress" if self.progress_page.winfo_ismapped() else "setup"
        )
        if page == "progress":
            self._apply_window_geometry(PROGRESS_WINDOW_WIDTH, PROGRESS_WINDOW_HEIGHT, center=True)
        elif page == "complete":
            self._apply_window_geometry(COMPLETE_WINDOW_WIDTH, COMPLETE_WINDOW_HEIGHT, center=True)
        else:
            self._apply_window_geometry(SETUP_WINDOW_WIDTH, SETUP_WINDOW_HEIGHT, center=True)

    def _window_dimensions(self, base_width: int, base_height: int) -> tuple[int, int]:
        self.root.update_idletasks()
        screen_w = max(1, self.root.winfo_screenwidth())
        screen_h = max(1, self.root.winfo_screenheight())
        scale = max(1.0, _ui_scale(self.root))
        width = max(int(base_width * scale), int(screen_w * 0.58))
        height = max(int(base_height * scale), int(screen_h * 0.68))
        return width, height

    def _apply_window_geometry(self, base_width: int, base_height: int, *, center: bool = False) -> None:
        width, height = self._window_dimensions(base_width, base_height)
        self.root.update_idletasks()
        screen_w = max(1, self.root.winfo_screenwidth())
        screen_h = max(1, self.root.winfo_screenheight())
        if center:
            x = max(0, (screen_w - width) // 2)
            y = max(0, (screen_h - height) // 2)
        else:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            if x <= 0 and y <= 0:
                x = max(0, (screen_w - width) // 2)
                y = max(0, (screen_h - height) // 2)
            else:
                x = max(0, min(x, screen_w - width))
                y = max(0, min(y, screen_h - height))
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        if sys.platform == "win32":
            self._force_window_size_windows(width, height, x, y)

    def _force_window_size_windows(self, width: int, height: int, x: int, y: int) -> None:
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if hwnd == 0:
                hwnd = self.root.winfo_id()
            SWP_NOZORDER = 0x0004
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, width, height, SWP_NOZORDER | SWP_SHOWWINDOW)
        except OSError:
            pass

    def _set_window_icon(self, root: tk.Misc) -> None:
        ico_path = INSTALLER_DIR / "assets" / "qm_favicon.ico"
        png_path = INSTALLER_DIR / "assets" / "qm_favicon_32.png"
        try:
            if sys.platform == "win32" and ico_path.is_file():
                bitmap_path = _icon_bitmap_path(ico_path)
                root.iconbitmap(default=bitmap_path)
                root.wm_iconbitmap(bitmap_path)
                return
            if HAS_PIL and png_path.is_file():
                hi_res = INSTALLER_DIR / "assets" / "qm_favicon_256.png"
                source = hi_res if hi_res.is_file() else png_path
                image = Image.open(source).convert("RGBA")
                self._icon_image = ImageTk.PhotoImage(image)
                root.iconphoto(True, self._icon_image)
            elif png_path.is_file():
                self._icon_image = tk.PhotoImage(file=str(png_path))
                root.iconphoto(True, self._icon_image)
        except (tk.TclError, OSError, FileNotFoundError) as exc:
            logging.warning("Could not set window icon: %s", exc)

    def _show_page(self, page: str) -> None:
        self.setup_page.pack_forget()
        self.progress_page.pack_forget()
        self.complete_page.pack_forget()
        if page == "setup":
            self.setup_page.pack(fill=tk.BOTH, expand=True)
            self._apply_window_geometry(SETUP_WINDOW_WIDTH, SETUP_WINDOW_HEIGHT)
        elif page == "progress":
            self.progress_page.pack(fill=tk.BOTH, expand=True)
            self._apply_window_geometry(PROGRESS_WINDOW_WIDTH, PROGRESS_WINDOW_HEIGHT)
        else:
            self.complete_page.pack(fill=tk.BOTH, expand=True)
            self._apply_window_geometry(COMPLETE_WINDOW_WIDTH, COMPLETE_WINDOW_HEIGHT)

    def _setup_ttk(self) -> None:
        theme = self.theme
        style = ttk.Style(self.root)
        if sys.platform == "win32" and "vista" in style.theme_names():
            style.theme_use("vista")
        else:
            for candidate in ("clam", "alt", "default"):
                if candidate in style.theme_names():
                    style.theme_use(candidate)
                    break

        body = self.fonts.get(10)
        style.configure(".", font=body, background=theme.surface, foreground=theme.ink)
        style.configure("Field.TLabel", background=theme.surface, foreground=theme.ink, font=body)
        style.configure("Section.TLabel", background=theme.surface, foreground=theme.ink, font=self.fonts.get(11))
        style.configure("Card.TCheckbutton", background=theme.surface, foreground=theme.ink, font=body)
        style.map("Card.TCheckbutton", background=[("active", theme.surface)])
        style.configure(
            "QM.TCombobox",
            fieldbackground=theme.log_bg,
            background=theme.log_bg,
            foreground=theme.ink,
            arrowcolor=theme.ink,
            bordercolor=theme.divider,
            padding=4,
        )
        style.configure(
            "QM.TEntry",
            fieldbackground=theme.log_bg,
            foreground=theme.ink,
            bordercolor=theme.divider,
            padding=4,
        )

    def _load_logo(self, parent: tk.Misc) -> None:
        if self._logo_image is None:
            logo_path = INSTALLER_DIR / "assets" / "qm_logo_header.png"
            if not logo_path.is_file():
                return
            try:
                scale = max(1.0, _ui_scale(self.root))
                target_width = int(LOGO_DISPLAY_WIDTH * scale)
                if HAS_PIL:
                    image = Image.open(logo_path).convert("RGBA")
                    target_height = max(1, int(target_width * image.height / image.width))
                    if image.width != target_width or image.height != target_height:
                        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
                    self._logo_image = ImageTk.PhotoImage(image)
                else:
                    self._logo_image = tk.PhotoImage(file=str(logo_path))
                    if self._logo_image.width() > target_width:
                        reduce = max(1, round(self._logo_image.width() / target_width))
                        self._logo_image = self._logo_image.subsample(reduce, reduce)
            except tk.TclError as exc:
                logging.warning("Could not load QM logo: %s", exc)
                return

        logo_label = tk.Label(parent, image=self._logo_image, bg=self.theme.surface)
        logo_label.image = self._logo_image
        logo_label.pack(anchor="w", pady=(0, 12))

    def _build_setup_page(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        self._build_setup_header(parent)
        self._build_options(parent)
        self._build_setup_footer(parent)

    def _build_progress_page(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1, minsize=200)

        self._build_progress_header(parent)
        self._build_progress(parent)
        self._build_progress_footer(parent)

    def _build_complete_page(self, parent: tk.Misc) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1, minsize=200)

        self._build_complete_header(parent)
        self._build_complete_summary(parent)
        self._build_complete_footer(parent)

    def _build_setup_header(self, parent: tk.Misc) -> None:
        theme = self.theme
        header = tk.Frame(parent, bg=theme.surface)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))

        self._load_logo(header)

        tk.Label(
            header,
            text="Set up QUA Libraries",
            bg=theme.surface,
            fg=theme.heading,
            font=self.fonts.get(22),
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            header,
            text=(
                "Choose a modality, install location, and Python version. "
                "The installer will clone the repository into that location, create a virtual environment, "
                "and configure QUAlibrate."
            ),
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(10),
            justify=tk.LEFT,
            anchor="w",
            wraplength=620,
        ).pack(anchor="w", pady=(8, 0))

    def _build_progress_header(self, parent: tk.Misc) -> None:
        theme = self.theme
        header = tk.Frame(parent, bg=theme.surface)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))

        self._load_logo(header)

        tk.Label(
            header,
            text="Installing QUA Libraries",
            bg=theme.surface,
            fg=theme.heading,
            font=self.fonts.get(22),
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Please wait while the installer completes the steps below.",
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(10),
            justify=tk.LEFT,
            anchor="w",
            wraplength=620,
        ).pack(anchor="w", pady=(8, 0))

    def _build_complete_header(self, parent: tk.Misc) -> None:
        theme = self.theme
        header = tk.Frame(parent, bg=theme.surface)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 18))

        self._load_logo(header)

        self.complete_title_label = tk.Label(
            header,
            text="Installation complete",
            bg=theme.surface,
            fg=theme.heading,
            font=self.fonts.get(22),
            anchor="w",
        )
        self.complete_title_label.pack(anchor="w")

        self.complete_subtitle_label = tk.Label(
            header,
            text="Your QUA Libraries environment is ready.",
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(10),
            justify=tk.LEFT,
            anchor="w",
            wraplength=620,
        )
        self.complete_subtitle_label.pack(anchor="w", pady=(8, 0))

    def _build_complete_summary(self, parent: tk.Misc) -> None:
        theme = self.theme
        summary = tk.Frame(parent, bg=theme.surface)
        summary.grid(row=1, column=0, sticky="nsew")
        summary.grid_columnconfigure(0, weight=1)
        summary.grid_rowconfigure(1, weight=1, minsize=140)

        ttk.Label(summary, text="Summary", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        summary_shell = tk.Frame(
            summary,
            bg=theme.log_bg,
            highlightbackground=theme.divider,
            highlightthickness=1,
        )
        summary_shell.grid(row=1, column=0, sticky="nsew")
        summary_shell.grid_columnconfigure(0, weight=1)
        summary_shell.grid_rowconfigure(0, weight=1)

        self.summary_text = tk.Text(
            summary_shell,
            wrap="word",
            state="disabled",
            bg=theme.log_bg,
            fg=theme.ink,
            insertbackground=theme.ink,
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=10,
            font=self.fonts.get(10),
        )
        self.summary_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(summary_shell, command=self.summary_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.summary_text.configure(yscrollcommand=scrollbar.set)

    def _build_complete_footer(self, parent: tk.Misc) -> None:
        theme = self.theme
        footer = tk.Frame(parent, bg=theme.surface)
        footer.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        footer.grid_columnconfigure(0, weight=1)

        tk.Frame(footer, bg=theme.divider, height=1).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        tk.Label(
            footer,
            text="Quantum Machines",
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(9),
        ).grid(row=1, column=0, sticky="w")

        actions = tk.Frame(footer, bg=theme.surface)
        actions.grid(row=1, column=1, sticky="e")

        WinPrimaryButton(
            actions,
            "Close",
            theme,
            self.fonts,
            self._on_close,
        ).pack(side=tk.RIGHT)

    def _summary_body_lines(self, summary: list[str]) -> list[str]:
        lines = summary[:]
        if lines and lines[0].strip().lower() == "installation complete":
            lines = lines[1:]
        return lines

    def _show_result_page(self, exit_code: int, summary: list[str]) -> None:
        theme = self.theme
        if exit_code == 0:
            self.complete_title_label.configure(
                text="Installation complete",
                fg=theme.heading,
            )
            self.complete_subtitle_label.configure(
                text="Your QUA Libraries environment is ready. Review the details below."
            )
        else:
            self.complete_title_label.configure(
                text="Installation failed",
                fg=FAILURE_HEADING_COLOR,
            )
            self.complete_subtitle_label.configure(
                text="Review the details below and check the log for more information."
            )

        body = self._summary_body_lines(summary)
        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", "\n".join(body))
        self.summary_text.configure(state="disabled")
        self._show_page("complete")

    def _build_options(self, parent: tk.Misc) -> None:
        theme = self.theme
        options = tk.Frame(parent, bg=theme.surface)
        options.grid(row=1, column=0, sticky="nsew", pady=(0, 16))
        options.grid_columnconfigure(1, weight=1)

        ttk.Label(options, text="Modality", style="Field.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 16), pady=6
        )
        modality_labels = {key: f"{key} — {mod.label}" for key, mod in self.manifest.modalities.items()}
        default_key = self.manifest.default_modality
        self.modality_var = tk.StringVar(value=modality_labels[default_key])
        self.modality_display = ttk.Combobox(
            options,
            textvariable=self.modality_var,
            values=[modality_labels[key] for key in self.manifest.modality_order],
            state="readonly",
            style="QM.TCombobox",
        )
        self.modality_display.grid(row=0, column=1, columnspan=2, sticky="ew", pady=6)
        self.modality_display.bind("<<ComboboxSelected>>", self._on_modality_selected)

        ttk.Label(options, text="Install to", style="Field.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 16), pady=6
        )
        self.dest_var = tk.StringVar()
        ttk.Entry(options, textvariable=self.dest_var, style="QM.TEntry").grid(
            row=1, column=1, sticky="ew", pady=6, padx=(0, 8)
        )
        self.browse_link = LinkButton(
            options,
            "Browse",
            theme,
            self.fonts,
            self._browse_dest,
            bg=theme.surface,
        )
        self.browse_link.grid(row=1, column=2, sticky="e", pady=6)

        ttk.Label(options, text="Python", style="Field.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=6)
        self.python_var = tk.StringVar(value=self.settings.default_python)
        ttk.Combobox(
            options,
            textvariable=self.python_var,
            values=list(self.settings.supported_python),
            state="readonly",
            width=10,
            style="QM.TCombobox",
        ).grid(row=2, column=1, sticky="w", pady=6)

        release = self.settings.release
        ttk.Label(options, text="QUA SDK", style="Field.TLabel").grid(row=3, column=0, sticky="w", padx=(0, 16), pady=6)
        sdk_label = f"qm-qua {release.qm_qua}" if release else "See compatibility matrix"
        ttk.Label(options, text=sdk_label, style="Field.TLabel").grid(row=3, column=1, columnspan=2, sticky="w", pady=6)

        if release:
            compat_text = (
                f"Tested with qua-libs-core {release.qua_libs_core}. "
                "See docs/COMPATIBILITY.md for the full compatibility matrix."
            )
        else:
            compat_text = "See docs/COMPATIBILITY.md for tested package combinations."
        tk.Label(
            options,
            text=compat_text,
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(9),
            justify=tk.LEFT,
            anchor="w",
            wraplength=620,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 6))

        checks = tk.Frame(options, bg=theme.surface)
        checks.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        self.telemetry_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            checks,
            text="Enable telemetry (local Uptrace via Docker)",
            style="Card.TCheckbutton",
            variable=self.telemetry_var,
        ).pack(anchor="w", pady=3)

        self.force_qualibrate_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            checks,
            text="Reconfigure QUAlibrate if ~/.qualibrate/config.toml already exists",
            style="Card.TCheckbutton",
            variable=self.force_qualibrate_var,
        ).pack(anchor="w", pady=3)

    def _build_progress(self, parent: tk.Misc) -> None:
        theme = self.theme
        progress = tk.Frame(parent, bg=theme.surface)
        progress.grid(row=1, column=0, sticky="nsew")
        progress.grid_columnconfigure(0, weight=1)
        progress.grid_rowconfigure(1, weight=1, minsize=140)

        ttk.Label(progress, text="Progress", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        log_shell = tk.Frame(
            progress,
            bg=theme.log_bg,
            highlightbackground=theme.divider,
            highlightthickness=1,
        )
        log_shell.grid(row=1, column=0, sticky="nsew")
        log_shell.grid_columnconfigure(0, weight=1)
        log_shell.grid_rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_shell,
            wrap="word",
            state="disabled",
            bg=theme.log_bg,
            fg=theme.ink,
            insertbackground=theme.ink,
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=10,
            font=self.fonts.get(9),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_shell, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _build_setup_footer(self, parent: tk.Misc) -> None:
        theme = self.theme
        footer = tk.Frame(parent, bg=theme.surface)
        footer.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        footer.grid_columnconfigure(0, weight=1)

        tk.Frame(footer, bg=theme.divider, height=1).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        tk.Label(
            footer,
            text="Quantum Machines",
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(9),
        ).grid(row=1, column=0, sticky="w")

        actions = tk.Frame(footer, bg=theme.surface)
        actions.grid(row=1, column=1, sticky="e")

        WinSecondaryButton(
            actions,
            "Close",
            theme,
            self.fonts,
            self._on_close,
            bg=theme.surface,
        ).pack(side=tk.RIGHT, padx=(12, 0))

        WinPrimaryButton(
            actions,
            "Install",
            theme,
            self.fonts,
            self._start_install,
        ).pack(side=tk.RIGHT)

    def _build_progress_footer(self, parent: tk.Misc) -> None:
        theme = self.theme
        footer = tk.Frame(parent, bg=theme.surface)
        footer.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        footer.grid_columnconfigure(0, weight=1)

        tk.Frame(footer, bg=theme.divider, height=1).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        tk.Label(
            footer,
            text="Quantum Machines",
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(9),
        ).grid(row=1, column=0, sticky="w")

        actions = tk.Frame(footer, bg=theme.surface)
        actions.grid(row=1, column=1, sticky="e")

        self.close_button = WinSecondaryButton(
            actions,
            "Close",
            theme,
            self.fonts,
            self._on_close,
            bg=theme.surface,
        )
        self.close_button.pack(side=tk.RIGHT)

    def _selected_modality(self) -> Modality:
        display = self.modality_var.get()
        key = display.split(" — ", 1)[0]
        return self.manifest.modalities[key]

    def _resolved_repo_root(self) -> Path | None:
        dest_raw = self.dest_var.get().strip()
        if not dest_raw:
            return None
        return repo_root_from_location(self._selected_modality(), dest_raw)

    def _on_modality_selected(self, _event: object | None = None) -> None:
        modality = self._selected_modality()
        self.dest_var.set(str(default_install_location(modality)))

    def _browse_dest(self) -> None:
        selected = filedialog.askdirectory(title="Choose install location")
        if selected:
            self.dest_var.set(selected)

    def _append_log(self, message: str) -> None:
        if self._closing:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _poll_log_queue(self) -> None:
        if self._closing:
            return
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log(message)
        if not self._closing and self.root.winfo_exists():
            self._poll_after_id = self.root.after(100, self._poll_log_queue)

    @staticmethod
    def _release_logging_handlers() -> None:
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            try:
                handler.close()
            except Exception:  # noqa: BLE001 - best-effort shutdown
                pass
            root_logger.removeHandler(handler)

    def _on_close(self) -> None:
        if self._closing:
            return
        if self.install_thread and self.install_thread.is_alive():
            if not messagebox.askokcancel(
                "Install in progress",
                "Installation is still running. Quit anyway?",
            ):
                return
        self._closing = True
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
            self._poll_after_id = None
        try:
            self.root.withdraw()
        except tk.TclError:
            pass
        self._release_logging_handlers()
        try:
            self.root.quit()
        except tk.TclError:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        os._exit(0)

    def _set_installing(self, installing: bool) -> None:
        state = tk.DISABLED if installing else tk.NORMAL
        self.close_button.configure_state(state)

    def _resolve_existing_action(self, dest: Path) -> str | None:
        if not dest.exists():
            return None
        is_git_clone = (dest / ".git").is_dir()
        if is_git_clone:
            choices = ["reinstall", "skip", "abort"]
            default = "abort"
            dialog_title = "Existing installation"
            heading = "Existing installation found"
            detail = f"{dest}\n\n" "This folder contains an existing git clone.\n\n" "What should the installer do?"
        else:
            choices = ["reinstall", "skip", "abort"]
            default = "reinstall"
            dialog_title = "Folder already exists"
            heading = "Folder already exists"
            detail = f"{dest}\n\n" "This path already exists on disk.\n\n" "What should the installer do?"

        theme = self.theme
        dialog = tk.Toplevel(self.root)
        dialog.title(dialog_title)
        dialog.configure(bg=theme.surface)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.minsize(460, 280)

        pad = tk.Frame(dialog, bg=theme.surface, padx=28, pady=24)
        pad.pack(fill=tk.BOTH, expand=True)
        pad.grid_columnconfigure(0, weight=1)

        tk.Label(
            pad,
            text=heading,
            bg=theme.surface,
            fg=theme.heading,
            font=self.fonts.get(14),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        tk.Label(
            pad,
            text=detail,
            bg=theme.surface,
            fg=theme.muted,
            font=self.fonts.get(10),
            justify=tk.LEFT,
            wraplength=400,
        ).grid(row=1, column=0, sticky="w", pady=(0, 12))

        choice_var = tk.StringVar(value=default)
        for index, option in enumerate(choices):
            ttk.Radiobutton(pad, text=option.capitalize(), value=option, variable=choice_var).grid(
                row=2 + index, column=0, sticky="w", pady=2
            )

        buttons = tk.Frame(pad, bg=theme.surface)
        buttons.grid(row=2 + len(choices), column=0, sticky="e", pady=(18, 0))

        result: dict[str, str | None] = {"value": None}

        def confirm() -> None:
            result["value"] = choice_var.get()
            dialog.destroy()

        def cancel() -> None:
            result["value"] = "abort"
            dialog.destroy()

        WinSecondaryButton(buttons, "Cancel", theme, self.fonts, cancel, bg=theme.surface).pack(
            side=tk.RIGHT, padx=(12, 0)
        )
        WinPrimaryButton(buttons, "Continue", theme, self.fonts, confirm).pack(side=tk.RIGHT)

        dialog.wait_window()
        return result["value"]

    def _build_options_obj(self) -> InstallOptions | None:
        modality = self._selected_modality()
        dest_raw = self.dest_var.get().strip()
        if not dest_raw:
            messagebox.showerror("Missing path", "Choose an install location.")
            return None

        repo_root = self._resolved_repo_root()
        assert repo_root is not None
        existing_action = self._resolve_existing_action(repo_root)
        if existing_action == "abort":
            return None

        return InstallOptions(
            modality=modality.key,
            dest=dest_raw,
            telemetry=self.telemetry_var.get(),
            existing_action=existing_action,
            python=self.python_var.get(),
            force_qualibrate=self.force_qualibrate_var.get(),
            yes=True,
            non_interactive=True,
        )

    def _confirm_docker_for_telemetry(self) -> bool:
        from telemetry_setup import docker_daemon_ready, docker_required_message, open_docker_install_page

        if docker_daemon_ready():
            return True

        while not docker_daemon_ready():
            if messagebox.askretrycancel("Docker required for telemetry", docker_required_message()):
                continue
            if messagebox.askyesno(
                "Open Docker install page?",
                "Open the Docker installation guide in your browser before trying again?",
            ):
                open_docker_install_page()
            return False
        return True

    def _abort_install_prep(self, message: str) -> None:
        self._append_log(message)
        self._set_installing(False)
        self._show_page("setup")

    def _continue_install(self) -> None:
        options = self._build_options_obj()
        if options is None:
            self._abort_install_prep("Installation cancelled.")
            return

        if options.telemetry:
            self._append_log("Checking Docker...")
            if not self._confirm_docker_for_telemetry():
                self._abort_install_prep("Installation cancelled.")
                return

        self._append_log("Starting installation...")

        def worker() -> None:
            try:
                plan = build_plan_from_options(self.manifest, options)
                exit_code, summary = run_install(self.manifest, options, plan)
            except Exception as exc:  # noqa: BLE001 - show any install failure in the GUI
                logging.exception("Installation failed")
                exit_code = 1
                summary = [f"Installation failed: {exc}"]

            def finish() -> None:
                if self._closing:
                    return
                self._set_installing(False)
                self._show_result_page(exit_code, summary)

            if not self._closing and self.root.winfo_exists():
                self.root.after(0, finish)

        self.install_thread = threading.Thread(target=worker, daemon=True)
        self.install_thread.start()

    def _start_install(self) -> None:
        if self.install_thread and self.install_thread.is_alive():
            return

        dest_raw = self.dest_var.get().strip()
        if not dest_raw:
            messagebox.showerror("Missing path", "Choose an install location.")
            return

        self._show_page("progress")

        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self._set_installing(True)
        self._append_log("Preparing installation...")
        self.root.update_idletasks()
        self.root.after(0, self._continue_install)


def main() -> int:
    try:
        manifest = load_manifest()
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"ERROR: Failed to load installer config: {exc}", file=sys.stderr)
        return 1

    if not HAS_PIL:
        print(
            "WARNING: Pillow is not installed; the QM logo may not display. " "Install with: pip install pillow",
            file=sys.stderr,
        )

    setup_logging(manifest.settings, gui=True)

    _enable_dpi_awareness()
    root = tk.Tk()
    _configure_tk_scaling(root)
    app = InstallerApp(root, manifest)

    queue_handler = QueueLogHandler(app.log_queue)
    queue_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(queue_handler)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
