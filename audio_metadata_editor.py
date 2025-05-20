#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import time
import platform
from typing import Dict, List, Optional, Tuple

# Workaround for macOS NSOpenPanel warning
is_macos = platform.system() == 'Darwin'
if is_macos:
    # Suppress NSOpenPanel warning on macOS
    # This redirects stderr temporarily during file dialog operations
    import contextlib
    import io
    import tempfile
    
    @contextlib.contextmanager
    def suppress_stderr():
        """Context manager to temporarily suppress stderr output."""
        stderr_fd = sys.stderr.fileno()
        with tempfile.NamedTemporaryFile(mode='w+') as tmp:
            stderr_copy = os.dup(stderr_fd)
            try:
                os.dup2(tmp.fileno(), stderr_fd)
                yield
            finally:
                os.dup2(stderr_copy, stderr_fd)
                os.close(stderr_copy)

# Audio metadata processing
import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, COMM
from mutagen.wave import WAVE
from mutagen.mp3 import MP3

# Import compatibility checker
from compatibility_checker import CompatibilityChecker

class AudioMetadataEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # App configuration
        self.title("Audio Metadata Editor")
        self.geometry("1000x700")
        self.minsize(800, 600)
        
        # Initialize variables
        self.current_dir = os.path.expanduser("~")  # Start in user's home directory
        self.status_var = tk.StringVar(value="Ready")  # Status bar text
        self.current_file = None  # Currently selected file
        self.checked_files_state = {}  # Track checked state of files
        self.supported_formats = ['.mp3', '.flac', '.wav', '.aaf']  # Supported audio formats
        self.last_report_data = []  # Store last compatibility check results
        
        # Initialize compatibility checker
        self.compatibility_checker = CompatibilityChecker(self)

        try:
            # Attempt to set application icon
            # Make sure 'app_icon.png' (or your chosen icon file) is in the same directory as the script
            # Or provide an absolute path to the icon file.
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.png')
            if os.path.exists(icon_path):
                self.iconphoto(True, tk.PhotoImage(file=icon_path))
            else:
                # You could print a warning if the icon is not found, or just proceed without it.
                print(f"Warning: Icon file not found at {icon_path}", flush=True) # Use flush for immediate output
        except tk.TclError as e:
            # This can happen if PhotoImage can't handle the file or on some systems
            print(f"Warning: Could not set application icon - {e}", flush=True)
        self.minsize(800, 600)
        
        # Set theme
        self.style = ttk.Style()
        # Use default theme as a base
        if is_macos:
            self.style.theme_use('aqua')
        elif is_windows:
            self.style.theme_use('vista')
        else:
            # On Linux and other platforms
            self.style.theme_use('clam')
        
        # Define theme colors as class attributes so they're accessible from all methods
        self.bg_color = "#FFFFFF"      # White background
        self.fg_color = "#333333"      # Dark gray text for contrast
        self.accent_color = "#26A69A"  # Teal accent
        self.primary_color = "#80CBC4"  # Lighter teal
        self.secondary_color = "#F5F5F5"  # Very light gray for secondary elements
        self.field_bg_color = "#F9F9F9"  # Slightly off-white for form fields
        self.highlight_color = "#4DB6AC"  # Brighter teal for hover states
        self.error_color = "#F44336"  # Red for errors
        self.success_color = "#4CAF50"  # Green for success indicators
        
        # Customize the style for a more modern look
        
        # Set window background color
        self.configure(background=self.bg_color)
        
        # Set frame background and foreground colors
        self.style.configure('TFrame', background=self.bg_color, foreground=self.fg_color)
        
        # Default style for labels
        self.style.configure('TLabel', background=self.bg_color, foreground=self.fg_color)
        self.style.configure('Treeview', background=self.bg_color, foreground=self.fg_color, fieldbackground=self.bg_color)
        self.style.map('Treeview', background=[('selected', self.accent_color)])
        
        # Variables
        self.current_dir = os.path.expanduser("~")
        self.status_var = tk.StringVar()
        self.current_file = None
        self.current_metadata = {}
        self.files_list = [] # To store full paths of listed files
        self.checked_files_state = {} # To store {file_path: True/False}
        self.batch_edit_menu_item_index = None # To store the index of the 'Batch Edit...' menu item
        self.supported_formats = ['.flac', '.mp3', '.wav', '.aaf']
        
        # Main layout
        self.create_menu()
        self.create_layout()
        
        # Bind events
        self.bind("<Control-o>", lambda e: self.browse_directory())
        self.bind("<Control-s>", lambda e: self.save_metadata())
    
    def configure_modern_style(self):
        # Use the class color attributes (defined in __init__) for consistent styling
        # No need for local variables - use self.fg_color directly for consistency
        
        # Button styles - primary action buttons
        self.style.configure("Accent.TButton", 
                            foreground=self.fg_color, 
                            background=self.accent_color,
                            relief=tk.RAISED, 
                            borderwidth=1, 
                            focusthickness=1, 
                            focuscolor=self.highlight_color,
                            padding=(10, 6))
        self.style.map("Accent.TButton", 
                      foreground=[("pressed", self.fg_color), ("active", self.fg_color)],
                      background=[("pressed", "#5daea6"), ("active", "#8fd8d0")])  # Lighter and darker accent
        
        # Button styles - secondary buttons
        self.style.configure("Secondary.TButton", 
                            foreground=self.fg_color, 
                            background=self.secondary_color,
                            relief=tk.RAISED, 
                            borderwidth=1, 
                            focusthickness=1, 
                            focuscolor=self.highlight_color,
                            padding=(10, 6))
        self.style.map("Secondary.TButton", 
                      foreground=[("pressed", self.fg_color), ("active", self.fg_color)],
                      background=[("pressed", "#3c4e57"), ("active", self.highlight_color)])
        
        # Treeview styling - for the file list
        self.style.configure("Treeview", 
                            background=self.field_bg_color,
                            foreground=self.fg_color,
                            rowheight=25,
                            fieldbackground=self.field_bg_color,
                            borderwidth=0)
        self.style.map("Treeview",
                      background=[("selected", self.primary_color)],
                      foreground=[("selected", self.fg_color)])
        
        # Treeview heading style - make headings more visible
        self.style.configure("Treeview.Heading", 
                            font=("Helvetica", 10, "bold"),
                            background=self.secondary_color, 
                            foreground=self.fg_color,
                            padding=(10, 5),
                            relief=tk.FLAT)
        self.style.map("Treeview.Heading",
                      background=[("active", self.highlight_color)],
                      foreground=[("active", self.fg_color)])
                      
        # Label frames - for sections
        self.style.configure("TLabelframe", 
                            background=self.bg_color,
                            borderwidth=1,
                            relief=tk.GROOVE)
        self.style.configure("TLabelframe.Label", 
                            foreground=self.accent_color,
                            background=self.bg_color,
                            font=("Helvetica", 11, "bold"))
                            
        # Entry fields
        self.style.configure("TEntry", 
                            foreground=self.fg_color,
                            fieldbackground=self.field_bg_color,
                            insertcolor=self.accent_color,  # Text cursor color
                            borderwidth=1,
                            padding=(8, 6))
        self.style.map("TEntry",
                       fieldbackground=[("focus", "#435761")],  # Slightly lighter when focused
                       bordercolor=[("focus", self.accent_color)])
                       
        # Checkbuttons - for field selection
        self.style.configure("TCheckbutton", 
                            background=self.bg_color,
                            foreground=self.fg_color,
                            indicatorcolor=self.accent_color)
        self.style.map("TCheckbutton",
                      background=[("active", self.bg_color)],
                      foreground=[("active", self.accent_color)])
                      
        # Labels
        self.style.configure("TLabel", 
                            background=self.bg_color,
                            foreground=self.fg_color,
                            padding=(2, 2))
                            
        # Info header labels - teal headers for visual hierarchy
        self.style.configure("Header.TLabel", 
                            font=("Helvetica", 10, "bold"),
                            foreground=self.accent_color,  # Teal for emphasis
                            background=self.bg_color)
                            
        # Status bar
        self.style.configure("Status.TLabel", 
                            background=self.secondary_color,
                            foreground=self.fg_color,
                            relief=tk.SUNKEN,
                            padding=(10, 5))
    
    def create_menu(self):
        """Create the application menu"""
        menubar = tk.Menu(self)
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Directory...", command=self.browse_directory, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        
        # Add Profile submenu
        profile_menu = tk.Menu(tools_menu, tearoff=0)
        profile_menu.add_command(label="Check Generic Strict Compatibility", command=self.check_compatibility)
        tools_menu.add_cascade(label="Profile", menu=profile_menu)
        
        tools_menu.add_separator()
        tools_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        # Set the menu to the window
        self.config(menu=menubar)
        
        # Key bindings
        self.bind("<Control-o>", lambda event: self.browse_directory())
        
        # Store menu references
        self.menubar = menubar
        self.file_menu = file_menu
        self.tools_menu = tools_menu
        self.profile_menu = profile_menu
    
    # Show about dialog
    def show_about(self):
        about_text = """Audio Metadata Editor

A simple tool for editing metadata in audio files.

Supported formats: MP3, FLAC, WAV

Version 1.0"""
        messagebox.showinfo("About", about_text)
        
    def create_layout(self):
        """Create the main application layout"""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure grid layout
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=3)
        main_frame.rowconfigure(0, weight=1)
        
        # Left panel - file browser
        browser_frame = ttk.LabelFrame(main_frame, text="Files")
        browser_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Directory browser
        browser_top_frame = ttk.Frame(browser_frame)
        browser_top_frame.pack(fill=tk.X, pady=5, padx=5)
        
        self.dir_var = tk.StringVar(value=self.current_dir)
        dir_entry = ttk.Entry(browser_top_frame, textvariable=self.dir_var)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        browse_btn = ttk.Button(browser_top_frame, text="Browse...", command=self.browse_directory)
        browse_btn.pack(side=tk.RIGHT)
        
        # File list with scrollbar
        file_frame = ttk.Frame(browser_frame)
        file_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Select All checkbox
        select_all_frame = ttk.Frame(file_frame)
        select_all_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.select_all_var = tk.BooleanVar(value=False)
        select_all_cb = ttk.Checkbutton(select_all_frame, text="Select All", 
                                       variable=self.select_all_var, 
                                       command=self.toggle_select_all,
                                       style="Field.TCheckbutton")
        select_all_cb.pack(side=tk.LEFT, padx=5)
        
        # Define columns: Checkbox, Filename, Format, Duration
        columns = ("checked", "filename", "format", "duration")
        self.file_tree = ttk.Treeview(file_frame, columns=columns, show="headings", selectmode="browse") 
        
        scrollbar = ttk.Scrollbar(file_frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.heading("checked", text="")
        self.file_tree.heading("filename", text="File Name")
        self.file_tree.heading("format", text="Format")
        self.file_tree.heading("duration", text="Duration")
        
        self.file_tree.column("checked", width=36, anchor=tk.CENTER, stretch=tk.NO)
        self.file_tree.column("filename", width=250, stretch=tk.YES)
        self.file_tree.column("format", width=80, anchor=tk.W)
        self.file_tree.column("duration", width=80, anchor=tk.W)

        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind left-click to handle checkbox toggle and row selection for metadata display
        self.file_tree.bind("<Button-1>", self.on_tree_click)
        
        # Right panel - metadata editor
        metadata_frame = ttk.LabelFrame(main_frame, text="Metadata Editor")
        metadata_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Split into file info and editable metadata
        metadata_frame.columnconfigure(0, weight=1)
        metadata_frame.rowconfigure(0, weight=0)  # File info
        metadata_frame.rowconfigure(1, weight=1)  # Editable metadata
        
        # Style specifically for the ScrolledText widget (Comment field)
        self.option_add("*Text*Background", self.field_bg_color)  # Set background
        self.option_add("*Text*foreground", self.fg_color)  # Set text color
        self.option_add("*Text*insertBackground", self.accent_color)  # Cursor color
        
        # File information panel
        info_frame = ttk.LabelFrame(metadata_frame, text="File Information")
        info_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X, padx=15, pady=12)
        
        # File info grid layout
        info_grid.columnconfigure(0, weight=0)
        info_grid.columnconfigure(1, weight=1)
        
        # File info labels - using Header.TLabel style for headers
        ttk.Label(info_grid, text="File:", style="Header.TLabel").grid(row=0, column=0, sticky=tk.W, pady=4)
        self.file_label = ttk.Label(info_grid, text="-")
        self.file_label.grid(row=0, column=1, sticky=tk.W, pady=4, padx=5)
        
        ttk.Label(info_grid, text="Format:", style="Header.TLabel").grid(row=1, column=0, sticky=tk.W, pady=4)
        self.format_label = ttk.Label(info_grid, text="-")
        self.format_label.grid(row=1, column=1, sticky=tk.W, pady=4, padx=5)
        
        ttk.Label(info_grid, text="Channels:", style="Header.TLabel").grid(row=2, column=0, sticky=tk.W, pady=4)
        self.channels_label = ttk.Label(info_grid, text="-")
        self.channels_label.grid(row=2, column=1, sticky=tk.W, pady=4, padx=5)
        
        ttk.Label(info_grid, text="Sample Rate:", style="Header.TLabel").grid(row=3, column=0, sticky=tk.W, pady=4)
        self.sample_rate_label = ttk.Label(info_grid, text="-")
        self.sample_rate_label.grid(row=3, column=1, sticky=tk.W, pady=4, padx=5)
        
        ttk.Label(info_grid, text="Bit Depth/Rate:", style="Header.TLabel").grid(row=4, column=0, sticky=tk.W, pady=4)
        self.bit_depth_label = ttk.Label(info_grid, text="-")
        self.bit_depth_label.grid(row=4, column=1, sticky=tk.W, pady=4, padx=5)
        
        ttk.Label(info_grid, text="Duration:", style="Header.TLabel").grid(row=5, column=0, sticky=tk.W, pady=4)
        self.duration_label = ttk.Label(info_grid, text="-")
        self.duration_label.grid(row=5, column=1, sticky=tk.W, pady=4, padx=5)
        
        # Metadata editor form
        form_frame = ttk.Frame(metadata_frame)
        form_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        form_frame.columnconfigure(0, weight=0)
        form_frame.columnconfigure(1, weight=1)
        
        # Configure columns for field checkboxes (for batch editing)
        form_frame.columnconfigure(0, weight=0)  # Checkbox
        form_frame.columnconfigure(1, weight=0)  # Label
        form_frame.columnconfigure(2, weight=1)  # Entry
        
        # Metadata field checkboxes (for batch editing)
        self.batch_field_vars = {}
        
        # Create a special style for field checkboxes
        self.style.configure("Field.TCheckbutton", 
                           background=self.field_bg_color,
                           foreground=self.fg_color,
                           relief=tk.GROOVE,
                           indicatorcolor=self.accent_color)
        
        # Metadata form fields with integrated batch checkboxes
        # Title
        self.batch_field_vars['title'] = tk.BooleanVar(value=False)
        title_checkbox = ttk.Checkbutton(form_frame, variable=self.batch_field_vars['title'], style="Field.TCheckbutton")
        title_checkbox.grid(row=0, column=0, padx=(0,6))
        
        ttk.Label(form_frame, text="Title:", style="Header.TLabel").grid(row=0, column=1, sticky=tk.W, pady=8)
        self.title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.title_var).grid(row=0, column=2, sticky=tk.EW, pady=8, padx=10)
        
        # Artist
        self.batch_field_vars['artist'] = tk.BooleanVar(value=False)
        artist_checkbox = ttk.Checkbutton(form_frame, variable=self.batch_field_vars['artist'], style="Field.TCheckbutton")
        artist_checkbox.grid(row=1, column=0, padx=(0,6))
        
        ttk.Label(form_frame, text="Artist:", style="Header.TLabel").grid(row=1, column=1, sticky=tk.W, pady=8)
        self.artist_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.artist_var).grid(row=1, column=2, sticky=tk.EW, pady=8, padx=10)
        
        # Album
        self.batch_field_vars['album'] = tk.BooleanVar(value=False)
        album_checkbox = ttk.Checkbutton(form_frame, variable=self.batch_field_vars['album'], style="Field.TCheckbutton")
        album_checkbox.grid(row=2, column=0, padx=(0,6))
        
        ttk.Label(form_frame, text="Album:", style="Header.TLabel").grid(row=2, column=1, sticky=tk.W, pady=8)
        self.album_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.album_var).grid(row=2, column=2, sticky=tk.EW, pady=8, padx=10)
        
        # Year/Date
        self.batch_field_vars['date'] = tk.BooleanVar(value=False)
        date_checkbox = ttk.Checkbutton(form_frame, variable=self.batch_field_vars['date'], style="Field.TCheckbutton")
        date_checkbox.grid(row=3, column=0, padx=(0,6))
        
        ttk.Label(form_frame, text="Year/Date:", style="Header.TLabel").grid(row=3, column=1, sticky=tk.W, pady=8)
        self.date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.date_var).grid(row=3, column=2, sticky=tk.EW, pady=8, padx=10)
        
        # Genre
        self.batch_field_vars['genre'] = tk.BooleanVar(value=False)
        genre_checkbox = ttk.Checkbutton(form_frame, variable=self.batch_field_vars['genre'], style="Field.TCheckbutton")
        genre_checkbox.grid(row=4, column=0, padx=(0,6))
        
        ttk.Label(form_frame, text="Genre:", style="Header.TLabel").grid(row=4, column=1, sticky=tk.W, pady=8)
        self.genre_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.genre_var).grid(row=4, column=2, sticky=tk.EW, pady=8, padx=10)
        
        # Comment
        self.batch_field_vars['comment'] = tk.BooleanVar(value=False)
        comment_checkbox = ttk.Checkbutton(form_frame, variable=self.batch_field_vars['comment'], style="Field.TCheckbutton")
        comment_checkbox.grid(row=5, column=0, padx=(0,6), sticky=tk.N)
        
        ttk.Label(form_frame, text="Comment:", style="Header.TLabel").grid(row=5, column=1, sticky=tk.NW, pady=8)
        self.comment_text = ScrolledText(form_frame, height=5, width=30, relief=tk.SOLID, borderwidth=1)
        self.comment_text.grid(row=5, column=2, sticky=tk.EW, pady=8, padx=10)
        
        # Add some vertical space
        ttk.Frame(form_frame).grid(row=6, column=0, pady=10)
        
        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=7, column=0, columnspan=3, sticky=tk.EW)
        
        # Using StringVar for dynamic button text
        self.save_btn_text = tk.StringVar(value="Save Changes")
        self.save_btn = ttk.Button(btn_frame, textvariable=self.save_btn_text, command=self.save_metadata, style="Accent.TButton")
        self.save_btn.pack(side=tk.LEFT, padx=6, pady=3)
        
        revert_btn = ttk.Button(btn_frame, text="Revert Changes", command=self.load_metadata, style="Secondary.TButton")
        revert_btn.pack(side=tk.LEFT, padx=6, pady=3)
        
        # Compatibility check button in edit view
        check_comp_btn = ttk.Button(btn_frame, text="Check Compatibility", command=self.check_compatibility, style="Secondary.TButton")
        check_comp_btn.pack(side=tk.RIGHT, padx=6, pady=3)
        
        # Auto-fix button (initially hidden, shown after compatibility check)
        self.auto_fix_btn = ttk.Button(btn_frame, text="Auto-Fix Issues", command=self.auto_fix_compatibility, style="Secondary.TButton")
        self.auto_fix_btn.pack(side=tk.RIGHT, padx=(0,6), pady=3)
        self.auto_fix_btn.pack_forget()  # Initially hidden
        
        # Status bar at bottom
        status_bar = ttk.Label(self, textvariable=self.status_var, style="Status.TLabel")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Browse for directory containing audio files
    def browse_directory(self):
        """Open directory browser dialog and load audio files"""
        # Use suppress_stderr on macOS to avoid NSOpenPanel warning
        if is_macos:
            with suppress_stderr():
                dir_path = filedialog.askdirectory(initialdir=self.current_dir)
        else:
            dir_path = filedialog.askdirectory(initialdir=self.current_dir)
            
        if dir_path:
            self.current_dir = dir_path
            self.dir_var.set(dir_path)
            self.load_directory(dir_path)
    
    # Load all audio files from directory
    def load_directory(self, dir_path):
        """Load all audio files from the specified directory"""
        self.status_var.set(f"Loading files from {dir_path}...")
        self.update_idletasks()
        
        # Clear current file list
        self.file_tree.delete(*self.file_tree.get_children())
        self.file_list = []
        
        try:
            # Find all audio files in the directory
            supported_formats = ['.mp3', '.flac', '.wav', '.aaf']
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                if os.path.isfile(file_path):
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext in supported_formats:
                        self.file_list.append(file_path)
            
            # Sort files alphabetically
            self.file_list.sort(key=lambda x: os.path.basename(x).lower())
            
            self.populate_file_tree(self.file_list)
            
            num_files = len(self.file_list)
            self.status_var.set(f"Loaded {num_files} audio file{'s' if num_files != 1 else ''}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading directory: {str(e)}")
            self.status_var.set("Error loading directory")
    
    # Toggle select all files
    def toggle_select_all(self):
        """Toggle selection of all files in the list"""
        select_all = self.select_all_var.get()
        checked_symbol = "[✔]" if select_all else "[ ]"
        
        # Update all checked states
        for file_path in self.checked_files_state.keys():
            self.checked_files_state[file_path] = select_all
            
            # Update visual checkbox
            current_values = list(self.file_tree.item(file_path, 'values'))
            current_values[0] = checked_symbol
            self.file_tree.item(file_path, values=tuple(current_values))
        
        # Update UI based on selection
        self.update_ui_for_batch()
    
    # Populate file tree with audio files
    def populate_file_tree(self, files):
        """Populate the file tree with the list of audio files"""
        self.file_tree.delete(*self.file_tree.get_children())
        self.file_list = files
        self.checked_files_state = {}
        
        checked_symbol = "[ ]"  # Unchecked by default
        
        for file_path in files:
            self.checked_files_state[file_path] = False  # Initialize as unchecked
            display_name = os.path.basename(file_path)
            fmt, dur = "N/A", "-"
            
            try:
                metadata = self.read_metadata(file_path)
                if metadata.get('error') and not metadata.get('format'):
                    display_name += " (Error)"
                    fmt = "Error"
                else:
                    fmt = metadata.get('format', 'N/A')
                    length = metadata.get('length', 0)
                    if length:
                        mins = int(length / 60)
                        secs = int(length % 60)
                        dur = f"{mins}:{secs:02d}"
            except Exception:
                display_name += " (Read Err)"
                fmt = "Error"
            
            # Values: checked_status, filename, format, duration
            self.file_tree.insert("", tk.END, iid=file_path, 
                                  values=(checked_symbol, display_name, fmt, dur))
        
        # Reset select all checkbox
        if hasattr(self, 'select_all_var'):
            self.select_all_var.set(False)
            
        # Update status 
        if files:
            self.status_var.set(f"Loaded {len(files)} files.")
        else:
            self.status_var.set("No audio files found in the selected directory.")
    
    # Check compatibility of files against the Generic Strict Profile
    def check_compatibility(self):
        """Check selected files against the Generic Strict Profile for compatibility"""
        # Check if any files are selected or checked
        selected_item = self.file_tree.selection()
        checked_files = [fp for fp, checked in self.checked_files_state.items() if checked]
        
        if not selected_item and not checked_files:
            messagebox.showinfo("No Files Selected", "Please select or check at least one file to check compatibility.")
            return
        
        files_to_check = []
        
        # Process selected or checked files
        if checked_files:
            # Process all checked files
            files_to_check = checked_files
        elif selected_item:
            # Process only the selected file
            file_path = selected_item[0]  # The iid is the file path
            files_to_check = [file_path]
        
        # Run the compatibility check
        self.status_var.set("Checking file compatibility...")
        self.update_idletasks()
        
        # Use the compatibility checker to validate files
        self.last_report_data, total_issues = self.compatibility_checker.check_compatibility(
            files_to_check, self.read_metadata)
        
        # Show Auto-Fix button if issues were found
        if total_issues > 0:
            self.auto_fix_btn.pack(side=tk.RIGHT, padx=(0,6), pady=3)
        else:
            self.auto_fix_btn.pack_forget()
        
        # Show the compatibility report
        self.compatibility_checker.show_compatibility_report(self.last_report_data, total_issues)
    
    # Auto-fix compatibility issues
    def auto_fix_compatibility(self):
        """Automatically fix common compatibility issues"""
        if not hasattr(self, 'last_report_data') or not self.last_report_data:
            messagebox.showinfo("No Issues", "Please run a compatibility check first.")
            return
        
        fixed_count = 0
        skipped_count = 0
        
        for filename, results in self.last_report_data:
            full_path = None
            # Find the full path from the filename
            for path in self.checked_files_state.keys():
                if os.path.basename(path) == filename:
                    full_path = path
                    break
            
            if not full_path:
                continue
                
            # Get current metadata
            metadata = self.read_metadata(full_path)
            if 'error' in metadata:
                skipped_count += 1
                continue
                
            updates_made = False
            
            # Auto-fix common issues
            if 'Missing title tag' in results['issues'] and os.path.basename(full_path):
                # Use filename (without extension) as title
                base_name = os.path.splitext(os.path.basename(full_path))[0]
                metadata['title'] = base_name
                updates_made = True
                
            if 'Missing artist tag' in results['issues']:
                # Set a default artist name
                metadata['artist'] = "Unknown Artist"
                updates_made = True
                
            # Trim overly long tags
            for field in ['title', 'artist', 'album']:
                issue_text = f"{field.capitalize()} tag exceeds 250 characters"
                if any(issue_text in issue for issue in results['issues']) and field in metadata:
                    metadata[field] = metadata[field][:250]
                    updates_made = True
            
            # Apply fixes if any were made
            if updates_made:
                result = self.write_metadata(full_path, metadata)
                if result.get('success', False):
                    fixed_count += 1
                else:
                    skipped_count += 1
        
        # Show results
        if fixed_count > 0:
            messagebox.showinfo("Auto-Fix Complete", 
                              f"Successfully fixed {fixed_count} files. {skipped_count} files could not be fixed automatically.")
            # Refresh current file if it was modified
            if self.current_file:
                self.load_metadata()
            # Reload directory to update file list
            if self.current_dir:
                self.load_directory(self.current_dir)
        else:
            messagebox.showinfo("Auto-Fix Complete", 
                              "No files could be automatically fixed. Some issues require manual editing.")
        
        # Hide auto-fix button until next compatibility check
        self.auto_fix_btn.pack_forget()
    
    # Handle click on the file_tree Treeview
    def on_tree_click(self, event):
        """Handle click on the file_tree Treeview - either check/uncheck or select file"""
        region = self.file_tree.identify_region(event.x, event.y)
        if region == "cell":
            # Get the item (row) and column that was clicked
            item_id = self.file_tree.identify_row(event.y)
            column_id = self.file_tree.identify_column(event.x)
            column_index = int(column_id.replace('#', '')) - 1
            
        item_id = self.file_tree.identify_row(event.y) # This is the iid (file_path)

        if not item_id: # Click outside of any item
            return

        if region == "cell" and column_id == "#1": # Clicked on the 'checked' column
            current_state = self.checked_files_state.get(item_id, False)
            new_state = not current_state
            self.checked_files_state[item_id] = new_state
            
            checked_symbol = "[✔]"
            unchecked_symbol = "[ ]"
            symbol_to_set = checked_symbol if new_state else unchecked_symbol
            
            # Update the visual state of the checkbox in the tree
            current_values = list(self.file_tree.item(item_id, 'values'))
            current_values[0] = symbol_to_set
            self.file_tree.item(item_id, values=tuple(current_values))
            
            self.update_ui_for_batch()
        
        # Always treat a click on a row (even checkbox) as a selection for metadata display
        if item_id != getattr(self, 'current_file', None):
            self.current_file = item_id
            self.load_metadata()
        
        # Ensure the clicked row gets focus/selection highlight
        if self.file_tree.selection() != (item_id,):
             self.file_tree.selection_set(item_id)
    
    # Load metadata from selected file
    def load_metadata(self):
        """Load metadata from the selected audio file"""
        if not hasattr(self, 'current_file') or not self.current_file:
            return
        
        try:
            self.status_var.set(f"Loading metadata from {os.path.basename(self.current_file)}...")
            self.update_idletasks()
            
            metadata = self.read_metadata(self.current_file)
            self.current_metadata = metadata
            
            # Update file info display
            self.file_label.config(text=os.path.basename(self.current_file))
            self.format_label.config(text=metadata.get('format', '-'))
            self.channels_label.config(text=str(metadata.get('channels', '-')))
            
            if metadata.get('sample_rate'):
                self.sample_rate_label.config(text=f"{metadata['sample_rate'] / 1000} kHz")
            else:
                self.sample_rate_label.config(text="-")
            
            # Handle bit depth or bitrate based on format
            if metadata.get('format') == 'MP3' and metadata.get('bitrate'):
                self.bit_depth_label.config(text=f"{metadata['bitrate'] / 1000:.0f} kbps")
            elif metadata.get('bits_per_sample'):
                self.bit_depth_label.config(text=f"{metadata['bits_per_sample']} bit")
            else:
                self.bit_depth_label.config(text="-")
            
            # Format duration
            if metadata.get('length'):
                mins = int(metadata['length'] / 60)
                secs = int(metadata['length'] % 60)
                self.duration_label.config(text=f"{mins}:{secs:02d}")
            else:
                self.duration_label.config(text="-")
            
            # Update form fields
            self.title_var.set(metadata.get('title', ''))
            self.artist_var.set(metadata.get('artist', ''))
            self.album_var.set(metadata.get('album', ''))
            self.date_var.set(metadata.get('date', ''))
            self.genre_var.set(metadata.get('genre', ''))
            
            # Update the comment text widget (needs special handling)
            self.comment_text.delete(1.0, tk.END)
            self.comment_text.insert(tk.END, metadata.get('comment', ''))
            
            self.status_var.set(f"Loaded metadata from {os.path.basename(self.current_file)}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading metadata: {str(e)}")
            self.status_var.set("Error loading metadata")
    
    # Save metadata changes to file(s)
    def save_metadata(self):
        """Save metadata changes to the audio file or multiple checked files"""
        # Check if we're in batch mode (multiple files checked + at least one batch field checkbox checked)
        checked_files = [fp for fp, checked in self.checked_files_state.items() if checked]
        batch_fields_checked = any(var.get() for var in self.batch_field_vars.values())
        
        # If in batch mode with multiple files, use the batch operation
        if len(checked_files) > 1 and batch_fields_checked:
            self.apply_batch_changes()
            return
        
        # Regular single file edit
        if not hasattr(self, 'current_file') or not self.current_file:
            messagebox.showinfo("Info", "No file selected")
            return
        
        try:
            self.status_var.set(f"Saving metadata to {os.path.basename(self.current_file)}...")
            self.update_idletasks()
            
            # Collect metadata from form
            metadata = {
                'title': self.title_var.get(),
                'artist': self.artist_var.get(),
                'album': self.album_var.get(),
                'date': self.date_var.get(),
                'genre': self.genre_var.get(),
                'comment': self.comment_text.get(1.0, tk.END).strip()
            }
            
            # Write metadata to file
            result = self.write_metadata(self.current_file, metadata)
            
            if result.get('success', False):
                self.status_var.set(f"Metadata saved to {os.path.basename(self.current_file)}")
                # Update current metadata
                if hasattr(self, 'current_metadata'):
                    self.current_metadata.update(metadata)
                
                # If this file was the only checked file and batch fields were selected,
                # reset the batch field checkboxes
                if len(checked_files) == 1 and self.current_file in checked_files and batch_fields_checked:
                    for var in self.batch_field_vars.values():
                        var.set(False)
                    self.update_ui_for_batch() # Update UI to reflect changes
            else:
                error_message = result.get('error', 'Unknown error')
                messagebox.showerror("Error", f"Failed to save metadata: {error_message}")
                self.status_var.set("Error saving metadata")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving metadata: {str(e)}")
            self.status_var.set("Error saving metadata")
    
    # Update UI for batch editing
    def update_ui_for_batch(self):
        """Update UI to show or hide batch editing controls based on file selection state"""
        checked_files = [fp for fp, checked in self.checked_files_state.items() if checked]
        batch_fields_checked = any(var.get() for var in self.batch_field_vars.values())
        
        # Always update Save button text to show number of files
        if checked_files and batch_fields_checked:
            self.save_btn_text.set(f"Save Changes ({len(checked_files)} files)")
        else:
            self.save_btn_text.set("Save Changes")
            
        # Handle select all checkbox state
        if not checked_files:
            # If no files checked, reset all field checkboxes
            for var in self.batch_field_vars.values():
                var.set(False)
            # Update select all checkbox
            if hasattr(self, 'select_all_var'):
                self.select_all_var.set(False)
    
    # Apply batch changes to multiple files
    def apply_batch_changes(self):
        """Apply changes from the main form to all checked files"""
        files_to_process = [fp for fp, checked in self.checked_files_state.items() if checked]
        
        if not files_to_process:
            messagebox.showinfo("Info", "No files checked. Please check files in the list to batch edit.")
            return
            
        # Check if any field is selected for batch update
        any_field_selected = any(var.get() for var in self.batch_field_vars.values())
        if not any_field_selected:
            messagebox.showinfo("Info", "No fields selected to update. Please tick the checkbox next to the fields you want to change.")
            return
            
        # Confirm with user
        if not messagebox.askyesno("Confirm Batch Update", 
                              f"This will modify metadata for {len(files_to_process)} selected file(s) based on the ticked fields. Continue?"):
            return
            
        self.status_var.set(f"Batch updating {len(files_to_process)} files...")
        self.update_idletasks()
        
        # Gather field values to update
        fields_to_update_values = {}
        for field_key, checkbox_var in self.batch_field_vars.items():
            if checkbox_var.get():  # If field checkbox is checked
                if field_key == 'comment':
                    value = self.comment_text.get(1.0, tk.END).strip()
                elif field_key == 'title':
                    value = self.title_var.get()
                elif field_key == 'artist':
                    value = self.artist_var.get()
                elif field_key == 'album':
                    value = self.album_var.get()
                elif field_key == 'date':
                    value = self.date_var.get()
                elif field_key == 'genre':
                    value = self.genre_var.get()
                fields_to_update_values[field_key] = value
                
        # Process files in a separate thread to keep UI responsive
        success_count = 0
        failed_files_details = []
        
        def _process_batch():
            nonlocal success_count, failed_files_details
            for file_path in files_to_process:
                try:
                    current_metadata = self.read_metadata(file_path)
                    if 'error' in current_metadata: # If read error, report it
                       failed_files_details.append((os.path.basename(file_path), f"Initial read failed: {current_metadata['error']}"))
                       continue
                       
                    metadata_to_write = current_metadata.copy()
                    
                    for field_key, new_value in fields_to_update_values.items():
                        metadata_to_write[field_key] = new_value
                    
                    result = self.write_metadata(file_path, metadata_to_write)
                    if result.get('success', False):
                        success_count += 1
                    else:
                        failed_files_details.append((os.path.basename(file_path), result.get('error', 'Unknown write error')))
                except Exception as e:
                    failed_files_details.append((os.path.basename(file_path), str(e)))
            
            self.after(0, _show_batch_results)
            
        def _show_batch_results():
            if failed_files_details:
                error_msg = "\n".join([f"{name}: {error}" for name, error in failed_files_details])
                messagebox.showerror("Batch Update Results", 
                                f"Updated {success_count} of {len(files_to_process)} files.\n\nErrors:\n{error_msg}")
            else:
                messagebox.showinfo("Batch Update Complete", f"Successfully updated metadata for {success_count} files.")
            
            self.status_var.set(f"Batch update completed: {success_count} of {len(files_to_process)} successful")
            
            # Refresh file tree to show any changes
            # Reload the current directory to refresh the list
            if self.current_dir:
                self.load_directory(self.current_dir)
        
        # Start processing thread
        threading.Thread(target=_process_batch, daemon=True).start()
    
    def read_metadata(self, file_path):
        """Read metadata from audio file based on its format"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            metadata = {
                'title': '',
                'artist': '',
                'album': '',
                'date': '',
                'genre': '',
                'comment': '',
                'format': os.path.splitext(file_path)[1][1:].upper(),
                'length': 0
            }
            
            if file_ext == '.flac':
                try:
                    audio = FLAC(file_path)
                    metadata.update({
                        'title': audio.get('title', [''])[0],
                        'artist': audio.get('artist', [''])[0],
                        'album': audio.get('album', [''])[0],
                        'date': audio.get('date', [''])[0],
                        'genre': audio.get('genre', [''])[0],
                        'comment': audio.get('comment', [''])[0],
                        'format': 'FLAC',
                        'channels': audio.info.channels,
                        'sample_rate': audio.info.sample_rate,
                        'bits_per_sample': audio.info.bits_per_sample,
                        'length': audio.info.length
                    })
                except Exception as e:
                    print(f"Error reading FLAC metadata: {str(e)}")
            
            elif file_ext == '.mp3':
                try:
                    # First try to get basic audio info - wrap this in try/except to handle corrupt files
                    try:
                        audio = MP3(file_path)
                        metadata.update({
                            'format': 'MP3',
                            'channels': getattr(audio.info, 'channels', 0),
                            'sample_rate': getattr(audio.info, 'sample_rate', 0),
                            'bitrate': getattr(audio.info, 'bitrate', 0),
                            'length': getattr(audio.info, 'length', 0)
                        })
                    except Exception as mp3_error:
                        print(f"Warning: MP3 audio info error: {str(mp3_error)}")
                        # Continue anyway to try to get ID3 tags
                    
                    # Then try to get ID3 tags separately
                    try:
                        id3 = ID3(file_path)
                        if id3:
                            if 'TIT2' in id3 and hasattr(id3['TIT2'], 'text') and id3['TIT2'].text:
                                metadata['title'] = id3['TIT2'].text[0]
                            if 'TPE1' in id3 and hasattr(id3['TPE1'], 'text') and id3['TPE1'].text:
                                metadata['artist'] = id3['TPE1'].text[0]
                            if 'TALB' in id3 and hasattr(id3['TALB'], 'text') and id3['TALB'].text:
                                metadata['album'] = id3['TALB'].text[0]
                            if 'TDRC' in id3 and hasattr(id3['TDRC'], 'text') and id3['TDRC'].text:
                                metadata['date'] = str(id3['TDRC'].text[0])
                            if 'TCON' in id3 and hasattr(id3['TCON'], 'text') and id3['TCON'].text:
                                metadata['genre'] = str(id3['TCON'].text[0])
                            if 'COMM' in id3 and hasattr(id3['COMM'], 'text') and id3['COMM'].text:
                                metadata['comment'] = id3['COMM'].text[0]
                    except Exception as id3_error:
                        print(f"Warning: ID3 tag reading error: {str(id3_error)}")
                except Exception as e:
                    print(f"Error reading MP3 metadata: {str(e)}")
            
            elif file_ext == '.wav':
                try:
                    audio = WAVE(file_path)
                    metadata.update({
                        'format': 'WAV',
                        'channels': audio.info.channels,
                        'sample_rate': audio.info.sample_rate,
                        'bits_per_sample': getattr(audio.info, 'bits_per_sample', 0),
                        'length': audio.info.length
                    })
                    
                    # Try to get ID3 tags if available in WAV
                    try:
                        id3 = ID3(file_path)
                        if 'TIT2' in id3 and hasattr(id3['TIT2'], 'text') and id3['TIT2'].text:
                            metadata['title'] = id3['TIT2'].text[0]
                        if 'TPE1' in id3 and hasattr(id3['TPE1'], 'text') and id3['TPE1'].text:
                            metadata['artist'] = id3['TPE1'].text[0]
                        if 'TALB' in id3 and hasattr(id3['TALB'], 'text') and id3['TALB'].text:
                            metadata['album'] = id3['TALB'].text[0]
                        if 'TDRC' in id3 and hasattr(id3['TDRC'], 'text') and id3['TDRC'].text:
                            metadata['date'] = str(id3['TDRC'].text[0])
                        if 'TCON' in id3 and hasattr(id3['TCON'], 'text') and id3['TCON'].text:
                            metadata['genre'] = str(id3['TCON'].text[0])
                        if 'COMM' in id3 and hasattr(id3['COMM'], 'text') and id3['COMM'].text:
                            metadata['comment'] = id3['COMM'].text[0]
                    except Exception as id3_error:
                        # WAV may not have ID3 tags, just continue
                        pass
                except Exception as e:
                    print(f"Error reading WAV metadata: {str(e)}")

                    
            elif file_ext == '.aaf':
                # AAF handling is more complex, this is a simplified approach
                metadata.update({
                    'format': 'AAF',
                    'note': 'AAF metadata extraction requires specialized libraries'
                })
                
                # Try to use mutagen to extract any available metadata
                try:
                    audio = mutagen.File(file_path)
                    if audio and hasattr(audio, 'info'):
                        metadata['length'] = getattr(audio.info, 'length', 0)
                    
                    # Try to extract any available standard tags
                    for key in ['title', 'artist', 'album', 'date', 'genre', 'comment']:
                        if key in audio:
                            try:
                                metadata[key] = audio[key][0]
                            except (IndexError, TypeError):
                                pass
                except Exception as e:
                    print(f"Could not extract AAF metadata with mutagen: {str(e)}")
                    # Continue processing other files
            
            return metadata
        
        except Exception as e:
            print(f"Error reading metadata: {str(e)}")
            return {
                'error': str(e),
                'title': '',
                'artist': '',
                'album': '',
                'date': '',
                'genre': '',
                'comment': '',
                'format': os.path.splitext(file_path)[1][1:].upper()
            }
    
    def write_metadata(self, file_path, metadata):
        """Write metadata to audio file based on its format"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.flac':
                audio = FLAC(file_path)
                if 'title' in metadata: audio['title'] = metadata['title']
                if 'artist' in metadata: audio['artist'] = metadata['artist']
                if 'album' in metadata: audio['album'] = metadata['album']
                if 'date' in metadata: audio['date'] = metadata['date']
                if 'genre' in metadata: audio['genre'] = metadata['genre']
                if 'comment' in metadata: audio['comment'] = metadata['comment']
                audio.save()
                
            elif file_ext == '.mp3':
                try:
                    audio = ID3(file_path)
                except:
                    # If no ID3 tags exist, create them
                    from mutagen.id3 import ID3NoHeaderError
                    try:
                        audio = ID3()
                    except ID3NoHeaderError:
                        audio = ID3()
                
                if 'title' in metadata: audio['TIT2'] = TIT2(encoding=3, text=[metadata['title']])
                if 'artist' in metadata: audio['TPE1'] = TPE1(encoding=3, text=[metadata['artist']])
                if 'album' in metadata: audio['TALB'] = TALB(encoding=3, text=[metadata['album']])
                if 'date' in metadata: audio['TDRC'] = TDRC(encoding=3, text=[metadata['date']])
                if 'genre' in metadata: audio['TCON'] = TCON(encoding=3, text=[metadata['genre']])
                if 'comment' in metadata: 
                    audio['COMM'] = COMM(encoding=3, lang='eng', desc='Comment', text=[metadata['comment']])
                
                audio.save(file_path)
                
            elif file_ext == '.wav':
                # WAV files can have ID3 tags, but it's not standard
                try:
                    audio = ID3(file_path)
                except:
                    # If no ID3 tags exist, create them
                    audio = ID3()
                
                if 'title' in metadata: audio['TIT2'] = TIT2(encoding=3, text=[metadata['title']])
                if 'artist' in metadata: audio['TPE1'] = TPE1(encoding=3, text=[metadata['artist']])
                if 'album' in metadata: audio['TALB'] = TALB(encoding=3, text=[metadata['album']])
                if 'date' in metadata: audio['TDRC'] = TDRC(encoding=3, text=[metadata['date']])
                if 'genre' in metadata: audio['TCON'] = TCON(encoding=3, text=[metadata['genre']])
                if 'comment' in metadata: 
                    audio['COMM'] = COMM(encoding=3, lang='eng', desc='Comment', text=[metadata['comment']])
                
                audio.save(file_path)
                
            elif file_ext == '.aaf':
                # AAF format requires specialized handling
                return {
                    'success': False,
                    'message': 'Writing AAF metadata is not fully supported in this version.'
                }
                
            return {
                'success': True,
                'message': 'Metadata updated successfully'
            }
            
        except Exception as e:
            print(f"Error writing metadata: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to update metadata: {str(e)}'
            }

if __name__ == "__main__":
    # Define required platform variables
    is_windows = platform.system() == 'Windows'
    app = AudioMetadataEditor()
    app.mainloop()