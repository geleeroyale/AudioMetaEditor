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
        
        # Get file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        
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
                
                # WAV files often don't correctly support metadata
                warnings.append("WAV format has limited metadata support")
                recommendations.append("Consider using FLAC or MP3 for better metadata compatibility")
                
                # Check for non-standard sampling rates
                if audio.info.sample_rate not in [44100, 48000]:
                    warnings.append(f"Uncommon sample rate: {audio.info.sample_rate}Hz")
                    recommendations.append("Standard sample rates are 44.1kHz and 48kHz")
                    
            except Exception as e:
                issues.append(f"Error analyzing WAV file: {str(e)}")
        
        # Return results
        return {
            'issues': issues,
            'warnings': warnings,
            'recommendations': recommendations,
            'format_info': format_info
        }
    
    def show_compatibility_report(self, report_data, total_issues):
        """Show the compatibility report dialog
        
        Args:
            report_data: List of tuples (filename, results) with compatibility information
            total_issues: Total number of issues found
        """
        report_window = tk.Toplevel(self.parent)
        report_window.title("Compatibility Report")
        report_window.geometry("700x500")
        report_window.configure(background=self.parent.bg_color)
        report_window.transient(self.parent)  # Set as transient to main window
        report_window.grab_set()  # Make modal
        
        # Create scrollable text widget
        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Show summary at top
        summary_frame = ttk.Frame(report_frame)
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
        
        # Create notebook for file reports
        notebook = ttk.Notebook(report_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Add a tab for each file
        for filename, results in report_data:
            file_frame = ttk.Frame(notebook, padding=10)
            notebook.add(file_frame, text=filename)
            
            # Format info section
            if results['format_info']:
                format_frame = ttk.LabelFrame(file_frame, text="Format Information", padding=5)
                format_frame.pack(fill=tk.X, pady=(0, 10))
                
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
                    
                    ttk.Label(format_frame, text=key.replace('_', ' ').title()).grid(row=row, column=0, sticky=tk.W, padx=5)
                    ttk.Label(format_frame, text=display_value).grid(row=row, column=1, sticky=tk.W, padx=5)
                    row += 1
            
            # Issues section
            if results['issues']:
                issues_frame = ttk.LabelFrame(file_frame, text="Issues", padding=5)
                issues_frame.pack(fill=tk.X, pady=(0, 10))
                
                for i, issue in enumerate(results['issues']):
                    ttk.Label(issues_frame, text=f"• {issue}", foreground=self.parent.error_color).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            
            # Warnings section
            if results['warnings']:
                warnings_frame = ttk.LabelFrame(file_frame, text="Warnings", padding=5)
                warnings_frame.pack(fill=tk.X, pady=(0, 10))
                
                for i, warning in enumerate(results['warnings']):
                    ttk.Label(warnings_frame, text=f"• {warning}", foreground="#FFA500").grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            
            # Recommendations section
            if results['recommendations']:
                recommendations_frame = ttk.LabelFrame(file_frame, text="Recommendations", padding=5)
                recommendations_frame.pack(fill=tk.X)
                
                for i, recommendation in enumerate(results['recommendations']):
                    ttk.Label(recommendations_frame, text=f"• {recommendation}", foreground=self.parent.accent_color).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            
            # If everything is OK
            if not results['issues'] and not results['warnings']:
                ttk.Label(file_frame, text="✓ This file meets all Generic Strict Profile standards", 
                        foreground=self.parent.success_color, font=("Helvetica", 11, "bold")).pack(pady=20)
        
        # Close button
        close_button = ttk.Button(report_frame, text="Close", command=report_window.destroy)
        close_button.pack(pady=10)
        
        # Update status bar in parent
        self.parent.status_var.set(f"Compatibility check complete: {total_issues} issues found")
        
        # Open window in the center of the parent window
        report_window.update_idletasks()
        width = report_window.winfo_width()
        height = report_window.winfo_height()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (width // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (height // 2)
        report_window.geometry(f"{width}x{height}+{x}+{y}")
