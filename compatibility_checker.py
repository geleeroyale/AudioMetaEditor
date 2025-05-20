#!/usr/bin/env python3
"""
Compatibility Checker - Generic Strict Profile
This module provides functions to validate audio file metadata against 
the Generic Strict Profile for maximum compatibility with various players.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

# Import required audio processing libraries
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.wave import WAVE
from mutagen.mp3 import MP3

class CompatibilityChecker:
    def __init__(self, parent):
        """Initialize the compatibility checker with a parent application"""
        self.parent = parent
        
    def check_compatibility(self, files_to_check, metadata_reader):
        """Check compatibility of files against the Generic Strict Profile
        
        Args:
            files_to_check: List of file paths to check
            metadata_reader: Function to read metadata from files
            
        Returns:
            tuple: (report_data, total_issues)
        """
        report_data = []
        total_issues = 0
        
        for file_path in files_to_check:
            metadata = metadata_reader(file_path)
            results = self.validate_strict_profile(file_path, metadata)
            report_data.append((os.path.basename(file_path), results))
            total_issues += len(results['issues'])
            
        return report_data, total_issues
    
    def validate_strict_profile(self, file_path, metadata):
        """Validate metadata against the Generic Strict Profile
        
        Args:
            file_path: Path to the audio file
            metadata: Dictionary containing metadata information
            
        Returns:
            dict: Results containing issues, warnings, recommendations and format info
        """
        issues = []
        warnings = []
        recommendations = []
        format_info = {}
        
        # Get file basename and extension
        file_basename = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Check for problematic macOS resource files
        if file_basename.startswith("._"):
            issues.append("macOS resource file detected")
            recommendations.append("These hidden resource files are not actual audio files and should be deleted")
        
        # Check common issues across all formats
        if not metadata.get('title', '').strip():
            issues.append("Missing title tag")
            recommendations.append("Add a title to improve compatibility")
        
        if not metadata.get('artist', '').strip():
            issues.append("Missing artist tag")
            recommendations.append("Add an artist name to improve compatibility")
        
        # Check for overly long metadata fields
        max_field_length = 250
        for field in ['title', 'artist', 'album']:
            if len(metadata.get(field, '')) > max_field_length:
                issues.append(f"{field.capitalize()} tag exceeds {max_field_length} characters")
                recommendations.append(f"Shorten {field} to improve compatibility with older players")
        
        # Format-specific checks
        if file_ext == '.mp3':
            # MP3 specific checks
            try:
                audio = MP3(file_path)
                format_info['bitrate'] = audio.info.bitrate
                format_info['sample_rate'] = audio.info.sample_rate
                format_info['length'] = audio.info.length
                
                # Check for uncommon bitrates
                if audio.info.bitrate < 128000 or audio.info.bitrate > 320000:
                    warnings.append(f"Uncommon bitrate: {audio.info.bitrate//1000}kbps")
                    recommendations.append("Standard compatible bitrates: 128kbps, 192kbps, 256kbps, 320kbps")
                
                # Check ID3 version
                try:
                    id3 = ID3(file_path)
                    format_info['id3_version'] = f"{id3.version[0]}.{id3.version[1]}"
                    
                    # Check for ID3v1 only
                    if id3.version[0] < 2:
                        warnings.append("Using ID3v1 tags which have limited support")
                        recommendations.append("Upgrade to ID3v2.3 or ID3v2.4 for better compatibility")
                except Exception:
                    issues.append("No ID3 tags found or corrupted tags")
                    recommendations.append("Add proper ID3v2.3 tags for maximum compatibility")
                    
            except Exception as e:
                issues.append(f"Error analyzing MP3 file: {str(e)}")
                
        elif file_ext == '.flac':
            # FLAC specific checks
            try:
                audio = FLAC(file_path)
                format_info['sample_rate'] = audio.info.sample_rate
                format_info['bits_per_sample'] = audio.info.bits_per_sample
                format_info['channels'] = audio.info.channels
                
                # Check for very high sample rates
                if audio.info.sample_rate > 48000:
                    warnings.append(f"High sample rate: {audio.info.sample_rate}Hz")
                    recommendations.append("Sample rates above 48kHz may not be supported by all players")
                
                # Check for very high bit depth
                if audio.info.bits_per_sample > 24:
                    warnings.append(f"High bit depth: {audio.info.bits_per_sample}-bit")
                    recommendations.append("Bit depths above 24-bit may not be supported by all players")
                    
                # Check for uncommon channel configurations
                if audio.info.channels > 2:
                    warnings.append(f"Multichannel audio: {audio.info.channels} channels")
                    recommendations.append("More than 2 channels may not be supported by all players")
                    
            except Exception as e:
                issues.append(f"Error analyzing FLAC file: {str(e)}")
                
        elif file_ext == '.wav':
            # WAV specific checks
            try:
                audio = WAVE(file_path)
                format_info['sample_rate'] = audio.info.sample_rate
                format_info['bits_per_sample'] = getattr(audio.info, 'bits_per_sample', 16)
                format_info['channels'] = audio.info.channels
                
                # Missing metadata is normal in WAV files - don't flag as issues but as warnings
                # Remove any "Missing title tag" or "Missing artist tag" from issues list
                for issue in list(issues):
                    if issue in ["Missing title tag", "Missing artist tag"]:
                        issues.remove(issue)
                        warnings.append(issue + " (normal for WAV files)")
                
                # Add specific WAV format note
                if not any([metadata.get('title'), metadata.get('artist'), metadata.get('album')]):
                    warnings.append("WAV file has no metadata (this is normal for WAV files)")
                    recommendations.append("WAV files typically have limited or no metadata support in most players")
                else:
                    recommendations.append("Some players may not display the metadata in this WAV file")
                
                # Check for non-standard sampling rates
                if audio.info.sample_rate not in [44100, 48000]:
                    warnings.append(f"Uncommon sample rate: {audio.info.sample_rate}Hz")
                    recommendations.append("Standard sample rates of 44.1kHz or 48kHz have the best compatibility")
                    
                # Check for high bit-depth
                if format_info['bits_per_sample'] > 16:
                    warnings.append(f"High bit depth: {format_info['bits_per_sample']}-bit")
                    recommendations.append("Bit depths above 16-bit may not be supported by all players")
                    
                # Check for multichannel
                if audio.info.channels > 2:
                    warnings.append(f"Multichannel audio: {audio.info.channels} channels")
                    recommendations.append("More than 2 channels may not be supported by all players")
                    
                # Check for INFO chunks
                has_info_chunks = False
                if hasattr(audio, 'tags') and audio.tags:
                    has_info_chunks = True
                    format_info['has_info_chunks'] = True
                    
                # Check for ID3 tags
                has_id3 = False
                try:
                    id3 = ID3(file_path)
                    if id3:
                        has_id3 = True
                        format_info['has_id3'] = True
                except Exception:
                    pass
                    
                if has_info_chunks and has_id3:
                    # Both metadata formats present
                    format_info['metadata_type'] = "INFO chunks + ID3"
                elif has_info_chunks:
                    format_info['metadata_type'] = "INFO chunks only"
                elif has_id3:
                    format_info['metadata_type'] = "ID3 only (non-standard)"
                    warnings.append("WAV file using non-standard ID3 tags")
                    recommendations.append("Some players may not recognize ID3 tags in WAV files")
                else:
                    format_info['metadata_type'] = "No metadata"
                    
            except Exception as e:
                issues.append(f"Error analyzing WAV file: {str(e)}")
                recommendations.append("The WAV file may be corrupted or using a non-standard format")
        
        # Return results
        return {
            'issues': issues,
            'warnings': warnings,
            'recommendations': recommendations,
            'format_info': format_info
        }
    
    def fix_metadata(self, file_path, field, value, list_index, listbox, fixed_status):
        """Fix a specific metadata field in a file
        
        Args:
            file_path: Path to the file to fix
            field: Metadata field to update
            value: New value for the field
            list_index: Index in the listbox
            listbox: The listbox widget
            fixed_status: Dictionary tracking fixed status
        """
        # Get current metadata
        metadata = self.parent.read_metadata(file_path)
        if 'error' in metadata:
            messagebox.showerror("Error", f"Could not read metadata: {metadata['error']}")
            return
        
        # Update the field
        metadata[field] = value
        
        # Write back to the file
        result = self.parent.write_metadata(file_path, metadata)
        
        if result.get('success', False):
            # Mark as fixed
            fixed_status[list_index] = True
            
            # Update listbox display
            filename = os.path.basename(file_path)
            current_text = listbox.get(list_index)
            if "❌" in current_text:
                # Decrease issue count or mark as fixed
                issue_text = current_text.split("❌")[1].strip()
                count_text = issue_text.split(" ")[0]
                try:
                    count = int(count_text)
                    if count > 1:
                        new_text = f"{filename} - ❌ {count-1} issues"
                        listbox.delete(list_index)
                        listbox.insert(list_index, new_text)
                        listbox.itemconfig(list_index, fg=self.parent.error_color)
                    else:
                        new_text = f"{filename} - ✓ Fixed"
                        listbox.delete(list_index)
                        listbox.insert(list_index, new_text)
                        listbox.itemconfig(list_index, fg=self.parent.success_color)
                except ValueError:
                    # Fallback if parsing fails
                    new_text = f"{filename} - ✓ Fixed"
                    listbox.delete(list_index)
                    listbox.insert(list_index, new_text)
                    listbox.itemconfig(list_index, fg=self.parent.success_color)
            
            # Re-select the item
            listbox.selection_set(list_index)
            
            # Update current display
            listbox.event_generate("<<ListboxSelect>>")
            
            # Update status
            self.parent.status_var.set(f"Fixed {field} in {filename}")
            
            # Refresh metadata if this is the currently loaded file
            if self.parent.current_file == file_path:
                self.parent.load_metadata()
        else:
            messagebox.showerror("Error", f"Failed to update metadata: {result.get('message', 'Unknown error')}")

    def apply_all_fixes(self, report_data, listbox, fixed_status):
        """Apply automatic fixes to all issues
        
        Args:
            report_data: List of tuples (filename, results) with compatibility information
            listbox: The listbox widget
            fixed_status: Dictionary tracking fixed status
        """
        fixed_count = 0
        skipped_count = 0
        
        for index, (filename, results) in enumerate(report_data):
            # Skip already fixed or files without issues
            if fixed_status[index] or not results['issues']:
                continue
                
            # Find the full path
            full_path = None
            for path in self.parent.checked_files_state.keys():
                if os.path.basename(path) == filename:
                    full_path = path
                    break
                    
            if not full_path:
                skipped_count += 1
                continue
                
            # Get metadata
            metadata = self.parent.read_metadata(full_path)
            if 'error' in metadata:
                skipped_count += 1
                continue
                
            updates_made = False
                
            # Process issues
            for issue in results['issues']:
                if "Missing title tag" in issue:
                    # Extract title from filename
                    suggested_title = os.path.splitext(filename)[0]
                    # Clean up title
                    suggested_title = suggested_title.replace('_', ' ').replace('-', ' - ')
                    metadata['title'] = suggested_title
                    updates_made = True
                    
                elif "Missing artist tag" in issue:
                    # Try to extract artist from filename or use Unknown Artist
                    parts = filename.split(' - ', 1)
                    if len(parts) > 1:
                        suggested_artist = parts[0].strip()
                    else:
                        suggested_artist = "Unknown Artist"
                    metadata['artist'] = suggested_artist
                    updates_made = True
                    
                elif "tag exceeds" in issue:
                    # Extract field name and trim
                    field = issue.split(' ')[0].lower()
                    if field in metadata:
                        metadata[field] = metadata[field][:250]
                        updates_made = True
            
            # Apply updates if any were made
            if updates_made:
                result = self.parent.write_metadata(full_path, metadata)
                if result.get('success', False):
                    fixed_count += 1
                    fixed_status[index] = True
                    
                    # Update listbox display
                    new_text = f"{filename} - ✓ Fixed"
                    listbox.delete(index)
                    listbox.insert(index, new_text)
                    listbox.itemconfig(index, fg=self.parent.success_color)
                else:
                    skipped_count += 1
    
        # Show results
        messagebox.showinfo("Auto-Fix Complete", 
                          f"Successfully fixed {fixed_count} files. {skipped_count} files could not be fixed automatically.")
        
        # Refresh current file if it was modified
        if self.parent.current_file:
            self.parent.load_metadata()
        
        # Update the display
        if listbox.curselection():
            listbox.event_generate("<<ListboxSelect>>")

    def delete_file(self, file_path, list_index, listbox, fixed_status):
        """Delete a file (used for macOS resource files)
        
        Args:
            file_path: Path to the file to delete
            list_index: Index in the listbox
            listbox: The listbox widget
            fixed_status: Dictionary tracking fixed status
        """
        try:
            # Delete the file
            os.remove(file_path)
            
            # Mark as fixed
            fixed_status[list_index] = True
            
            # Update listbox display
            filename = os.path.basename(file_path)
            new_text = f"{filename} - ✓ Deleted"
            listbox.delete(list_index)
            listbox.insert(list_index, new_text)
            listbox.itemconfig(list_index, fg=self.parent.success_color)
            
            # Re-select the item
            listbox.selection_set(list_index)
            
            # Update status
            self.parent.status_var.set(f"Deleted problematic file: {filename}")
            
            # If this is the only file with an issue, hide the auto-fix button
            if all(fixed_status.values()):
                self.parent.auto_fix_btn.pack_forget()
                
            # Refresh directory view if needed
            if self.parent.current_dir:
                self.parent.load_directory(self.parent.current_dir)
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not delete file: {str(e)}")
    
    def get_suggestions(self, file_path, issue):
        """Get suggested fixes for an issue
        
        Args:
            file_path: Path to the file
            issue: The issue text
            
        Returns:
            dict: Suggested fixes
        """
        filename = os.path.basename(file_path)
        suggestions = {}
        
        if "Missing title tag" in issue:
            # Extract from filename
            base_name = os.path.splitext(filename)[0]
            clean_name = base_name.replace('_', ' ').replace('-', ' - ')
            suggestions['title'] = clean_name
            
        elif "Missing artist tag" in issue:
            # Try from filename pattern "Artist - Title"  
            parts = filename.split(' - ', 1)
            if len(parts) > 1:
                suggestions['artist'] = parts[0].strip()
            else:
                suggestions['artist'] = "Unknown Artist"
                
        return suggestions

    def show_compatibility_report(self, report_data, total_issues):
        """Show the compatibility report dialog
        
        Args:
            report_data: List of tuples (filename, results) with compatibility information
            total_issues: Total number of issues found
        """
        report_window = tk.Toplevel(self.parent)
        report_window.title("Compatibility Report")
        report_window.geometry("800x600")
        report_window.configure(background=self.parent.bg_color)
        report_window.transient(self.parent)  # Set as transient to main window
        report_window.grab_set()  # Make modal
    
        # Split window into two panels
        paned = ttk.PanedWindow(report_window, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - file list with status indicators
        list_frame = ttk.Frame(paned, padding=5)
        paned.add(list_frame, weight=1)
    
        # Show summary at top
        summary_frame = ttk.Frame(list_frame)
        summary_frame.pack(fill=tk.X, pady=(0, 10))
        
        if total_issues > 0:
            summary_label = ttk.Label(summary_frame, 
                                    text=f"Found {total_issues} issues across {len(report_data)} files",
                                    foreground=self.parent.error_color,
                                    font=("Helvetica", 12, "bold"))
        else:
            summary_label = ttk.Label(summary_frame, 
                                    text=f"All {len(report_data)} files passed strict compatibility checks!",
                                    foreground=self.parent.success_color,
                                    font=("Helvetica", 12, "bold"))
        summary_label.pack(pady=5)
    
        # Create scrollable list of files
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar for file list
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create a listbox with files
        file_listbox = tk.Listbox(list_container, yscrollcommand=scrollbar.set, 
                                 font=("Helvetica", 10), 
                                 background=self.parent.field_bg_color,
                                 activestyle="none",
                                 highlightthickness=1,
                                 selectbackground=self.parent.accent_color,
                                 selectforeground="white")
        file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=file_listbox.yview)
        
        # Dictionary to track fixed status
        fixed_status = {}
    
        # Populate listbox with filenames and issue count
        for i, (filename, results) in enumerate(report_data):
            issue_count = len(results['issues'])
            warning_count = len(results['warnings'])
            
            # Format the display name to be more readable
            display_name = filename
            if os.path.isabs(filename) and hasattr(self.parent, 'current_dir') and self.parent.current_dir:
                # For full paths, show relative path if possible for better readability
                try:
                    # Try to make path relative to current directory
                    rel_path = os.path.relpath(filename, self.parent.current_dir)
                    # Don't show parent directory paths (with ..)
                    if not rel_path.startswith('..'):
                        display_name = rel_path
                    else:
                        # Just use the filename if it's outside current directory
                        display_name = os.path.basename(filename)
                except:
                    # Fall back to basename if there's any error
                    display_name = os.path.basename(filename)
        
            status = "✓" if issue_count == 0 else f"❌ {issue_count} issues"
            display_text = f"{display_name} - {status}"
        
            file_listbox.insert(tk.END, display_text)
            fixed_status[i] = False
            
            # Color code entries based on issue count
            if issue_count > 0:
                file_listbox.itemconfig(i, fg=self.parent.error_color)
            elif warning_count > 0:
                file_listbox.itemconfig(i, fg="#FFA500")  # Orange for warnings
            else:
                file_listbox.itemconfig(i, fg=self.parent.success_color)
    
        # Right panel - details and fixes
        details_frame = ttk.Frame(paned, padding=10)
        paned.add(details_frame, weight=2)
        
        # Header for details panel
        details_header = ttk.Frame(details_frame)
        details_header.pack(fill=tk.X, pady=(0, 5))
        
        details_title = ttk.Label(details_header, text="Select a file to view details", 
                               font=("Helvetica", 11, "bold"))
        details_title.pack(side=tk.LEFT, pady=5)
        
        # Scrollable content frame for details
        details_canvas = tk.Canvas(details_frame, background=self.parent.bg_color, 
                                 highlightthickness=0)
        details_scrollbar = ttk.Scrollbar(details_frame, orient="vertical", 
                                        command=details_canvas.yview)
        
        details_content = ttk.Frame(details_canvas)
        details_content.bind("<Configure>", lambda e: 
                           details_canvas.configure(scrollregion=details_canvas.bbox("all")))
        
        details_canvas.create_window((0, 0), window=details_content, anchor="nw")
        details_canvas.configure(yscrollcommand=details_scrollbar.set)
        
        details_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Button frame at bottom
        button_frame = ttk.Frame(report_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        close_button = ttk.Button(button_frame, text="Close", 
                               command=report_window.destroy)
        close_button.pack(side=tk.RIGHT, padx=5)
        
        fix_all_button = ttk.Button(button_frame, text="Auto-Fix All Issues", 
                                 style="Accent.TButton",
                                 command=lambda: self.apply_all_fixes(report_data, file_listbox, fixed_status))
        if total_issues > 0:
            fix_all_button.pack(side=tk.RIGHT, padx=5)
    
        # Function to display file details
        def display_file_details(index):
            # Clear previous content
            for widget in details_content.winfo_children():
                widget.destroy()
            
            if index < 0 or index >= len(report_data):
                return
            
            filename, results = report_data[index]
            
            # Update header
            details_title.config(text=filename)
            
            # Get full file path - this handles both direct files and files from recursive scan
            full_path = None
            
            # First check if this might be a full path already (from recursive scan)
            if os.path.isfile(filename):
                full_path = filename
            else:
                # If not, try to find by basename in checked_files_state
                for path in self.parent.checked_files_state.keys():
                    if os.path.basename(path) == filename:
                        full_path = path
                        break
                    
                # If still not found, try to match against any loaded files (from recursive scan)
                if not full_path and hasattr(self.parent, 'scan_file_paths'):
                    for path in self.parent.scan_file_paths:
                        if os.path.basename(path) == filename or path.endswith(filename):
                            full_path = path
                            break
            
            if not full_path:
                ttk.Label(details_content, text="Error: Could not find file path", 
                         foreground=self.parent.error_color).pack(pady=10)
                return
            
            # Show current metadata
            metadata = self.parent.read_metadata(full_path)
        
            # Format info section
            if results['format_info']:
                format_frame = ttk.LabelFrame(details_content, text="Format Information", padding=5)
                format_frame.pack(fill=tk.X, pady=(0, 10))
                
                grid_frame = ttk.Frame(format_frame)
                grid_frame.pack(fill=tk.X, expand=True, pady=5)
                
                row = 0
                for key, value in results['format_info'].items():
                    # Format the value based on what it is
                    if key == 'bitrate':
                        display_value = f"{value//1000} kbps"
                    elif key == 'sample_rate':
                        display_value = f"{value} Hz"
                    elif key == 'length':
                        minutes, seconds = divmod(int(value), 60)
                        display_value = f"{minutes}:{seconds:02d}"
                    else:
                        display_value = str(value)
                    
                    ttk.Label(grid_frame, text=key.replace('_', ' ').title() + ":", 
                            font=("Helvetica", 10, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
                    ttk.Label(grid_frame, text=display_value).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
                    row += 1
        
            # Issues section with fix buttons
            if results['issues']:
                issues_frame = ttk.LabelFrame(details_content, text="Issues", padding=5)
                issues_frame.pack(fill=tk.X, pady=(0, 10))
                
                for i, issue in enumerate(results['issues']):
                    issue_frame = ttk.Frame(issues_frame)
                    issue_frame.pack(fill=tk.X, pady=5)
                    
                    ttk.Label(issue_frame, text=f"• {issue}", 
                             foreground=self.parent.error_color).pack(side=tk.LEFT, padx=5)
                    
                    # Add fix button based on issue type
                    fix_command = None
                    fix_label = "Fix"
                    
                    if "macOS resource file detected" in issue:
                        # For macOS resource files, offer to delete them
                        fix_command = lambda f=full_path: self.delete_file(f, index, file_listbox, fixed_status)
                        fix_label = "Delete File"
                    
                    elif "Missing title tag" in issue:
                        # Extract title from filename
                        suggested_title = os.path.splitext(filename)[0]
                        # Clean up title (remove underscores, dashes, etc.)
                        suggested_title = suggested_title.replace('_', ' ').replace('-', ' - ')
                        fix_command = lambda f=full_path, t=suggested_title: self.fix_metadata(f, 'title', t, index, file_listbox, fixed_status)
                        fix_label = f"Add title: {suggested_title}"
                    
                    elif "Missing artist tag" in issue:
                        # Try to extract artist from filename or use Unknown Artist
                        parts = filename.split(' - ', 1)
                        if len(parts) > 1:
                            suggested_artist = parts[0].strip()
                        else:
                            suggested_artist = "Unknown Artist"
                        fix_command = lambda f=full_path, a=suggested_artist: self.fix_metadata(f, 'artist', a, index, file_listbox, fixed_status)
                        fix_label = f"Add artist: {suggested_artist}"
                    
                    elif "tag exceeds" in issue:
                        # Extract field name and trim suggestion
                        field = issue.split(' ')[0].lower()
                        if field in metadata:
                            current_value = metadata[field]
                            trimmed_value = current_value[:250]
                            fix_command = lambda f=full_path, field=field, v=trimmed_value: self.fix_metadata(f, field, v, index, file_listbox, fixed_status)
                            fix_label = f"Trim {field}"
                    
                    if fix_command:
                        fix_btn = ttk.Button(issue_frame, text=fix_label, command=fix_command)
                        fix_btn.pack(side=tk.RIGHT, padx=5)
        
            # Warnings section
            if results['warnings']:
                warnings_frame = ttk.LabelFrame(details_content, text="Warnings", padding=5)
                warnings_frame.pack(fill=tk.X, pady=(0, 10))
                
                for i, warning in enumerate(results['warnings']):
                    warning_frame = ttk.Frame(warnings_frame)
                    warning_frame.pack(fill=tk.X, pady=2)
                    
                    ttk.Label(warning_frame, text=f"• {warning}", 
                             foreground="#FFA500").pack(side=tk.LEFT, padx=5, pady=2)
            
            # Recommendations section
            if results['recommendations']:
                recommendations_frame = ttk.LabelFrame(details_content, text="Recommendations", padding=5)
                recommendations_frame.pack(fill=tk.X, pady=(0, 10))
                
                for i, recommendation in enumerate(results['recommendations']):
                    ttk.Label(recommendations_frame, text=f"• {recommendation}", 
                             foreground=self.parent.accent_color).pack(anchor=tk.W, padx=5, pady=2)
            
            # If everything is OK
            if not results['issues'] and not results['warnings']:
                ttk.Label(details_content, text="✓ This file meets all Generic Strict Profile standards", 
                        foreground=self.parent.success_color, 
                        font=("Helvetica", 11, "bold")).pack(pady=20)
            
        # Bind listbox selection to display details
        file_listbox.bind('<<ListboxSelect>>', lambda e: display_file_details(file_listbox.curselection()[0] 
                                                                            if file_listbox.curselection() else -1))
        
        # Update status bar in parent
        self.parent.status_var.set(f"Compatibility check complete: {total_issues} issues found")
        
        # Open window in the center of the parent window
        report_window.update_idletasks()
        width = report_window.winfo_width()
        height = report_window.winfo_height()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - height) // 2
        report_window.geometry(f"{width}x{height}+{x}+{y}")
        
        # Select first item with issues if any
        for i in range(file_listbox.size()):
            if "❌" in file_listbox.get(i):
                file_listbox.selection_set(i)
                file_listbox.see(i)
                display_file_details(i)
                break
        else:
            # If no issues, select first item
            if file_listbox.size() > 0:
                file_listbox.selection_set(0)
                display_file_details(0)
