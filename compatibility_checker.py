#!/usr/bin/env python3
"""
Compatibility Checker - Generic Strict Profile
This module provides functions to validate audio file metadata against 
the Generic Strict Profile for maximum compatibility with various players.
"""

import os
import io
import tkinter as tk
from tkinter import ttk, messagebox
import struct
import hashlib
import time

# Import required audio processing libraries
from mutagen.flac import FLAC, error as FLACError
from mutagen.id3 import ID3, error as ID3Error
from mutagen.wave import WAVE, error as WAVEError
from mutagen.mp3 import MP3, HeaderNotFoundError
from mutagen import MutagenError

class CompatibilityChecker:
    def __init__(self, parent):
        """Initialize the compatibility checker with a parent application"""
        self.parent = parent
        self.perform_integrity_check = tk.BooleanVar(value=False)  # Default disabled
        self.perform_path_validation = tk.BooleanVar(value=True)  # Default enabled
        
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
            # Store the full path and the basename for display purposes
            results['full_path'] = file_path  # Store full path within results
            display_name = os.path.basename(file_path)  # For display in UI
            report_data.append((display_name, results))
            total_issues += len(results['issues'])
            
        return report_data, total_issues
    
    def check_directory_path(self, dir_path):
        """Check a directory path for naming issues
        
        Args:
            dir_path: Path to the directory to check
            
        Returns:
            tuple: (issues, warnings, recommendations, can_rename, suggested_dirname)
        """
        issues = []
        warnings = []
        recommendations = []
        can_rename = False
        suggested_dirname = None
        
        # Skip if path validation is disabled
        if not self.perform_path_validation.get():
            return issues, warnings, recommendations, can_rename, suggested_dirname
        
        # Get directory name
        dir_name = os.path.basename(dir_path)
        parent_dir = os.path.dirname(dir_path)
        
        # Skip root directories or empty names
        if not dir_name or dir_path == '/' or dir_path == '//' or dir_path == '\\' or dir_path == '\\':
            return issues, warnings, recommendations, can_rename, suggested_dirname
        
        # Check directory name length
        MAX_DIRNAME_LENGTH = 100
        if len(dir_name) > MAX_DIRNAME_LENGTH:
            issues.append(f"Directory name exceeds {MAX_DIRNAME_LENGTH} characters")
            recommendations.append("Consider shortening directory names for better compatibility")
            can_rename = True
        
        # Check for non-standard characters in directory name
        import re
        import unicodedata
        
        # Find problematic characters
        invalid_chars = []
        accented_chars = []
        
        for char in dir_name:
            # Skip allowed characters
            if re.match(r'[0-9a-zA-Z\- ]', char):
                continue
                
            # Detect accented characters
            category = unicodedata.category(char)
            if category.startswith('L'):  # Letter category
                if char not in accented_chars:
                    accented_chars.append(char)
            elif char not in invalid_chars:
                invalid_chars.append(char)
        
        # Report accented characters
        if accented_chars:
            char_list = ', '.join([f"'{c}'" for c in accented_chars])
            warnings.append(f"Directory name contains accented characters: {char_list}")
            recommendations.append("Accented characters may cause issues on some systems")
            can_rename = True
            
        # Report invalid characters
        if invalid_chars:
            char_list = ', '.join([f"'{c}'" for c in invalid_chars])
            issues.append(f"Directory name contains special characters: {char_list}")
            recommendations.append("Use only numbers, letters, spaces, and dashes for best compatibility")
            can_rename = True
            
        # Generate suggested dirname if needed
        if can_rename:
            import re
            import unicodedata
            
            # Create safe directory name by normalizing and transliterating accented characters
            safe_dirname = ""
            
            # First, normalize and attempt to convert accented characters to ASCII
            normalized = unicodedata.normalize('NFKD', dir_name)
            for char in normalized:
                # Skip combining characters (used to create accents)
                if unicodedata.category(char).startswith('M'):
                    continue
                    
                # Keep alphanumeric chars, spaces, and dashes
                if re.match(r'[0-9a-zA-Z\- ]', char):
                    safe_dirname += char
                else:
                    # Skip other characters
                    pass
            
            # If resulting dirname is empty, use a fallback name
            if not safe_dirname.strip():
                safe_dirname = "folder"
                
            # Remove consecutive spaces and dashes
            safe_dirname = re.sub(r'[ ]+', ' ', safe_dirname)  # Collapse multiple spaces
            safe_dirname = re.sub(r'-+', '-', safe_dirname)    # Collapse multiple dashes
            
            # Remove leading/trailing spaces and dashes
            safe_dirname = safe_dirname.strip('- ')
            
            # Truncate if still too long
            if len(safe_dirname) > MAX_DIRNAME_LENGTH:
                safe_dirname = safe_dirname[:MAX_DIRNAME_LENGTH - 3] + '...'  # Add ellipsis
                
            suggested_dirname = safe_dirname
            
        return issues, warnings, recommendations, can_rename, suggested_dirname
    
    def check_path_issues(self, file_path):
        """Check for file path related issues (length, special characters, etc.)
        
        Args:
            file_path: Full path to the audio file
            
        Returns:
            tuple: (issues, warnings, recommendations, can_rename, suggested_filename)
        """
        issues = []
        warnings = []
        recommendations = []
        can_rename = False
        suggested_filename = None
        
        # Get file and directory information
        file_basename = os.path.basename(file_path)
        file_name, file_ext = os.path.splitext(file_basename)
        dir_path = os.path.dirname(file_path)
        
        # Check for path length issues (Windows has ~260 char limit by default)
        MAX_PATH_LENGTH = 250
        MAX_FILENAME_LENGTH = 100
        if len(file_path) > MAX_PATH_LENGTH:
            issues.append(f"File path exceeds {MAX_PATH_LENGTH} characters")
            recommendations.append("Shorten the file path for better compatibility across systems")
        
        # Check filename length
        if len(file_basename) > MAX_FILENAME_LENGTH:
            issues.append(f"Filename exceeds {MAX_FILENAME_LENGTH} characters")
            recommendations.append("Consider shortening the filename")
            can_rename = True
        
        # Only perform character validation if the option is enabled
        if self.perform_path_validation.get():
            # Check for non-standard characters in filename
            # Allow: A-Z, a-z, 0-9, spaces, and dashes
            # Detect accented characters and other non-ASCII characters
            import re
            import unicodedata
            
            # Find problematic characters
            invalid_chars = []
            accented_chars = []
            
            for char in file_name:
                # Skip allowed characters
                if re.match(r'[0-9a-zA-Z\- ]', char):
                    continue
                    
                # Detect accented characters
                category = unicodedata.category(char)
                if category.startswith('L'):  # Letter category
                    if char not in accented_chars:
                        accented_chars.append(char)
                elif char not in invalid_chars:
                    invalid_chars.append(char)
            
            # Report accented characters
            if accented_chars:
                char_list = ', '.join([f"'{c}'" for c in accented_chars])
                warnings.append(f"Filename contains accented characters: {char_list}")
                recommendations.append("Accented characters may cause issues on some systems")
                can_rename = True
                
            # Report invalid characters
            if invalid_chars:
                char_list = ', '.join([f"'{c}'" for c in invalid_chars])
                issues.append(f"Filename contains special characters: {char_list}")
                recommendations.append("Use only numbers, letters, spaces, and dashes for best compatibility")
                can_rename = True
        
        # Generate suggested filename if needed
        if can_rename:
            import re
            import unicodedata
            
            # Create safe filename by normalizing and transliterating accented characters
            # and keeping only allowed chars (alphanumeric, spaces, and dashes)
            safe_filename = ""
            
            # First, normalize and attempt to convert accented characters to ASCII
            normalized = unicodedata.normalize('NFKD', file_name)
            for char in normalized:
                # Skip combining characters (used to create accents)
                if unicodedata.category(char).startswith('M'):
                    continue
                    
                # Keep alphanumeric chars, spaces, and dashes
                if re.match(r'[0-9a-zA-Z\- ]', char):
                    safe_filename += char
                else:
                    # Skip other characters
                    pass
            
            # If resulting filename is empty, use a fallback name
            if not safe_filename.strip():
                safe_filename = "audiofile"
                
            # Remove consecutive spaces and dashes
            safe_filename = re.sub(r'[ ]+', ' ', safe_filename)  # Collapse multiple spaces
            safe_filename = re.sub(r'-+', '-', safe_filename)    # Collapse multiple dashes
            
            # Remove leading/trailing spaces and dashes
            safe_filename = safe_filename.strip('- ')
            
            # Truncate if still too long
            if len(safe_filename) > MAX_FILENAME_LENGTH - len(file_ext):
                safe_filename = safe_filename[:MAX_FILENAME_LENGTH - len(file_ext) - 3] + '...'  # Add ellipsis
                
            suggested_filename = safe_filename + file_ext
        
        return issues, warnings, recommendations, can_rename, suggested_filename
        
    def validate_strict_profile(self, file_path, metadata):
        """Validate metadata against the Generic Strict Profile and check file integrity
        
        Args:
            file_path: Path to the audio file
            metadata: Dictionary containing metadata information
            
        Returns:
            dict: Results containing issues, warnings, recommendations, file integrity status and format info
        """
        issues = []
        warnings = []
        recommendations = []
        format_info = {}
        integrity_status = {"status": "OK", "issues": [], "md5": ""}
        path_can_rename = False
        suggested_filename = None
        
        # Get file basename and extension
        file_basename = os.path.basename(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Check for problematic macOS resource files
        if file_basename.startswith("._"):
            issues.append("macOS resource file detected")
            recommendations.append("These hidden resource files are not actual audio files and should be deleted")
        
        # Check for file path-related issues
        path_issues, path_warnings, path_recommendations, path_can_rename, suggested_filename = self.check_path_issues(file_path)
        issues.extend(path_issues)
        warnings.extend(path_warnings)
        recommendations.extend(path_recommendations)
        
        # Check parent directory name issues
        if self.perform_path_validation.get():
            # Get directory path and check it
            dir_path = os.path.dirname(file_path)
            dir_issues, dir_warnings, dir_recommendations, dir_can_rename, suggested_dirname = self.check_directory_path(dir_path)
            
            # Add directory issues to results, marking them as directory-related
            for issue in dir_issues:
                issues.append(f"Parent directory issue: {issue}")
            for warning in dir_warnings:
                warnings.append(f"Parent directory warning: {warning}")
            for rec in dir_recommendations:
                recommendations.append(f"Parent directory: {rec}")
            
            # Store directory renaming information (if applicable)
            if dir_can_rename and suggested_dirname:
                # Add to the path information in the results
                path_can_rename = True  # This will now indicate that either file or directory has issues
        
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
        
        # Perform file integrity check if enabled
        if self.perform_integrity_check.get():
            integrity_status = self.check_file_integrity(file_path, file_ext)
        
        # Add integrity issues to the main issues list
        if integrity_status["status"] != "OK":
            for integrity_issue in integrity_status["issues"]:
                issues.append(f"Integrity issue: {integrity_issue}")
                if "corrupted" in integrity_issue.lower():
                    recommendations.append("This file appears to be corrupted and may need to be re-encoded")
                elif "truncated" in integrity_issue.lower():
                    recommendations.append("This file appears to be truncated and may be missing data")
                elif "header" in integrity_issue.lower():
                    recommendations.append("This file has header issues that may cause playback problems")
            
            # Add MD5 checksum to format info if calculated successfully
            if integrity_status["md5"]:
                format_info['md5_checksum'] = integrity_status["md5"]
        
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
        
        # Return the combined results
        return {
            'issues': issues,
            'warnings': warnings,
            'recommendations': recommendations,
            'format_info': format_info,
            'integrity': integrity_status,
            'path': {
                'can_rename': path_can_rename,
                'suggested_filename': suggested_filename,
                'dir_path': os.path.dirname(file_path),
                'dir_can_rename': dir_can_rename if self.perform_path_validation.get() else False,
                'suggested_dirname': suggested_dirname if self.perform_path_validation.get() else None
            }
        }
    
    def rename_directory(self, dir_path, new_dirname):
        """Rename a directory with a safer name
        
        Args:
            dir_path: Original directory path
            new_dirname: New directory name (without parent path)
            
        Returns:
            dict: Result of the rename operation
        """
        result = {"success": False, "message": "", "new_path": None}
        
        try:
            # Get parent directory and construct new path
            parent_dir = os.path.dirname(dir_path)
            new_path = os.path.join(parent_dir, new_dirname)
            
            # Check if destination already exists
            if os.path.exists(new_path):
                result["message"] = f"Cannot rename directory: '{new_dirname}' already exists"
                return result
            
            # Perform the rename
            os.rename(dir_path, new_path)
            result["success"] = True
            result["message"] = f"Directory renamed successfully to '{new_dirname}'"
            result["new_path"] = new_path
            
        except Exception as e:
            result["message"] = f"Failed to rename directory: {str(e)}"
            
        return result
    
    def rename_file(self, file_path, new_filename):
        """Rename a file with a safer filename
        
        Args:
            file_path: Original file path
            new_filename: New filename (without directory path)
            
        Returns:
            dict: Result of the rename operation
        """
        result = {"success": False, "message": "", "new_path": None}
        
        try:
            # Get directory and construct new path
            dir_path = os.path.dirname(file_path)
            new_path = os.path.join(dir_path, new_filename)
            
            # Check if destination already exists
            if os.path.exists(new_path):
                result["message"] = f"Cannot rename: '{new_filename}' already exists"
                return result
                
            # Create a backup of the original file's metadata (if possible)
            metadata = None
            try:
                from mutagen import File
                audio = File(file_path)
                if audio is not None:
                    metadata = audio
            except Exception:
                pass  # Ignore errors in metadata backup attempt
            
            # Perform the rename
            os.rename(file_path, new_path)
            result["success"] = True
            result["message"] = f"File renamed successfully to '{new_filename}'"
            result["new_path"] = new_path
            
            # Try to restore metadata if available
            if metadata is not None:
                try:
                    new_audio = File(new_path)
                    if new_audio is not None and hasattr(metadata, 'tags') and metadata.tags:
                        new_audio.tags = metadata.tags
                        new_audio.save()
                except Exception as e:
                    result["message"] += f" (Warning: metadata transfer had issues: {str(e)})"
            
        except Exception as e:
            result["message"] = f"Failed to rename file: {str(e)}"
            
        return result
    
    def cleanup_resource_files(self, directory):
        """Clean up macOS resource files (files starting with ._)
        
        Args:
            directory: Directory to clean up
            
        Returns:
            int: Number of resource files removed
        """
        if not os.path.isdir(directory):
            return 0
            
        count = 0
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.startswith('._'):
                    try:
                        full_path = os.path.join(root, file)
                        os.remove(full_path)
                        count += 1
                        print(f"Removed macOS resource file: {full_path}")
                    except Exception as e:
                        print(f"Failed to remove resource file {file}: {str(e)}")
        return count
        
    def check_file_integrity(self, file_path, file_ext):
        """Check the integrity of an audio file
        
        Args:
            file_path: Path to the audio file
            file_ext: File extension (lowercase)
            
        Returns:
            dict: Integrity status information with repair suggestion if applicable
        """
        # Skip macOS resource files
        if os.path.basename(file_path).startswith('._'):
            return {
                "status": "Error",
                "issues": ["macOS resource file"],
                "can_repair": True,
                "repair_method": "delete_resource_file"
            }
            
        result = {"status": "OK", "issues": [], "md5": "", "can_repair": False, "repair_method": None}
        
        try:
            # Calculate MD5 hash of the file
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5()
                # Read in chunks to handle large files efficiently
                chunk = f.read(8192)
                while chunk:
                    file_hash.update(chunk)
                    chunk = f.read(8192)
                result["md5"] = file_hash.hexdigest()
            
            # Get file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                result["status"] = "Error"
                result["issues"].append("Zero-byte file detected")
                return result
            
            # Format-specific integrity checks
            if file_ext == '.mp3':
                # MP3 integrity check
                try:
                    with open(file_path, 'rb') as f:
                        # Check for valid MP3 header
                        header = f.read(4)
                        if not header.startswith(b'ID3') and not (header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
                            result["status"] = "Error"
                            result["issues"].append("Invalid MP3 header")
                            result["can_repair"] = True
                            result["repair_method"] = "rebuild_mp3"
                    
                    # Use mutagen to verify the file can be parsed
                    audio = MP3(file_path)
                    
                    # Check if duration makes sense (should be positive, not excessively large)
                    if audio.info.length <= 0 or audio.info.length > 24*60*60:  # >24 hours is suspicious
                        result["status"] = "Warning"
                        result["issues"].append("Suspicious track duration")
                        
                    # Check if bitrate makes sense
                    if audio.info.bitrate <= 0 or audio.info.bitrate > 1000000:  # >1000kbps is suspicious for MP3
                        result["status"] = "Warning"
                        result["issues"].append("Suspicious bitrate value")
                    
                except HeaderNotFoundError:
                    result["status"] = "Error"
                    result["issues"].append("MP3 header not found, file may be corrupted")
                    result["can_repair"] = True
                    result["repair_method"] = "rebuild_mp3"
                except Exception as e:
                    result["status"] = "Error"
                    result["issues"].append(f"MP3 parsing error: {str(e)}")
            
            elif file_ext == '.flac':
                # FLAC integrity check
                try:
                    # Use mutagen to verify the file can be parsed
                    audio = FLAC(file_path)
                    
                    # Check if STREAMINFO block is present (required for valid FLAC)
                    if not audio.info:
                        result["status"] = "Error"
                        result["issues"].append("Missing STREAMINFO block")
                    
                    # FLAC-specific checks
                    with open(file_path, 'rb') as f:
                        # Check FLAC signature
                        if f.read(4) != b'fLaC':
                            result["status"] = "Error"
                            result["issues"].append("Invalid FLAC signature")
                            result["can_repair"] = True
                            result["repair_method"] = "rebuild_flac"
                            
                except FLACError:
                    result["status"] = "Error"
                    result["issues"].append("FLAC parsing error, file may be corrupted")
                except Exception as e:
                    result["status"] = "Error"
                    result["issues"].append(f"FLAC integrity error: {str(e)}")
            
            elif file_ext == '.wav':
                # WAV integrity check
                try:
                    with open(file_path, 'rb') as f:
                        # Check WAV header
                        riff = f.read(4)
                        size = f.read(4)
                        wave = f.read(4)
                        
                        if riff != b'RIFF' or wave != b'WAVE':
                            result["status"] = "Error"
                            result["issues"].append("Invalid WAV header")
                            result["can_repair"] = True
                            result["repair_method"] = "rebuild_wav"
                        
                        # Check file size against header
                        try:
                            expected_size = struct.unpack('<I', size)[0] + 8
                            if abs(expected_size - file_size) > 100:  # Allow small difference for metadata
                                result["status"] = "Warning"
                                result["issues"].append("WAV file size mismatch")
                        except:
                            result["status"] = "Warning"
                            result["issues"].append("Unable to verify WAV file size")
                
                except WAVEError:
                    result["status"] = "Error"
                    result["issues"].append("WAV parsing error, file may be corrupted")
                except Exception as e:
                    result["status"] = "Error"
                    result["issues"].append(f"WAV integrity error: {str(e)}")
            
            elif file_ext == '.ogg':
                # OGG integrity check
                try:
                    with open(file_path, 'rb') as f:
                        # Check OGG signature
                        if f.read(4) != b'OggS':
                            result["status"] = "Error"
                            result["issues"].append("Invalid OGG signature")
                except Exception as e:
                    result["status"] = "Error"
                    result["issues"].append(f"OGG integrity error: {str(e)}")
                    
        except IOError as e:
            result["status"] = "Error"
            result["issues"].append(f"File access error: {str(e)}")
        except Exception as e:
            result["status"] = "Error"
            result["issues"].append(f"Integrity check error: {str(e)}")
        
        return result

    def fix_metadata(self, file_path, field, value, list_index, listbox, fixed_status):
        """Fix a specific metadata field in a file
        
{{ ... }}
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
        # Check if the parent class has the enhanced auto-fix method
        if hasattr(self.parent, 'auto_fix_compatibility'):
            # Store the report data for the parent to use
            self.parent.last_report_data = report_data.copy()
            
            # Store file paths for the parent to use
            file_paths = []
            for index, (filename, results) in enumerate(report_data):
                # Skip already fixed files
                if fixed_status[index] or not results.get('issues', []):
                    continue
                    
                # Find the full path
                for path in self.parent.checked_files_state.keys():
                    if os.path.basename(path) == filename:
                        file_paths.append(path)
                        break
            
            # Set up callback for when auto-fix completes
            original_callback = None
            if hasattr(self.parent, 'completion_callback'):
                original_callback = self.parent.completion_callback
                
            # Define update function
            def update_after_fix():
                # Update the listbox display
                for index, (filename, results) in enumerate(report_data):
                    # Check if fixed by looking at the full path
                    for path in self.parent.checked_files_state.keys():
                        if os.path.basename(path) == filename:
                            if self.parent.checked_files_state[path].get('fixed', False):
                                fixed_status[index] = True
                                new_text = f"{filename} - ✓ Fixed"
                                listbox.delete(index)
                                listbox.insert(index, new_text)
                                listbox.itemconfig(index, fg=self.parent.success_color)
                                break
                
                # Update the display
                if listbox.curselection():
                    listbox.event_generate("<<ListboxSelect>>")
                    
                # Restore original callback
                if original_callback:
                    self.parent.completion_callback = original_callback
                else:
                    if hasattr(self.parent, 'completion_callback'):
                        delattr(self.parent, 'completion_callback')
            
            # Set the callback
            self.parent.completion_callback = update_after_fix
            
            # Call parent's auto-fix method
            try:
                self.parent.auto_fix_compatibility()
            except Exception as e:
                messagebox.showerror("Auto-Fix Error", f"An error occurred: {str(e)}")
                # Restore callback in case of error
                if original_callback:
                    self.parent.completion_callback = original_callback
                else:
                    if hasattr(self.parent, 'completion_callback'):
                        delattr(self.parent, 'completion_callback')
        else:
            # Fallback to basic fix implementation
            self._basic_auto_fix(report_data, listbox, fixed_status)
            
    def _basic_auto_fix(self, report_data, listbox, fixed_status):
        """Basic implementation of auto-fix functionality (fallback)
        
        Args:
            report_data: List of tuples (filename, results) with compatibility information
            listbox: The listbox widget
            fixed_status: Dictionary tracking fixed status
        """
        fixed_count = 0
        skipped_count = 0
        
        for index, (filename, results) in enumerate(report_data):
            # Skip already fixed or files without issues
            if fixed_status[index] or not results.get('issues', []):
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
            
    def repair_file_integrity(self, file_path, integrity_result):
        """Attempt to repair file integrity issues
        
        Args:
            file_path: Path to the audio file to repair
            integrity_result: The integrity check result dictionary
            
        Returns:
            dict: Result of the repair attempt
        """
        if not integrity_result.get("can_repair", False):
            return {"success": False, "message": "This issue cannot be automatically repaired"}
        
        result = {"success": False, "message": ""}
        file_ext = os.path.splitext(file_path)[1].lower()
        repair_method = integrity_result.get("repair_method")
        
        try:
            # Create a backup of the original file
            backup_path = file_path + ".bak"
            try:
                with open(file_path, 'rb') as src:
                    with open(backup_path, 'wb') as dst:
                        dst.write(src.read())
            except Exception as e:
                return {"success": False, "message": f"Failed to create backup: {str(e)}"}
            
            # Apply the appropriate repair method
            if repair_method == "delete_resource_file":
                # Handle macOS resource files by deleting them
                try:
                    os.remove(file_path)
                    result = {"success": True, "message": "Removed macOS resource file successfully"}
                except Exception as e:
                    result = {"success": False, "message": f"Failed to delete resource file: {str(e)}"}
            elif repair_method == "rebuild_mp3":
                result = self._repair_mp3(file_path)
            elif repair_method == "rebuild_flac":
                result = self._repair_flac(file_path)
            elif repair_method == "rebuild_wav":
                result = self._repair_wav(file_path)
            else:
                result = {"success": False, "message": "Unknown repair method"}
                
            # If repair failed, restore from backup
            if not result["success"]:
                try:
                    with open(backup_path, 'rb') as src:
                        with open(file_path, 'wb') as dst:
                            dst.write(src.read())
                    os.remove(backup_path)
                except Exception as e:
                    result["message"] += f" (Error restoring backup: {str(e)})"
            else:
                # Successful repair, delete backup
                try:
                    os.remove(backup_path)
                except Exception:
                    pass
                    
        except Exception as e:
            result = {"success": False, "message": f"Repair failed: {str(e)}"}
            
        return result
    
    def _repair_mp3(self, file_path):
        """Repair MP3 file with header or structural issues"""
        try:
            # Read the audio data
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Find the start of the MP3 frame (usually starts with 0xFF)
            # Skip any ID3 tags if present
            start_pos = 0
            # Look for ID3 tag
            if data.startswith(b'ID3'):
                # The ID3v2 header is 10 bytes, followed by the tag size
                # The size is stored as 4 synchsafe integers (7 bits each)
                if len(data) > 10:
                    size_bytes = data[6:10]
                    size = ((size_bytes[0] & 0x7F) << 21) | ((size_bytes[1] & 0x7F) << 14) | \
                           ((size_bytes[2] & 0x7F) << 7) | (size_bytes[3] & 0x7F)
                    start_pos = 10 + size
            
            # Find the first MP3 frame
            pos = start_pos
            frame_start = -1
            while pos < len(data) - 1:
                if data[pos] == 0xFF and (data[pos+1] & 0xE0) == 0xE0:
                    frame_start = pos
                    break
                pos += 1
            
            if frame_start == -1:
                return {"success": False, "message": "Could not find MP3 frame start"}
            
            # Write a new MP3 file with proper structure
            with open(file_path, 'wb') as f:
                # If there was an ID3 tag, preserve it
                if start_pos > 0:
                    f.write(data[:start_pos])
                # Write from the first valid frame to the end
                f.write(data[frame_start:])
            
            return {"success": True, "message": "MP3 file structure repaired successfully"}
        except Exception as e:
            return {"success": False, "message": f"MP3 repair failed: {str(e)}"}
    def _repair_flac(self, file_path):
        """Repair FLAC file with header or structural issues"""
        backup_path = None
        temp_dir = None
        
        try:
            import subprocess
            import tempfile
            import shutil
            import time
            
            # Check if this is a macOS resource file (._ prefix)
            if os.path.basename(file_path).startswith('._'):
                print(f"Skipping macOS resource file: {os.path.basename(file_path)}", flush=True)
                return {"success": False, "message": "Cannot repair macOS resource file. Please use 'Delete Selected' for resource files."}
            
            # Get the file extension for later use
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Create a unique temporary directory
            temp_dir = tempfile.mkdtemp(prefix="flac_repair_")
            temp_wav = os.path.join(temp_dir, os.path.basename(file_path) + ".wav")
            temp_flac = os.path.join(temp_dir, os.path.basename(file_path))
            temp_fixed_flac = os.path.join(temp_dir, "fixed_" + os.path.basename(file_path))
            
            # Create a backup of the original file
            backup_path = file_path + ".bak"
            try:
                shutil.copy2(file_path, backup_path)
                print(f"Created backup of {os.path.basename(file_path)}", flush=True)
            except Exception as e:
                print(f"Warning: Could not create backup: {str(e)}", flush=True)
                return {"success": False, "message": f"Could not create backup. Aborting repair to prevent data loss."}
            
            repair_message = ""
            repair_successful = False
            
            # STAGE 1: Try to use flac's built-in repair capability
            try:
                print(f"[STAGE 1] Attempting to repair {os.path.basename(file_path)} using flac tools...", flush=True)
                
                # Run flac with --keep-foreign-metadata to preserve as much as possible
                process = subprocess.run(["flac", "--decode", "--force", "--output-name", temp_wav, file_path], 
                              check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                
                if process.returncode == 0:
                    repair_message += "Successfully decoded FLAC to WAV. "
                    print("Successfully decoded to WAV format", flush=True)
                    
                    # Re-encode the WAV back to FLAC with verified encoding
                    print("Re-encoding to FLAC with verification...", flush=True)
                    process = subprocess.run(["flac", "--verify", "--best", "--output-name", temp_flac, temp_wav],
                                  check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    
                    if process.returncode == 0:
                        repair_message += "Successfully re-encoded to FLAC. "
                        print("Re-encoding successful", flush=True)
                        
                        # If all went well, replace the original file
                        with open(temp_flac, 'rb') as src:
                            with open(file_path, 'wb') as dst:
                                dst.write(src.read())
                        
                        # Verify the fixed file immediately
                        time.sleep(0.1)  # Small delay to ensure file system catches up
                        integrity_result = self.check_file_integrity(file_path, file_ext)
                        
                        if integrity_result["status"] == "OK":
                            success_msg = f"FLAC file repaired using native FLAC tools. {repair_message}Integrity check passed."
                            print(success_msg, flush=True)
                            repair_successful = True
                            return {"success": True, "message": success_msg, "integrity_result": integrity_result}
                        else:
                            print("Repair didn't resolve all integrity issues. Trying alternative methods...", flush=True)
                    else:
                        print(f"FLAC re-encoding failed: {process.stderr.decode('utf-8', errors='ignore')}", flush=True)
                else:
                    print(f"FLAC decoding failed: {process.stderr.decode('utf-8', errors='ignore')}", flush=True)
            except Exception as stage1_error:
                print(f"Error in Stage 1 repair: {str(stage1_error)}", flush=True)
            
            # STAGE 2: Try direct Mutagen repair
            if not repair_successful:
                print(f"[STAGE 2] Attempting repair using Mutagen library...", flush=True)
                try:
                    # Restore from backup before attempting this method
                    if os.path.exists(backup_path):
                        shutil.copy2(backup_path, file_path)
                        print("Restored from backup for fresh repair attempt", flush=True)
                    
                    # Try to read with mutagen
                    audio = FLAC(file_path)
                    # Add minimal metadata if missing to ensure valid structure
                    if not audio.tags:
                        audio.tags = mutagen.flac.VCFLACDict()
                        audio.tags['TITLE'] = [os.path.splitext(os.path.basename(file_path))[0]]
                    
                    # Try to save and fix the file
                    audio.save(file_path)
                    
                    # Verify the fixed file
                    time.sleep(0.1)  # Small delay
                    integrity_result = self.check_file_integrity(file_path, file_ext)
                    
                    if integrity_result["status"] == "OK":
                        success_msg = "FLAC file header repaired successfully with mutagen. Integrity check passed."
                        print(success_msg, flush=True)
                        repair_successful = True
                        return {"success": True, "message": success_msg, "integrity_result": integrity_result}
                    else:
                        print("Mutagen repair didn't resolve all integrity issues.", flush=True)
                except Exception as mutagen_error:
                    print(f"Mutagen repair failed: {str(mutagen_error)}", flush=True)
            
            # STAGE 3: Try ffmpeg if available
            if not repair_successful:
                print(f"[STAGE 3] Attempting repair using ffmpeg...", flush=True)
                try:
                    # Restore from backup before attempting this method
                    if os.path.exists(backup_path):
                        shutil.copy2(backup_path, file_path)
                        print("Restored from backup for fresh repair attempt", flush=True)
                    
                    # Check if ffmpeg is available
                    ffmpeg_check = subprocess.run(["which", "ffmpeg"], 
                                     check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                    
                    if ffmpeg_check.returncode == 0:
                        print("ffmpeg found, attempting repair...", flush=True)
                        
                        # Try to convert through ffmpeg
                        ffmpeg_process = subprocess.run(
                            ["ffmpeg", "-i", file_path, "-c:a", "flac", "-compression_level", "12", temp_fixed_flac],
                            check=False, stderr=subprocess.PIPE, stdout=subprocess.PIPE
                        )
                        
                        if ffmpeg_process.returncode == 0 and os.path.exists(temp_fixed_flac):
                            # Replace original with fixed version
                            shutil.copy2(temp_fixed_flac, file_path)
                            print("ffmpeg repair completed", flush=True)
                            
                            # Check integrity
                            integrity_result = self.check_file_integrity(file_path, file_ext)
                            if integrity_result["status"] == "OK":
                                success_msg = "FLAC file repaired using ffmpeg. Integrity check passed."
                                print(success_msg, flush=True)
                                repair_successful = True
                                return {"success": True, "message": success_msg, "integrity_result": integrity_result}
                            else:
                                print("ffmpeg repair didn't resolve all integrity issues.", flush=True)
                        else:
                            print(f"ffmpeg repair failed: {ffmpeg_process.stderr.decode('utf-8', errors='ignore')}", flush=True)
                    else:
                        print("ffmpeg not found, skipping this repair method.", flush=True)
                except Exception as ffmpeg_error:
                    print(f"Error during ffmpeg repair: {str(ffmpeg_error)}", flush=True)
            
            # If we got here, all repair attempts failed
            print("All repair attempts failed. Restoring original file from backup.", flush=True)
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                print("Original file restored.", flush=True)
            
            return {"success": False, "message": "All repair attempts failed to fix integrity issues.", "last_error": "No repair method was successful"}
                
        except Exception as e:
            print(f"FLAC repair failed with unexpected error: {str(e)}", flush=True)
            # Try to restore from backup
            if backup_path and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, file_path)
                    print("Restored original file after error.", flush=True)
                except:
                    pass
            return {"success": False, "message": f"FLAC repair failed: {str(e)}"}
        finally:
            # Always clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    print("Cleaned up temporary files.", flush=True)
                except Exception as cleanup_error:
                    print(f"Warning: Could not clean up temporary files: {str(cleanup_error)}", flush=True)
            
            # Always clean up backup if repair was successful or we're done with it
            if backup_path and os.path.exists(backup_path) and repair_successful:
                try:
                    os.remove(backup_path)
                    print("Removed backup file after successful repair.", flush=True)
                except Exception as backup_error:
                    print(f"Warning: Could not remove backup file: {str(backup_error)}", flush=True)
    
    def _repair_wav(self, file_path):
        """Repair WAV file with header or structural issues"""
        try:
            # Read the file data
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # A minimal valid WAV header (44 bytes for PCM)
            if len(data) < 44:
                return {"success": False, "message": "WAV file too small to repair"}
            
            # Check/fix the basic WAV header
            header = bytearray(44)
            
            # RIFF header
            header[0:4] = b'RIFF'
            
            # File size (file size - 8 bytes)
            file_size = len(data) - 8
            header[4:8] = file_size.to_bytes(4, byteorder='little')
            
            # WAVE signature
            header[8:12] = b'WAVE'
            
            # 'fmt ' chunk
            header[12:16] = b'fmt '
            
            # Rest of the header - use default PCM values if we can't determine
            # We'll set a basic PCM format (16-bit, stereo, 44.1kHz)
            # fmt chunk size (16 for PCM)
            header[16:20] = (16).to_bytes(4, byteorder='little')
            # Audio format (1 = PCM)
            header[20:22] = (1).to_bytes(2, byteorder='little')
            # Num channels (2 = stereo)
            header[22:24] = (2).to_bytes(2, byteorder='little')
            # Sample rate (44100)
            header[24:28] = (44100).to_bytes(4, byteorder='little')
            # Byte rate (sample_rate * num_channels * bits_per_sample/8)
            header[28:32] = (44100 * 2 * 2).to_bytes(4, byteorder='little')
            # Block align (num_channels * bits_per_sample/8)
            header[32:34] = (2 * 2).to_bytes(2, byteorder='little')
            # Bits per sample (16)
            header[34:36] = (16).to_bytes(2, byteorder='little')
            
            # 'data' chunk
            header[36:40] = b'data'
            
            # Data size (file size - 44 bytes header)
            data_size = max(0, len(data) - 44)
            header[40:44] = data_size.to_bytes(4, byteorder='little')
            
            # Write the repaired file
            with open(file_path, 'wb') as f:
                f.write(header)
                if len(data) > 44:
                    f.write(data[44:])
            
            return {"success": True, "message": "WAV file structure repaired successfully"}
        
        except Exception as e:
            return {"success": False, "message": f"WAV repair failed: {str(e)}"}
    
    def update_report_with_integrity_setting(self, report_data, listbox, details_content):
        """Update the report display when the integrity check setting is changed
        
        Args:
            report_data: List of tuples (filename, results) with compatibility information
            listbox: The listbox widget showing file list
            details_content: Frame containing the details view
        """
        # Get the currently selected item if any
        selected_indices = listbox.curselection()
        if selected_indices:
            index = selected_indices[0]
            # Update the details display for the selected file
            if hasattr(self, 'display_file_details') and callable(self.display_file_details):
                self.display_file_details(index)
            else:
                # Refresh the details pane
                for widget in details_content.winfo_children():
                    widget.destroy()
                
                if index >= 0 and index < len(report_data):
                    filename, results = report_data[index]
                    
                    # Update visibility of integrity information
                    if not self.perform_integrity_check.get():
                        # Hide integrity issues if check is disabled
                        for i in range(len(results.get('issues', []))):
                            if i < len(results['issues']) and 'Integrity issue:' in results['issues'][i]:
                                results['issues'][i] = None
                        # Filter out None values
                        results['issues'] = [issue for issue in results['issues'] if issue is not None]
    
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
                    
            # Format info section
            if results['format_info']:
                format_frame = ttk.LabelFrame(details_content, text="File Information", padding=5)
                format_frame.pack(fill=tk.X, pady=(0, 10))
                
                # File path display (especially useful for recursive scan)
                path_label = ttk.Label(format_frame, text=f"Path: {full_path}", wraplength=580)
                path_label.pack(anchor=tk.W, padx=5, pady=2)
                
                for key, value in results['format_info'].items():
                    if key == 'bitrate':
                        value = f"{value//1000} kbps"
                    elif key == 'sample_rate':
                        value = f"{value//1000} kHz"
                    elif key == 'length':
                        minutes = int(value // 60)
                        seconds = int(value % 60)
                        value = f"{minutes}:{seconds:02d}"
                    elif key == 'md5_checksum':
                        value = f"{value} (calculated during integrity check)"
                    
                    info_frame = ttk.Frame(format_frame)
                    info_frame.pack(fill=tk.X, pady=1)
                    
                    # Format key with title case and replace underscores with spaces
                    formatted_key = key.replace('_', ' ').title()
                    ttk.Label(info_frame, text=f"{formatted_key}:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=5)
                    ttk.Label(info_frame, text=f"{value}").pack(side=tk.LEFT)
            
            # File integrity section
            if 'integrity' in results and self.perform_integrity_check.get():
                integrity_frame = ttk.LabelFrame(details_content, text="File Integrity", padding=5)
                integrity_frame.pack(fill=tk.X, pady=(0, 10))
                
                status_frame = ttk.Frame(integrity_frame)
                status_frame.pack(fill=tk.X, pady=2)
                
                status_label = ttk.Label(status_frame, text="Status:", width=10, anchor=tk.W)
                status_label.pack(side=tk.LEFT, padx=5)
                
                status_color = "#4CAF50" if results['integrity']['status'] == "OK" else \
                               "#FFA500" if results['integrity']['status'] == "Warning" else "#F44336"
                
                status_value = ttk.Label(status_frame, 
                                          text=results['integrity']['status'],
                                          foreground=status_color,
                                          font=("Helvetica", 10, "bold"))
                status_value.pack(side=tk.LEFT)
                
                # Display MD5 checksum if available
                if results['integrity']['md5']:
                    md5_frame = ttk.Frame(integrity_frame)
                    md5_frame.pack(fill=tk.X, pady=1)
                    
                    ttk.Label(md5_frame, text="File MD5:", width=10, anchor=tk.W).pack(side=tk.LEFT, padx=5)
                    ttk.Label(md5_frame, text=results['integrity']['md5'], font=("Courier", 9)).pack(side=tk.LEFT)
            
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
