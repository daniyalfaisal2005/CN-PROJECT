"""
GUI framework for P2P election system using tkinter.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import asyncio
import threading
from typing import Callable, Optional, Dict, List
from enum import Enum


class Theme:
    """Color theme for GUI - Modern vibrant dark theme."""
    # Background colors
    BG_DARK = '#0a0e27'       # Very dark background (navy)
    BG_LIGHT = '#1e2139'      # Slightly lighter background
    BG_PANEL = '#232d45'      # Panel background (deep blue-gray)
    
    # Text colors
    FG_TEXT = '#e1e8f0'       # Primary text (bright gray-blue)
    FG_MUTED = '#8b95a5'      # Muted text (medium gray)
    FG_ACCENT = '#00d9ff'     # Bright cyan accent
    
    # Button colors
    BTN_PRIMARY = '#5b4bef'   # Vibrant purple-indigo
    BTN_SUCCESS = '#00d084'   # Vibrant green
    BTN_DANGER = '#ff4757'    # Vibrant red
    BTN_HOVER = '#6f5aff'     # Brighter purple
    BTN_SECONDARY = '#4a5568' # Secondary button gray
    
    # Status colors
    ERROR = '#ff6b6b'
    SUCCESS = '#51cf66'
    WARNING = '#ffa94d'
    INFO = '#4dabf7'
    
    # Borders & highlights
    BORDER = '#3d4556'
    HIGHLIGHT = '#00d9ff'
    SHADOW = '#000000'


class GUIBase(tk.Tk):
    """Base class for GUI windows."""

    def __init__(self, title: str, geometry: str = '800x600'):
        super().__init__()
        self.title(title)
        self.geometry(geometry)
        self.configure(bg=Theme.BG_DARK)

        # Configure style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure ttk styles with professional colors
        style.configure('TLabel', background=Theme.BG_DARK, foreground=Theme.FG_TEXT)
        style.configure('TButton', background=Theme.BTN_PRIMARY, foreground=Theme.FG_TEXT,
                       borderwidth=0, focuscolor='none', padding=8)
        style.map('TButton',
                 background=[('active', Theme.BTN_HOVER)],
                 foreground=[('active', Theme.FG_TEXT)])
        
        style.configure('TFrame', background=Theme.BG_DARK)
        style.configure('TLabelFrame', background=Theme.BG_DARK, foreground=Theme.FG_TEXT)
        style.configure('TLabelFrame.Label', background=Theme.BG_DARK, foreground=Theme.FG_ACCENT)
        
        style.configure('TText', background=Theme.BG_LIGHT, foreground=Theme.FG_TEXT)
        style.configure('TEntry', fieldbackground=Theme.BG_LIGHT, foreground=Theme.FG_TEXT,
                       borderwidth=1)
        
        # Configure notebook (tabs)
        style.configure('TNotebook', background=Theme.BG_DARK, borderwidth=0)
        style.configure('TNotebook.Tab', background=Theme.BG_LIGHT, foreground=Theme.FG_TEXT,
                       padding=[20, 10])
        style.map('TNotebook.Tab',
                 background=[('selected', Theme.BTN_PRIMARY)],
                 foreground=[('selected', Theme.FG_TEXT)])

        self.loop = None
        self.async_thread = None
        self._running = True

    def create_frame(self, parent=None, **kwargs) -> ttk.Frame:
        """Create a styled frame."""
        if parent is None:
            parent = self
        return ttk.Frame(parent, **kwargs)

    def create_label(self, parent, text: str, **kwargs) -> ttk.Label:
        """Create a styled label."""
        return ttk.Label(parent, text=text, **kwargs)

    def create_button(self, parent, text: str, command: Callable, **kwargs) -> tk.Button:
        """Create a styled button with intelligent coloring and enhanced visuals."""
        # Determine button color based on text
        btn_color = Theme.BTN_PRIMARY
        if 'Delete' in text or 'Close' in text or 'Clear' in text:
            btn_color = Theme.BTN_DANGER
        elif 'Vote' in text or 'Enroll' in text or 'Start' in text or 'Send' in text or 'Spawn' in text:
            btn_color = Theme.BTN_SUCCESS
        
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=btn_color,
            fg=Theme.FG_TEXT,
            activebackground=Theme.BTN_HOVER if btn_color == Theme.BTN_PRIMARY else btn_color,
            activeforeground=Theme.FG_TEXT,
            relief=tk.FLAT,
            padx=16,
            pady=11,
            font=('Segoe UI', 9, 'bold'),
            cursor='hand2',
            highlightthickness=0,
            bd=0,
            **kwargs
        )
        
        # Add hover effects with visual feedback
        def on_enter(e):
            btn.config(relief=tk.RAISED, bd=1)
        
        def on_leave(e):
            btn.config(relief=tk.FLAT, bd=0)
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn

    def create_entry(self, parent, **kwargs) -> tk.Entry:
        """Create a styled entry with enhanced appearance."""
        entry = tk.Entry(
            parent,
            bg=Theme.BG_LIGHT,
            fg=Theme.FG_TEXT,
            insertbackground=Theme.FG_ACCENT,
            relief=tk.FLAT,
            font=('Segoe UI', 10),
            bd=0,
            highlightthickness=1,
            highlightcolor=Theme.HIGHLIGHT,
            highlightbackground=Theme.BORDER,
            **kwargs
        )
        
        # Add focus highlighting
        def on_focus_in(e):
            entry.config(highlightcolor=Theme.HIGHLIGHT, highlightthickness=2)
        
        def on_focus_out(e):
            entry.config(highlightthickness=1, highlightbackground=Theme.BORDER)
        
        entry.bind('<FocusIn>', on_focus_in)
        entry.bind('<FocusOut>', on_focus_out)
        
        return entry
        
        return entry

    def create_text(self, parent, height: int = 10, width: int = 40, **kwargs) -> scrolledtext.ScrolledText:
        """Create a styled scrolled text widget."""
        text = scrolledtext.ScrolledText(
            parent,
            height=height,
            width=width,
            bg=Theme.BG_LIGHT,
            fg=Theme.FG_TEXT,
            insertbackground=Theme.FG_ACCENT,
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=('Consolas', 9),
            bd=1,
            **kwargs
        )
        return text

    def create_listbox(self, parent, **kwargs) -> tk.Listbox:
        """Create a styled listbox."""
        listbox = tk.Listbox(
            parent,
            bg=Theme.BG_LIGHT,
            fg=Theme.FG_TEXT,
            selectbackground=Theme.BTN_PRIMARY,
            relief=tk.FLAT,
            font=('Segoe UI', 9),
            **kwargs
        )
        return listbox

    def show_status(self, message: str, color: str = Theme.FG_TEXT, duration: int = 3000):
        """Show status message."""
        if hasattr(self, 'status_label'):
            self.status_label.config(fg=color, text=message)
            if duration > 0:
                self.after(duration, lambda: self.status_label.config(text=''))

    def start_async_loop(self, loop: asyncio.AbstractEventLoop):
        """Start asyncio event loop in background thread."""
        self.loop = loop

        def run_loop():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

        self.async_thread = threading.Thread(target=run_loop, daemon=True)
        self.async_thread.start()

    def schedule_async(self, coro):
        """Schedule a coroutine in the asyncio loop."""
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop_async_loop(self):
        """Stop the asyncio event loop and cancel pending tasks."""
        if self.loop and self.loop.is_running():
            # Cancel all pending tasks
            def cancel_tasks():
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()
                # Stop the loop after tasks are cancelled
                self.loop.stop()
            
            self.loop.call_soon_threadsafe(cancel_tasks)

    def on_closing(self):
        """Handle window closing."""
        self._running = False
        self.stop_async_loop()
        self.destroy()


class ChatPanel(ttk.Frame):
    """Reusable chat panel widget with public and private messaging."""

    def __init__(self, parent, on_send: Callable = None, available_users: List[str] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_send = on_send
        self.available_users = available_users or []
        self.selected_recipient = None

        # Messages display
        self.messages_text = scrolledtext.ScrolledText(
            self,
            height=15,
            width=50,
            bg=Theme.BG_LIGHT,
            fg=Theme.FG_TEXT,
            state=tk.DISABLED,
            relief=tk.FLAT,
            font=('Consolas', 9),
            padx=8,
            pady=8
        )
        self.messages_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure tags for messages
        self.messages_text.tag_configure('system', foreground=Theme.FG_ACCENT, font=('Consolas', 9, 'bold'))
        self.messages_text.tag_configure('sender', foreground=Theme.BTN_PRIMARY, font=('Consolas', 9, 'bold'))
        self.messages_text.tag_configure('timestamp', foreground=Theme.FG_MUTED, font=('Consolas', 8))
        self.messages_text.tag_configure('private', foreground='#ff9800', font=('Consolas', 9, 'italic'))

        # Control frame
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Recipient selector
        recipient_label = tk.Label(
            control_frame,
            text='To:',
            bg=Theme.BG_DARK,
            fg=Theme.FG_TEXT,
            font=('Segoe UI', 9)
        )
        recipient_label.pack(side=tk.LEFT, padx=(0, 5))

        self.recipient_var = tk.StringVar(value='Everyone (Broadcast)')
        self.recipient_combo = ttk.Combobox(
            control_frame,
            textvariable=self.recipient_var,
            state='readonly',
            width=20,
            values=['Everyone (Broadcast)'] + self.available_users
        )
        self.recipient_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Input frame
        input_frame = ttk.Frame(self)
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        self.input_entry = tk.Entry(
            input_frame,
            bg=Theme.BG_PANEL,
            fg=Theme.FG_TEXT,
            insertbackground=Theme.FG_ACCENT,
            relief=tk.FLAT,
            font=('Segoe UI', 9),
            bd=1
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.input_entry.bind('<Return>', lambda e: self.send_message())

        send_btn = tk.Button(
            input_frame,
            text='Send',
            command=self.send_message,
            bg=Theme.BTN_PRIMARY,
            fg=Theme.FG_TEXT,
            relief=tk.FLAT,
            padx=15,
            pady=5,
            font=('Segoe UI', 9, 'bold'),
            cursor='hand2'
        )
        send_btn.pack(side=tk.RIGHT, padx=5)

    def update_users(self, users: List[str]):
        """Update available users for private messaging."""
        self.available_users = users
        current_values = ['Everyone (Broadcast)'] + users
        self.recipient_combo['values'] = current_values

    def send_message(self):
        """Handle send message."""
        message = self.input_entry.get().strip()
        recipient = self.recipient_var.get()
        
        if message and self.on_send:
            # Determine if private or broadcast
            is_private = recipient != 'Everyone (Broadcast)'
            self.on_send(message, recipient if is_private else None)
            self.input_entry.delete(0, tk.END)

    def add_message(self, sender: str, message: str, color: str = Theme.FG_TEXT, is_private: bool = False):
        """Add a message to display."""
        self.messages_text.config(state=tk.NORMAL)
        
        if is_private:
            prefix = f'[PRIVATE] {sender}'
            tag = 'private'
        else:
            prefix = sender
            tag = 'msg'
        
        self.messages_text.insert(tk.END, f'{prefix}: {message}\n', tag)
        self.messages_text.tag_configure(tag, foreground=color)
        self.messages_text.see(tk.END)
        self.messages_text.config(state=tk.DISABLED)

    def add_system_message(self, message: str, color: str = Theme.WARNING):
        """Add a system message."""
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.insert(tk.END, f'[SYSTEM] {message}\n', 'system')
        self.messages_text.tag_configure('system', foreground=color)
        self.messages_text.see(tk.END)
        self.messages_text.config(state=tk.DISABLED)

    def clear_messages(self):
        """Clear all messages."""
        self.messages_text.config(state=tk.NORMAL)
        self.messages_text.delete(1.0, tk.END)
        self.messages_text.config(state=tk.DISABLED)


class LogViewer(ttk.Frame):
    """Widget for displaying logs."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # Log display
        self.log_text = scrolledtext.ScrolledText(
            self,
            height=10,
            width=80,
            bg=Theme.BG_LIGHT,
            fg=Theme.FG_TEXT,
            state=tk.DISABLED,
            relief=tk.FLAT,
            font=('Courier', 8)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tag configuration
        self.log_text.tag_configure('DEBUG', foreground='#888888')
        self.log_text.tag_configure('INFO', foreground=Theme.FG_TEXT)
        self.log_text.tag_configure('WARNING', foreground=Theme.WARNING)
        self.log_text.tag_configure('ERROR', foreground=Theme.ERROR)

    def add_log(self, level: str, message: str):
        """Add a log message."""
        self.log_text.config(state=tk.NORMAL)
        tag = level.upper() if level.upper() in ['DEBUG', 'INFO', 'WARNING', 'ERROR'] else 'INFO'
        self.log_text.insert(tk.END, f'[{level.upper()}] {message}\n', tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def clear_logs(self):
        """Clear all logs."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
