#!/usr/bin/env python3
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import time
from typing import Dict, List, Optional, Tuple

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
        self.geometry("1024x700")
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
        self.current_file = None
        self.files_list = []
        self.current_metadata = {}
        self.supported_formats = ['.flac', '.mp3', '.wav', '.aaf']
        
        # Main layout
        self.create_menu()
        self.create_layout()
        
        # Bind events
        self.bind("<Control-o>", lambda e: self.browse_directory())
        self.bind("<Control-s>", lambda e: self.save_metadata())
        
        # Status variables
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        
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
        tools_menu.add_command(label="Batch Edit...", command=self.batch_edit)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.config(menu=menubar)
    
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
        browser_frame = ttk.LabelFrame(main_frame, text="Audio Files")
        browser_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
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
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(file_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview for files
        self.file_tree = ttk.Treeview(file_frame, columns=("format", "duration"), 
                                        yscrollcommand=scrollbar.set, selectmode="browse")
        self.file_tree.heading("#0", text="Filename")
        self.file_tree.heading("format", text="Format")
        self.file_tree.heading("duration", text="Duration")
        
        self.file_tree.column("#0", width=200, minwidth=150)
        self.file_tree.column("format", width=80, minwidth=50, anchor=tk.CENTER)
        self.file_tree.column("duration", width=80, minwidth=50, anchor=tk.CENTER)
        
        self.file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.file_tree.yview)
        
        # Bind selection event
        self.file_tree.bind("<<TreeviewSelect>>", self.on_file_select)
        
        # Right panel - metadata editor
        metadata_frame = ttk.LabelFrame(main_frame, text="Metadata")
        metadata_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
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
            
            # Populate the tree with file information
            for file_path in self.files_list:
                filename = os.path.basename(file_path)
                file_ext = os.path.splitext(filename)[1].lower()
                
                # Get basic info without full metadata load for speed
                format_name = file_ext[1:].upper()
                duration = "-"
                
                try:
                    # Quick load just to get duration
                    audio = mutagen.File(file_path)
                    if audio and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                        mins = int(audio.info.length / 60)
                        secs = int(audio.info.length % 60)
                        duration = f"{mins}:{secs:02d}"
                except:
                    pass
                
                self.file_tree.insert("", "end", text=filename, values=(format_name, duration))
            
            num_files = len(self.files_list)
            self.status_var.set(f"Loaded {num_files} audio file{'s' if num_files != 1 else ''}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading directory: {str(e)}")
            self.status_var.set("Error loading directory")
    
    def on_file_select(self, event):
        """Handle file selection from the tree view"""
        selection = self.file_tree.selection()
        if selection:
            item_id = selection[0]
            file_index = self.file_tree.index(item_id)
            if 0 <= file_index < len(self.files_list):
                self.current_file = self.files_list[file_index]
                self.load_metadata()
    
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
        """Open batch editing dialog"""
        if not self.files_list:
            messagebox.showinfo("Info", "No files loaded. Please open a directory first.")
            return
        
        # Create batch edit dialog
        dialog = tk.Toplevel(self)
        dialog.title("Batch Edit Metadata")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()
        
        # Dialog content
        ttk.Label(dialog, text="Select fields to batch edit:").pack(pady=10, padx=10, anchor=tk.W)
        
        # Checkbuttons for fields
        batch_vars = {}
        fields = [
            ('title', 'Title'), 
            ('artist', 'Artist'), 
            ('album', 'Album'),
            ('date', 'Year/Date'),
            ('genre', 'Genre'),
            ('comment', 'Comment')
        ]
        
        # Checkbox frame
        check_frame = ttk.Frame(dialog)
        check_frame.pack(fill=tk.X, padx=10, pady=5)
        
        for i, (field, label) in enumerate(fields):
            var = tk.BooleanVar(value=False)
            batch_vars[field] = var
            ttk.Checkbutton(check_frame, text=label, variable=var).grid(
                row=i//3, column=i%3, sticky=tk.W, padx=5, pady=5)
        
        # Value entry frame
        entry_frame = ttk.Frame(dialog)
        entry_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        entry_values = {}
        for i, (field, label) in enumerate(fields):
            ttk.Label(entry_frame, text=f"{label}:").grid(row=i, column=0, sticky=tk.W, pady=5)
            
            if field == 'comment':
                text = ScrolledText(entry_frame, height=4, width=40)
                text.grid(row=i, column=1, sticky=tk.EW, pady=5)
                entry_values[field] = text
            else:
                var = tk.StringVar()
                ttk.Entry(entry_frame, textvariable=var).grid(row=i, column=1, sticky=tk.EW, pady=5)
                entry_values[field] = var
        
        # Files selection
        ttk.Label(dialog, text="Apply to:").pack(pady=(10,0), padx=10, anchor=tk.W)
        
        file_selection_var = tk.StringVar(value="all")
        ttk.Radiobutton(dialog, text="All files", variable=file_selection_var, 
                       value="all").pack(pady=2, padx=20, anchor=tk.W)
        ttk.Radiobutton(dialog, text="Selected file only", variable=file_selection_var, 
                       value="selected").pack(pady=2, padx=20, anchor=tk.W)
        
        # Button frame
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=tk.X, pady=15, padx=10)
        
        def on_apply():
            # Get selected fields and values
            fields_to_update = {}
            for field, var in batch_vars.items():
                if var.get():
                    if field == 'comment':
                        value = entry_values[field].get(1.0, tk.END).strip()
                    else:
                        value = entry_values[field].get()
                    fields_to_update[field] = value
            
            if not fields_to_update:
                messagebox.showinfo("Info", "No fields selected for batch edit.")
                return
            
            # Determine which files to update
            files_to_update = []
            if file_selection_var.get() == "all":
                files_to_update = self.files_list
            elif file_selection_var.get() == "selected" and self.current_file:
                files_to_update = [self.current_file]
            
            if not files_to_update:
                messagebox.showinfo("Info", "No files selected for batch edit.")
                return
            
            # Confirm
            if not messagebox.askyesno("Confirm", 
                                      f"This will modify metadata for {len(files_to_update)} file(s). Continue?"):
                return
            
            # Apply changes
            success_count = 0
            failed_files = []
            
            for file_path in files_to_update:
                try:
                    # Read existing metadata first
                    current = self.read_metadata(file_path)
                    # Update with new values
                    current.update(fields_to_update)
                    # Write back
                    result = self.write_metadata(file_path, current)
                    if result.get('success', False):
                        success_count += 1
                    else:
                        failed_files.append(os.path.basename(file_path))
                except Exception as e:
                    failed_files.append(f"{os.path.basename(file_path)} ({str(e)})")
            
            # Show results
            if failed_files:
                error_message = "\n".join(failed_files[:10])
                if len(failed_files) > 10:
                    error_message += f"\n... and {len(failed_files) - 10} more"
                messagebox.showwarning("Batch Edit Results", 
                                     f"Updated {success_count} of {len(files_to_update)} files.\n\nFailed files:\n{error_message}")
            else:
                messagebox.showinfo("Batch Edit Results", 
                                   f"Successfully updated metadata for {success_count} file(s).")
            
            # Close dialog
            dialog.destroy()
            
            # Refresh current file view if it was updated
            if self.current_file in files_to_update:
                self.load_metadata()
        
        ttk.Button(btn_frame, text="Apply", command=on_apply).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
    
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
            metadata = {}
            
            if file_ext == '.flac':
                audio = FLAC(file_path)
                metadata = {
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
                }
                
            elif file_ext == '.mp3':
                audio = MP3(file_path)
                id3 = ID3(file_path) if audio.tags else None
                
                metadata = {
                    'title': id3.get('TIT2', TIT2(encoding=3, text=[''])).text[0] if id3 and 'TIT2' in id3 else '',
                    'artist': id3.get('TPE1', TPE1(encoding=3, text=[''])).text[0] if id3 and 'TPE1' in id3 else '',
                    'album': id3.get('TALB', TALB(encoding=3, text=[''])).text[0] if id3 and 'TALB' in id3 else '',
                    'date': str(id3.get('TDRC', TDRC(encoding=3, text=[''])).text[0]) if id3 and 'TDRC' in id3 else '',
                    'genre': str(id3.get('TCON', TCON(encoding=3, text=[''])).text[0]) if id3 and 'TCON' in id3 else '',
                    'comment': id3.get('COMM', COMM(encoding=3, text=[''])).text[0] if id3 and 'COMM' in id3 else '',
                    'format': 'MP3',
                    'channels': audio.info.channels,
                    'sample_rate': audio.info.sample_rate,
                    'bitrate': audio.info.bitrate,
                    'length': audio.info.length
                }
                
            elif file_ext == '.wav':
                audio = WAVE(file_path)
                metadata = {
                    'title': '',
                    'artist': '',
                    'album': '',
                    'date': '',
                    'genre': '',
                    'comment': '',
                    'format': 'WAV',
                    'channels': audio.info.channels,
                    'sample_rate': audio.info.sample_rate,
                    'bits_per_sample': getattr(audio.info, 'bits_per_sample', 0),
                    'length': audio.info.length
                }
                
                # Try to get ID3 tags if available in WAV
                try:
                    id3 = ID3(file_path)
                    metadata.update({
                        'title': id3.get('TIT2', TIT2(encoding=3, text=[''])).text[0] if 'TIT2' in id3 else '',
                        'artist': id3.get('TPE1', TPE1(encoding=3, text=[''])).text[0] if 'TPE1' in id3 else '',
                        'album': id3.get('TALB', TALB(encoding=3, text=[''])).text[0] if 'TALB' in id3 else '',
                        'date': str(id3.get('TDRC', TDRC(encoding=3, text=[''])).text[0]) if 'TDRC' in id3 else '',
                        'genre': str(id3.get('TCON', TCON(encoding=3, text=[''])).text[0]) if 'TCON' in id3 else '',
                        'comment': id3.get('COMM', COMM(encoding=3, text=[''])).text[0] if 'COMM' in id3 else ''
                    })
                except:
                    # WAV may not have ID3 tags, just continue
                    pass
                    
            elif file_ext == '.aaf':
                # AAF handling is more complex, this is a simplified approach
                metadata = {
                    'title': '',
                    'artist': '',
                    'album': '',
                    'date': '',
                    'genre': '',
                    'comment': '',
                    'format': 'AAF',
                    'length': 0,
                    'note': 'AAF metadata extraction requires specialized libraries'
                }
                
                # Try to use mutagen to extract any available metadata
                try:
                    audio = mutagen.File(file_path)
                    if audio and hasattr(audio, 'info'):
                        metadata['length'] = audio.info.length
                except:
                    print(f"Could not extract AAF metadata with mutagen for {file_path}")
            
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