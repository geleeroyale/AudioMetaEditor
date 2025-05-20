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

class AudioMetadataEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # App configuration
        self.title("Audio Metadata Editor")
        self.geometry("1000x700")

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
        self.style.theme_use('clam')  # Use a theme that looks good on all platforms
        
        # Configure colors (dark theme)
        bg_color = "#2d2d2d"
        fg_color = "#e0e0e0"
        accent_color = "#3a7ebf"
        self.configure(background=bg_color)
        
        self.style.configure('TFrame', background=bg_color)
        self.style.configure('TLabel', background=bg_color, foreground=fg_color)
        self.style.configure('TButton', background=accent_color, foreground=fg_color)
        self.style.configure('Treeview', background=bg_color, foreground=fg_color, fieldbackground=bg_color)
        self.style.map('Treeview', background=[('selected', accent_color)])
        
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
        
        # Status bar
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_menu(self):
        """Create the application menu"""
        menubar = tk.Menu(self)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Directory...", command=self.browse_directory, accelerator="Ctrl+O")
        file_menu.add_command(label="Save Metadata", command=self.save_metadata, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        self.tools_menu = tools_menu
        tools_menu.add_command(label="Batch Edit...", command=self.batch_edit, state=tk.DISABLED)
        self.batch_edit_menu_item_index = tools_menu.index(tk.END) # Get index of the last added item
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.config(menu=menubar)
        self.update_batch_edit_menu_state() # Initial state update
    
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
        file_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Define columns: Checkbox, Filename, Format, Duration
        columns = ("checked", "filename", "format", "duration")
        self.file_tree = ttk.Treeview(file_frame, columns=columns, show="headings", selectmode="browse") # selectmode browse for single active row
        
        scrollbar = ttk.Scrollbar(file_frame, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=scrollbar.set)
        
        self.file_tree.heading("checked", text="")
        self.file_tree.heading("filename", text="File Name")
        self.file_tree.heading("format", text="Format")
        self.file_tree.heading("duration", text="Duration")
        
        self.file_tree.column("checked", width=30, anchor=tk.CENTER, stretch=tk.NO)
        self.file_tree.column("filename", width=250, stretch=tk.YES)
        self.file_tree.column("format", width=80, anchor=tk.W)
        self.file_tree.column("duration", width=80, anchor=tk.W)

        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind left-click to handle checkbox toggle and row selection for metadata display
        self.file_tree.bind("<Button-1>", self.on_tree_click)
        
        # Right panel - metadata editor
        metadata_frame = ttk.LabelFrame(main_frame, text="Metadata")
        # Use pack for metadata_frame as browser_frame (its sibling in main_frame) uses pack.
        metadata_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Split into file info and editable metadata
        metadata_frame.columnconfigure(0, weight=1)
        metadata_frame.rowconfigure(0, weight=0)  # File info
        metadata_frame.rowconfigure(1, weight=1)  # Editable metadata
        
        # File information panel
        info_frame = ttk.LabelFrame(metadata_frame, text="File Information")
        info_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill=tk.X, padx=10, pady=10)
        
        # File info grid layout
        info_grid.columnconfigure(0, weight=0)
        info_grid.columnconfigure(1, weight=1)
        
        # File info labels
        ttk.Label(info_grid, text="File:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.file_label = ttk.Label(info_grid, text="-")
        self.file_label.grid(row=0, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_grid, text="Format:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.format_label = ttk.Label(info_grid, text="-")
        self.format_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_grid, text="Channels:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.channels_label = ttk.Label(info_grid, text="-")
        self.channels_label.grid(row=2, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_grid, text="Sample Rate:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.sample_rate_label = ttk.Label(info_grid, text="-")
        self.sample_rate_label.grid(row=3, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_grid, text="Bit Depth/Rate:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.bit_depth_label = ttk.Label(info_grid, text="-")
        self.bit_depth_label.grid(row=4, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(info_grid, text="Duration:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.duration_label = ttk.Label(info_grid, text="-")
        self.duration_label.grid(row=5, column=1, sticky=tk.W, pady=2)
        
        # Metadata editor form
        form_frame = ttk.Frame(metadata_frame)
        form_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        form_frame.columnconfigure(0, weight=0)
        form_frame.columnconfigure(1, weight=1)
        
        # Metadata form fields
        ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.title_var).grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Artist:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.artist_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.artist_var).grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Album:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.album_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.album_var).grid(row=2, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Year/Date:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.date_var).grid(row=3, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Genre:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.genre_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.genre_var).grid(row=4, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(form_frame, text="Comment:").grid(row=5, column=0, sticky=tk.NW, pady=5)
        self.comment_var = tk.StringVar()
        self.comment_text = ScrolledText(form_frame, height=5, width=30)
        self.comment_text.grid(row=5, column=1, sticky=tk.EW, pady=5, padx=5)
        
        # Add some vertical space
        ttk.Frame(form_frame).grid(row=6, column=0, pady=10)
        
        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW)
        
        save_btn = ttk.Button(btn_frame, text="Save Changes", command=self.save_metadata)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        revert_btn = ttk.Button(btn_frame, text="Revert Changes", command=self.load_metadata)
        revert_btn.pack(side=tk.LEFT, padx=5)
    
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
    
    def load_directory(self, dir_path):
        """Load all audio files from the specified directory"""
        self.status_var.set(f"Loading files from {dir_path}...")
        self.update_idletasks()
        
        # Clear current file list
        self.file_tree.delete(*self.file_tree.get_children())
        self.files_list = []
        
        try:
            # Find all audio files in the directory
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                if os.path.isfile(file_path):
                    file_ext = os.path.splitext(filename)[1].lower()
                    if file_ext in self.supported_formats:
                        self.files_list.append(file_path)
            
            # Sort files alphabetically
            self.files_list.sort(key=lambda x: os.path.basename(x).lower())
            
            self.populate_file_tree(self.files_list)
            
            num_files = len(self.files_list)
            self.status_var.set(f"Loaded {num_files} audio file{'s' if num_files != 1 else ''}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading directory: {str(e)}")
            self.status_var.set("Error loading directory")
    
    def populate_file_tree(self, files):
        self.file_tree.delete(*self.file_tree.get_children())
        self.files_list = files
        self.checked_files_state.clear()
        checked_symbol = "[✔]" # Or 
        unchecked_symbol = "[ ]" # Or 

        for file_path in files:
            self.checked_files_state[file_path] = False # Initialize as unchecked
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
                                  values=(unchecked_symbol, display_name, fmt, dur))
        
        self.update_batch_edit_menu_state()
        if files:
            self.status_var.set(f"Loaded {len(files)} files.")
        else:
            self.status_var.set("No audio files found in the selected directory.")
    
    def update_batch_edit_menu_state(self):
        """Enable/disable batch edit menu based on checked files."""
        if hasattr(self, 'tools_menu') and self.batch_edit_menu_item_index is not None:
            any_checked = any(self.checked_files_state.values())
            if any_checked:
                self.tools_menu.entryconfigure(self.batch_edit_menu_item_index, state=tk.NORMAL)
            else:
                self.tools_menu.entryconfigure(self.batch_edit_menu_item_index, state=tk.DISABLED)

    def on_tree_click(self, event):
        """Handle clicks on the Treeview for checkbox toggling and row selection."""
        region = self.file_tree.identify_region(event.x, event.y)
        column_id = self.file_tree.identify_column(event.x)
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
            
            self.update_batch_edit_menu_state()
        
        # Always treat a click on a row (even checkbox) as a selection for metadata display
        # This simplifies logic from <<TreeviewSelect>> which is harder with checkboxes
        if item_id != self.current_file:
            self.current_file = item_id
            self.load_metadata()
        
        # Ensure the clicked row gets focus/selection highlight if desired by selectmode
        if self.file_tree.selection() != (item_id,):
             self.file_tree.selection_set(item_id)

    def load_metadata(self):
        """Load metadata from the selected audio file"""
        if not self.current_file:
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
    
    def save_metadata(self):
        """Save metadata changes to the audio file"""
        if not self.current_file:
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
                self.current_metadata.update(metadata)
            else:
                error_message = result.get('message', 'Unknown error')
                messagebox.showerror("Error", f"Failed to save metadata: {error_message}")
                self.status_var.set("Error saving metadata")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error saving metadata: {str(e)}")
            self.status_var.set("Error saving metadata")
    
    def batch_edit(self):
        """Open batch editing dialog for files marked as checked."""
        files_to_process = [fp for fp, checked in self.checked_files_state.items() if checked]

        if not files_to_process:
            messagebox.showinfo("Info", "No files checked. Please check files in the list to batch edit.")
            return

        # Create batch edit dialog
        dialog = tk.Toplevel(self)
        dialog.title(f"Batch Edit Metadata ({len(files_to_process)} files)")
        dialog.geometry("600x450") # Increased height to ensure buttons are visible
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Configure grid layout for the dialog itself
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=0)  # Instructional Label
        dialog.rowconfigure(1, weight=1)  # Main form frame (for fields, should expand)
        dialog.rowconfigure(2, weight=0)  # Button frame

        # Dialog content
        info_label = ttk.Label(dialog, text="Tick fields to update and enter new values:")
        info_label.grid(row=0, column=0, sticky=tk.W, padx=10, pady=(10, 5))
        
        batch_vars = {}
        fields_config = [
            ('title', 'Title'), 
            ('artist', 'Artist'), 
            ('album', 'Album'),
            ('date', 'Year/Date'),
            ('genre', 'Genre'),
            ('comment', 'Comment')
        ]
        
        # Frame for checkboxes and entries
        main_form_frame = ttk.Frame(dialog)
        main_form_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=5)

        # Configure grid inside main_form_frame (this part was already using grid and seems fine)
        main_form_frame.columnconfigure(0, weight=0) # Checkbox for field
        main_form_frame.columnconfigure(1, weight=0) # Label for field
        main_form_frame.columnconfigure(2, weight=1) # Entry for field value

        entry_values = {}

        for i, (field_key, field_label) in enumerate(fields_config):
            var = tk.BooleanVar(value=False)
            batch_vars[field_key] = var
            ttk.Checkbutton(main_form_frame, variable=var).grid(
                row=i, column=0, sticky=tk.W, padx=(0,2), pady=5)
            
            ttk.Label(main_form_frame, text=f"{field_label}:").grid(
                row=i, column=1, sticky=tk.W, padx=(0,5), pady=5)
            
            if field_key == 'comment':
                text_widget = ScrolledText(main_form_frame, height=3, width=30, relief=tk.SOLID, borderwidth=1)
                text_widget.grid(row=i, column=2, sticky='ew', pady=5, padx=(0,5))
                entry_values[field_key] = text_widget
            else:
                entry_var = tk.StringVar()
                ttk.Entry(main_form_frame, textvariable=entry_var).grid(
                    row=i, column=2, sticky='ew', pady=5, padx=(0,5))
                entry_values[field_key] = entry_var
            
        # Button frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, sticky='ew', padx=10, pady=(10,15))
        # Configure button frame grid to push buttons to the right
        btn_frame.columnconfigure(0, weight=1) # Spacer to push buttons to the right
        btn_frame.columnconfigure(1, weight=0) # Cancel button
        btn_frame.columnconfigure(2, weight=0) # Apply button
        
        def on_apply():
            fields_to_update_values = {}
            any_field_selected = False
            for field_key, checkbox_var in batch_vars.items():
                if checkbox_var.get():
                    any_field_selected = True
                    if field_key == 'comment':
                        value = entry_values[field_key].get(1.0, tk.END).strip()
                    else:
                        value = entry_values[field_key].get()
                    fields_to_update_values[field_key] = value
            
            if not any_field_selected:
                messagebox.showinfo("Info", "No fields selected to update. Please tick the checkbox next to the fields you want to change.", parent=dialog)
                return
            
            if not messagebox.askyesno("Confirm Batch Update", 
                                      f"This will modify metadata for {len(files_to_process)} selected file(s) based on the ticked fields. Continue?", parent=dialog):
                return
            
            self.status_var.set(f"Batch updating {len(files_to_process)} files...")
            self.update_idletasks()

            success_count = 0
            failed_files_details = []
            
            dialog.destroy() # Close dialog before starting long operation

            def _process_batch():
                nonlocal success_count, failed_files_details
                for file_path in files_to_process:
                    try:
                        current_metadata = self.read_metadata(file_path)
                        if 'error' in current_metadata and not files_to_process: # If read error, report it unless it's expected (e.g. dummy file)
                           failed_files_details.append((os.path.basename(file_path), f"Initial read failed: {current_metadata['error']}"))
                           continue

                        metadata_to_write = current_metadata.copy()
                        
                        for field_key, new_value in fields_to_update_values.items():
                            if batch_vars[field_key].get(): 
                                metadata_to_write[field_key] = new_value
                        
                        result = self.write_metadata(file_path, metadata_to_write)
                        if result.get('success', False):
                            success_count += 1
                        else:
                            failed_files_details.append((os.path.basename(file_path), result.get('error', 'Unknown write error')))
                    except Exception as e:
                        failed_files_details.append((os.path.basename(file_path), str(e)))
                
                self.after(0, _show_batch_results, success_count, failed_files_details, len(files_to_process))

            def _show_batch_results(s_count, f_details, total_files):
                if f_details:
                    error_message_parts = [f"{name}: {err}" for name, err in f_details[:10]]
                    error_message_str = "\n".join(error_message_parts)
                    if len(f_details) > 10:
                        error_message_str += f"\n... and {len(f_details) - 10} more"
                    messagebox.showwarning("Batch Edit Results", 
                                         f"Updated {s_count} of {total_files} files.\n\nFailed files:\n{error_message_str}", parent=self)
                else:
                    messagebox.showinfo("Batch Edit Results", 
                                       f"Successfully updated metadata for {s_count} file(s).", parent=self)
                
                self.status_var.set(f"Batch edit complete. Updated {s_count}/{total_files} files.")
                if self.current_file in files_to_process:
                     self.load_metadata() 

            threading.Thread(target=_process_batch, daemon=True).start()

        apply_btn = ttk.Button(btn_frame, text="Apply Changes to Selected Files", command=on_apply)
        apply_btn.grid(row=0, column=2, sticky=tk.E, padx=(5,0))
        
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=dialog.destroy)
        cancel_btn.grid(row=0, column=1, sticky=tk.E, padx=5)  # Place cancel button to the left of apply

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.wait_window() 
    
    def show_about(self):
        """Show about dialog"""
        about_text = """Audio Metadata Editor

A desktop application for editing metadata in audio files.

Supported formats:
- FLAC
- MP3
- WAV
- AAF (limited support)

Version 1.0
"""
        messagebox.showinfo("About", about_text)
    
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
    app = AudioMetadataEditor()
    app.mainloop()