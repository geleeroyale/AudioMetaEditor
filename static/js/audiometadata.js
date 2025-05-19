document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('fileInput');
    const browseButton = document.getElementById('browseButton');
    const uploadProgress = document.getElementById('upload-progress');
    const progressBar = uploadProgress.querySelector('.progress-bar');
    const metadataEditor = document.getElementById('metadata-editor');
    const saveButton = document.getElementById('save-button');
    const downloadButton = document.getElementById('download-button');
    const currentFileBadge = document.getElementById('current-file-badge');
    const audioPlayer = document.getElementById('audio-player');
    const alertContainer = document.getElementById('alert-container');
    
    // Form fields
    const metadataForm = document.getElementById('metadata-form');
    const titleField = document.getElementById('title');
    const artistField = document.getElementById('artist');
    const albumField = document.getElementById('album');
    const dateField = document.getElementById('date');
    const genreField = document.getElementById('genre');
    const commentField = document.getElementById('comment');
    
    // File info display
    const infoFormat = document.getElementById('info-format');
    const infoChannels = document.getElementById('info-channels');
    const infoSampleRate = document.getElementById('info-sample-rate');
    const infoBitDepth = document.getElementById('info-bit-depth');
    const infoDuration = document.getElementById('info-duration');
    
    // Current file data
    let currentFileData = null;
    
    // Setup event listeners for drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropArea.classList.add('highlight');
    }
    
    function unhighlight() {
        dropArea.classList.remove('highlight');
    }
    
    // Handle file drop
    dropArea.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const file = dt.files[0];
        handleFile(file);
    }
    
    // Handle file selection via browse button
    browseButton.addEventListener('click', () => {
        fileInput.click();
    });
    
    fileInput.addEventListener('change', () => {
        const file = fileInput.files[0];
        if (file) {
            handleFile(file);
        }
    });
    
    // Handle the selected/dropped file
    function handleFile(file) {
        // Check if file is an audio file
        const validExtensions = ['.flac', '.mp3', '.wav', '.aaf'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!validExtensions.includes(fileExtension)) {
            showAlert('Unsupported file format. Please upload FLAC, AAF, WAV, or MP3 files.', 'warning');
            return;
        }
        
        // Upload the file and extract metadata
        uploadFile(file);
    }
    
    // Upload file to the server
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        // Show upload progress
        uploadProgress.classList.remove('d-none');
        progressBar.style.width = '0%';
        progressBar.setAttribute('aria-valuenow', 0);
        
        const xhr = new XMLHttpRequest();
        
        xhr.open('POST', '/upload', true);
        
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.setAttribute('aria-valuenow', percentComplete);
            }
        });
        
        xhr.onload = function() {
            if (xhr.status === 200) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    currentFileData = response;
                    
                    // Update the UI with the metadata
                    displayMetadata(response);
                    
                    // Hide progress and show editor
                    setTimeout(() => {
                        uploadProgress.classList.add('d-none');
                        metadataEditor.classList.remove('d-none');
                        
                        // Update audio player source
                        updateAudioPlayer();
                        
                        // Scroll to the editor
                        metadataEditor.scrollIntoView({ behavior: 'smooth' });
                    }, 500);
                    
                } catch (error) {
                    console.error('Error parsing response:', error);
                    showAlert('Error processing file metadata.', 'danger');
                    uploadProgress.classList.add('d-none');
                }
            } else {
                let errorMessage = 'Error uploading file.';
                try {
                    const response = JSON.parse(xhr.responseText);
                    if (response.error) {
                        errorMessage = response.error;
                    }
                } catch (e) {
                    // If can't parse the error, use the default message
                }
                
                showAlert(errorMessage, 'danger');
                uploadProgress.classList.add('d-none');
            }
        };
        
        xhr.onerror = function() {
            showAlert('Network error occurred during upload.', 'danger');
            uploadProgress.classList.add('d-none');
        };
        
        xhr.send(formData);
    }
    
    // Display metadata in the UI
    function displayMetadata(metadata) {
        // Set file name in the badge
        currentFileBadge.textContent = metadata.filename;
        
        // Fill in form fields
        titleField.value = metadata.title || '';
        artistField.value = metadata.artist || '';
        albumField.value = metadata.album || '';
        dateField.value = metadata.date || '';
        genreField.value = metadata.genre || '';
        commentField.value = metadata.comment || '';
        
        // Update file information
        infoFormat.textContent = metadata.format || '-';
        infoChannels.textContent = metadata.channels || '-';
        infoSampleRate.textContent = metadata.sample_rate ? `${metadata.sample_rate / 1000} kHz` : '-';
        
        // Handle bit depth or bitrate based on format
        if (metadata.format === 'MP3') {
            infoBitDepth.textContent = metadata.bitrate ? `${Math.round(metadata.bitrate / 1000)} kbps` : '-';
        } else {
            infoBitDepth.textContent = metadata.bits_per_sample ? `${metadata.bits_per_sample} bit` : '-';
        }
        
        // Format duration
        if (metadata.length) {
            const minutes = Math.floor(metadata.length / 60);
            const seconds = Math.floor(metadata.length % 60);
            infoDuration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        } else {
            infoDuration.textContent = '-';
        }
        
        // Check if there was an error extracting metadata
        if (metadata.error) {
            showAlert(`Warning: ${metadata.error}. Some metadata fields may be incomplete.`, 'warning');
        }
    }
    
    // Update audio player source
    function updateAudioPlayer() {
        const timestamp = new Date().getTime(); // Cache buster
        audioPlayer.src = `/play?t=${timestamp}`;
        audioPlayer.load();
    }
    
    // Save metadata changes
    saveButton.addEventListener('click', function() {
        const metadata = {
            title: titleField.value,
            artist: artistField.value,
            album: albumField.value,
            date: dateField.value,
            genre: genreField.value,
            comment: commentField.value
        };
        
        // Show saving indicator
        saveButton.disabled = true;
        saveButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Saving...';
        
        fetch('/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(metadata)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('Metadata saved successfully!', 'success');
                // Update current file data with new metadata
                if (currentFileData) {
                    Object.assign(currentFileData, metadata);
                }
            } else {
                showAlert(`Error: ${data.message || 'Failed to save metadata.'}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Network error occurred while saving metadata.', 'danger');
        })
        .finally(() => {
            // Reset button state
            saveButton.disabled = false;
            saveButton.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes';
        });
    });
    
    // Download edited file
    downloadButton.addEventListener('click', function() {
        window.location.href = '/download';
    });
    
    // Show alert message
    function showAlert(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.role = 'alert';
        
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertContainer.appendChild(alertDiv);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertDiv);
            bsAlert.close();
        }, 5000);
    }
});
