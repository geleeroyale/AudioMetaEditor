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
        
        # Maximize window at startup
        self.after(100, self.maximize_window)  # Short delay to ensure window is fully created

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
    
    def maximize_window(self):
        """Maximize the window after initialization"""
        # Get screen dimensions
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Maximize the window based on platform
        if is_macos:
            # macOS uses state='zoomed' but it might not work on all versions
            # So we'll also set the geometry to use most of the screen
            self.state('zoomed')
            # Leave some margin for the dock and menu bar
            self.geometry(f"{screen_width-100}x{screen_height-100}+50+50")
        elif is_windows:
            # Windows can use state='zoomed'
            self.state('zoomed')
        else:
            # Linux/other platforms
            self.attributes("-zoomed", True)  # For some window managers
            # Fallback to manual resizing if needed
            self.geometry(f"{screen_width}x{screen_height}+0+0")
    
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
        file_menu.add_command(label="Delete Selected Files", command=self.delete_selected_files)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        
        # Profile sub-menu
        profile_menu = tk.Menu(tools_menu, tearoff=0)
        profile_menu.add_command(label="Check Selected Files Compatibility", command=self.check_compatibility)
        profile_menu.add_command(label="Scan Directory Recursively", command=self.scan_directory_recursively)
        tools_menu.add_cascade(label="Profile", menu=profile_menu)
        
        # Cleanup menu
        cleanup_menu = tk.Menu(tools_menu, tearoff=0)
        cleanup_menu.add_command(label="Remove macOS Resource Files", command=self.remove_macos_resource_files)
        tools_menu.add_cascade(label="Cleanup", menu=cleanup_menu)
        
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
        
        # Toolbar in the file browser section
        toolbar_frame = ttk.Frame(browser_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 5), padx=5)
        
        # Initialize the integrity check boolean variable in the compatibility checker
        if not hasattr(self.compatibility_checker, 'perform_integrity_check'):
            self.compatibility_checker.perform_integrity_check = tk.BooleanVar(value=False)
        
        # Create a row for buttons
        button_row1 = ttk.Frame(toolbar_frame)
        button_row1.pack(fill=tk.X, pady=(0, 2))
        
        # Create a second row for more buttons and the checkbox
        button_row2 = ttk.Frame(toolbar_frame)
        button_row2.pack(fill=tk.X, pady=(2, 0))
        
        # Add Check Selected button
        check_button = ttk.Button(button_row1, text="Check Selected", command=self.check_compatibility,
                             style="Accent.TButton", width=15)
        check_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        # Add Delete Selected button
        delete_button = ttk.Button(button_row1, text="Delete Selected", command=self.delete_selected_files,
                             style="Secondary.TButton", width=15)
        delete_button.pack(side=tk.LEFT, padx=2, pady=2)
        
        # Add Scan Directory Recursively button
        scan_dir_btn = ttk.Button(button_row2, text="Scan Directory Recursively", 
                               command=self.scan_directory_recursively, 
                               style="Secondary.TButton", width=25)
        scan_dir_btn.pack(side=tk.LEFT, padx=2, pady=2)
        
        # Add file integrity checkbox
        integrity_check = ttk.Checkbutton(button_row2, text="Enable File Integrity Check", 
                                       variable=self.compatibility_checker.perform_integrity_check)
        integrity_check.pack(side=tk.LEFT, padx=(10, 2), pady=2)
        
        # File list with scrollbar
        file_frame = ttk.Frame(browser_frame)
        file_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Select All checkbox and action buttons
        select_all_frame = ttk.Frame(file_frame)
        select_all_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.select_all_var = tk.BooleanVar(value=False)
        select_all_cb = ttk.Checkbutton(select_all_frame, text="Select All", 
                                       variable=self.select_all_var, 
                                       command=self.toggle_select_all,
                                       style="Field.TCheckbutton")
        select_all_cb.pack(side=tk.LEFT, padx=5)
        
        # Removed Delete button since it's now in the toolbar
        
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
        
        # Auto-fix button (initially hidden, shown after compatibility check)
        self.auto_fix_btn = ttk.Button(btn_frame, text="Auto-Fix Issues", command=self.auto_fix_compatibility, style="Accent.TButton")
        self.auto_fix_btn.pack(side=tk.RIGHT, padx=6, pady=3)
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
    
    # Delete selected files
    def delete_selected_files(self):
        """Delete the selected/checked files from disk"""
        # Get checked files
        checked_files = [fp for fp, checked in self.checked_files_state.items() if checked]
        
        # If no files are checked, try to use the currently selected file
        if not checked_files and self.current_file:
            checked_files = [self.current_file]
        
        # Verify we have files to delete
        if not checked_files:
            messagebox.showinfo("No Files Selected", "Please select files to delete using the checkboxes.")
            return
        
        # Show file list for confirmation
        file_list = "\n".join([os.path.basename(f) for f in checked_files])
        if len(checked_files) > 10:
            # Truncate list if too long
            file_list = "\n".join([os.path.basename(f) for f in checked_files[:10]])
            file_list += f"\n... and {len(checked_files) - 10} more files"
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Deletion", 
                                 f"Are you sure you want to delete these {len(checked_files)} files?\n\n{file_list}", 
                                 icon="warning"):
            return
        
        # Delete files
        deleted_count = 0
        errors = []
        
        for file_path in checked_files:
            try:
                os.remove(file_path)
                deleted_count += 1
            except Exception as e:
                errors.append(f"{os.path.basename(file_path)}: {str(e)}")
        
        # Show results
        if errors:
            error_msg = "\n".join(errors[:10])
            if len(errors) > 10:
                error_msg += f"\n... and {len(errors) - 10} more errors"
            messagebox.showerror("Deletion Errors", 
                               f"Successfully deleted {deleted_count} files, but {len(errors)} errors occurred:\n\n{error_msg}")
        else:
            messagebox.showinfo("Deletion Complete", f"Successfully deleted {deleted_count} files.")
        
        # Refresh file list
        if self.current_dir:
            self.load_directory(self.current_dir)
    
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
        
        # Run the compatibility check on selected files
        self.check_compatibility_for_files(files_to_check)
    
    # Check compatibility of specific files
    def check_compatibility_for_files(self, files_to_check):
        """Run compatibility check on specific files"""
        # Update status
        self.status_var.set(f"Checking compatibility of {len(files_to_check)} files...")
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
    
    # Recursively scan a directory for audio files and check compatibility
    def scan_directory_recursively(self):
        """Scan a directory recursively for audio files and check their compatibility"""
        # Ask the user to select a directory
        directory = filedialog.askdirectory(title="Select Directory to Scan Recursively")
        if not directory:
            return  # User cancelled
        
        # Update status
        self.status_var.set("Scanning directories for audio files...")
        self.update_idletasks()
        
        # Find all audio files recursively
        audio_files = []
        total_files = 0
        scanned_dirs = 0
        
        # Progress dialog
        progress_window = tk.Toplevel(self)
        progress_window.title("Scanning Directories")
        progress_window.geometry("400x150")
        progress_window.transient(self)  # Set as transient to main window
        progress_window.grab_set()  # Make modal
        
        # Progress info
        progress_frame = ttk.Frame(progress_window, padding=20)
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        status_var = tk.StringVar(value="Initializing scan...")
        status_label = ttk.Label(progress_frame, textvariable=status_var)
        status_label.pack(fill=tk.X, pady=(0, 10))
        
        progress_count = tk.StringVar(value="Found: 0 audio files, 0 directories")
        progress_count_label = ttk.Label(progress_frame, textvariable=progress_count)
        progress_count_label.pack(fill=tk.X, pady=(0, 10))
        
        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, mode="indeterminate")
        progress_bar.pack(fill=tk.X, pady=(0, 10))
        progress_bar.start(10)
        
        # Cancel button
        cancel_var = tk.BooleanVar(value=False)
        cancel_button = ttk.Button(progress_frame, text="Cancel", 
                                command=lambda: cancel_var.set(True))
        cancel_button.pack(pady=5)
        
        # Update progress function
        def update_progress():
            progress_count.set(f"Found: {len(audio_files)} audio files, {scanned_dirs} directories")
            progress_window.update_idletasks()
            
            # Check if user cancelled
            if cancel_var.get():
                return False
            return True
        
        # Process scan results
        def process_results():
            progress_bar.stop()
            progress_window.destroy()
            
            if not audio_files:
                messagebox.showinfo("No Files Found", 
                                  "No supported audio files were found in the selected directory.")
                return
            
            # Ask user if they want to proceed with compatibility check
            if messagebox.askyesno("Scan Complete", 
                                  f"Found {len(audio_files)} audio files in {scanned_dirs} directories.\n\nProceed with compatibility check?"):
                # Store file paths for compatibility checker to reference later
                self.scan_file_paths = audio_files.copy()
                
                # Run compatibility check on all found files
                self.check_compatibility_for_files(audio_files)
        
        # Recursive scanning function (executed in a separate thread)
        def scan_thread():
            nonlocal audio_files, total_files, scanned_dirs
            
            try:
                # Walk through directory structure
                for root, dirs, files in os.walk(directory):
                    # Update status with current directory
                    current_dir = os.path.basename(root) or root
                    status_var.set(f"Scanning: {current_dir}")
                    scanned_dirs += 1
                    
                    # Find audio files in this directory
                    for filename in files:
                        if any(filename.lower().endswith(ext) for ext in self.supported_formats):
                            full_path = os.path.join(root, filename)
                            audio_files.append(full_path)
                            total_files += 1
                    
                    # Update progress and check for cancel
                    if scanned_dirs % 5 == 0:  # Update every 5 directories for performance
                        if not update_progress():
                            self.after(0, progress_window.destroy)
                            return  # User cancelled
                
                # Scan complete - process results in the main thread
                self.after(0, process_results)
                
            except Exception as e:
                def show_error():
                    progress_window.destroy()
                    messagebox.showerror("Error", f"An error occurred while scanning: {str(e)}")
                self.after(0, show_error)
        
        # Start the scan in a separate thread
        threading.Thread(target=scan_thread, daemon=True).start()
    
    # Auto-fix compatibility issues
    def remove_macos_resource_files(self):
        """Find and remove macOS resource files that start with ._ in the current directory"""
        if not self.current_dir:
            messagebox.showinfo("No Directory Selected", "Please open a directory first.")
            return
            
        # Ask for confirmation
        if not messagebox.askyesno("Confirm Deletion", 
                                "This will delete all macOS resource files (starting with ._) \n"
                                "in the current directory and subdirectories.\n\n"
                                "These files are not actual audio files but resource forks created by macOS.\n"
                                "Are you sure you want to continue?"):
            return
        
        # Find all files starting with ._ in the current directory and subdirectories
        resource_files = []
        for root, dirs, files in os.walk(self.current_dir):
            for filename in files:
                if filename.startswith("._"):
                    resource_files.append(os.path.join(root, filename))
        
        if not resource_files:
            messagebox.showinfo("No Files Found", "No macOS resource files were found.")
            return
        
        # Create progress dialog
        progress_window = tk.Toplevel(self)
        progress_window.title("Removing Resource Files")
        progress_window.geometry("400x150")
        progress_window.transient(self)
        progress_window.grab_set()
        
        progress_frame = ttk.Frame(progress_window, padding=20)
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        status_var = tk.StringVar(value=f"Found {len(resource_files)} resource files to delete")
        status_label = ttk.Label(progress_frame, textvariable=status_var)
        status_label.pack(fill=tk.X, pady=(0, 10))
        
        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=len(resource_files))
        progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Process files
        deleted_count = 0
        failed_count = 0
        failed_files = []
        
        for i, file_path in enumerate(resource_files):
            try:
                # Update progress
                filename = os.path.basename(file_path)
                status_var.set(f"Deleting: {filename}")
                progress_var.set(i + 1)
                progress_window.update_idletasks()
                
                # Delete the file
                os.remove(file_path)
                deleted_count += 1
            except Exception as e:
                failed_count += 1
                failed_files.append((file_path, str(e)))
        
        # Close progress dialog
        progress_window.destroy()
        
        # Show results
        if failed_count == 0:
            messagebox.showinfo("Deletion Complete", 
                              f"Successfully deleted {deleted_count} resource files.")
        else:
            result = f"Deleted: {deleted_count} files\nFailed: {failed_count} files\n\nFailed files:\n"
            for path, error in failed_files[:10]:  # Show first 10 failures
                result += f"- {os.path.basename(path)}: {error}\n"
            if len(failed_files) > 10:
                result += f"... and {len(failed_files) - 10} more"
            
            messagebox.showwarning("Deletion Results", result)
        
        # Refresh the directory view
        self.load_directory(self.current_dir)
    
    def auto_fix_compatibility(self):
        """Automatically fix common compatibility issues and file integrity problems"""
        if not hasattr(self, 'last_report_data') or not self.last_report_data:
            messagebox.showinfo("No Issues", "Please run a compatibility check first.")
            return
        
        fixed_count = 0
        skipped_count = 0
        integrity_fixed_count = 0
        
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
            integrity_fixed = False
            
            # Check for macOS resource files to delete
            if 'macOS resource file detected' in results['issues']:
                try:
                    os.remove(full_path)
                    messagebox.showinfo("File Deleted", 
                                     f"Deleted problematic macOS resource file:\n{os.path.basename(full_path)}")
                    # Refresh the directory view if needed
                    if self.current_dir:
                        self.load_directory(self.current_dir)
                    fixed_count += 1
                    continue  # Skip to next file since this one is deleted
                except Exception as e:
                    messagebox.showerror("Deletion Error", 
                                      f"Could not delete file {os.path.basename(full_path)}:\n{str(e)}")
                    skipped_count += 1
                    continue  # Skip to next file
            
            # Check for file integrity issues
            if self.compatibility_checker.perform_integrity_check.get() and 'integrity' in results:
                integrity_result = results['integrity']
                if integrity_result['status'] != "OK" and integrity_result.get('can_repair', False):
                    # Found repairable integrity issue
                    try:
                        repair_result = self.compatibility_checker.repair_file_integrity(full_path, integrity_result)
                        if repair_result.get('success', False):
                            messagebox.showinfo("Integrity Repair", 
                                             f"Successfully repaired file integrity for:\n{os.path.basename(full_path)}\n\nDetails: {repair_result.get('message', '')}")
                            integrity_fixed = True
                            integrity_fixed_count += 1
                        else:
                            messagebox.showwarning("Repair Failed", 
                                               f"Could not repair integrity of:\n{os.path.basename(full_path)}\n\nReason: {repair_result.get('message', 'Unknown error')}")
                    except Exception as e:
                        messagebox.showerror("Repair Error", 
                                          f"Error repairing file {os.path.basename(full_path)}:\n{str(e)}")
            
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
            elif integrity_fixed:
                # If only integrity was fixed, count as fixed
                fixed_count += 1
        
        # Show results
        if fixed_count > 0:
            integrity_msg = f" (including {integrity_fixed_count} with integrity issues)" if integrity_fixed_count > 0 else ""
            messagebox.showinfo("Auto-Fix Complete", 
                              f"Successfully fixed {fixed_count} files{integrity_msg}. {skipped_count} files could not be fixed automatically.")
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
                    # Get basic WAV info
                    audio = WAVE(file_path)
                    metadata.update({
                        'format': 'WAV',
                        'channels': audio.info.channels,
                        'sample_rate': audio.info.sample_rate,
                        'bits_per_sample': getattr(audio.info, 'bits_per_sample', 16),
                        'length': audio.info.length
                    })
                    
                    # Try to get INFO chunks from WAV (the standard WAV metadata format)
                    if hasattr(audio, 'tags'):
                        wav_tags = audio.tags
                        if wav_tags:
                            # Standard INFO chunk fields
                            if 'INAM' in wav_tags: metadata['title'] = wav_tags['INAM'][0]
                            if 'IART' in wav_tags: metadata['artist'] = wav_tags['IART'][0]
                            if 'IPRD' in wav_tags: metadata['album'] = wav_tags['IPRD'][0]
                            if 'ICRD' in wav_tags: metadata['date'] = wav_tags['ICRD'][0]
                            if 'IGNR' in wav_tags: metadata['genre'] = wav_tags['IGNR'][0]
                            if 'ICMT' in wav_tags: metadata['comment'] = wav_tags['ICMT'][0]
                    
                    # Some WAV files might also have ID3 tags (non-standard but common)
                    # Only try ID3 if we couldn't get valid tags from INFO chunks
                    if not any([metadata['title'], metadata['artist'], metadata['album']]):
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
                        except Exception:
                            # It's normal for WAV files to not have ID3 tags
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
                # First, try to write INFO chunks (standard for WAV files)
                try:
                    # Open the WAV file and try to add the INFO chunk
                    audio = WAVE(file_path)
                    # Check if we need to create tags
                    if not hasattr(audio, 'tags') or audio.tags is None:
                        audio.add_tags()
                    
                    # Map metadata to standard INFO chunk fields
                    if 'title' in metadata and metadata['title']: audio.tags['INAM'] = [metadata['title']]
                    if 'artist' in metadata and metadata['artist']: audio.tags['IART'] = [metadata['artist']]
                    if 'album' in metadata and metadata['album']: audio.tags['IPRD'] = [metadata['album']]
                    if 'date' in metadata and metadata['date']: audio.tags['ICRD'] = [metadata['date']]
                    if 'genre' in metadata and metadata['genre']: audio.tags['IGNR'] = [metadata['genre']]
                    if 'comment' in metadata and metadata['comment']: audio.tags['ICMT'] = [metadata['comment']]
                    
                    audio.save()
                except Exception as wav_error:
                    print(f"Warning: Could not write WAV INFO chunks: {str(wav_error)}")
                
                # Also add ID3 tags for broader compatibility
                try:
                    try:
                        id3 = ID3(file_path)
                    except:
                        # If no ID3 tags exist, create them
                        id3 = ID3()
                    
                    if 'title' in metadata and metadata['title']: id3['TIT2'] = TIT2(encoding=3, text=[metadata['title']])
                    if 'artist' in metadata and metadata['artist']: id3['TPE1'] = TPE1(encoding=3, text=[metadata['artist']])
                    if 'album' in metadata and metadata['album']: id3['TALB'] = TALB(encoding=3, text=[metadata['album']])
                    if 'date' in metadata and metadata['date']: id3['TDRC'] = TDRC(encoding=3, text=[metadata['date']])
                    if 'genre' in metadata and metadata['genre']: id3['TCON'] = TCON(encoding=3, text=[metadata['genre']])
                    if 'comment' in metadata and metadata['comment']: 
                        id3['COMM'] = COMM(encoding=3, lang='eng', desc='Comment', text=[metadata['comment']])
                    
                    id3.save(file_path)
                except Exception as id3_error:
                    print(f"Warning: Could not write WAV ID3 tags: {str(id3_error)}")
                
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