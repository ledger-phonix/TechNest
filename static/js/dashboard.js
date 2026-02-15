/* dashboard.js - UI & Image Management */

document.addEventListener('DOMContentLoaded', () => {

    // 1. Initialize Character Counters (from your main script.js)
    // Useful for bio/tagline length limits
    if (typeof initTextCounters === "function") {
        initTextCounters();
    }

    // 2. Profile Picture Management
    const profilePicInput = document.getElementById('profile_pic');
    const previewImg = document.getElementById('preview-img');
    const fileHint = document.querySelector('.file-hint');

    if (profilePicInput) {
        // Use your reusable validation from suggestion.js
        if (typeof handleFileUpload === "function") {
            handleFileUpload(profilePicInput, '.file-hint');
        }

        // Real-time Preview Logic
        profilePicInput.addEventListener('change', function () {
            const file = this.files[0];
            const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
            const maxSize = 2 * 1024 * 1024; // 2MB

            if (file) {
                // Validation Check
                if (!allowedTypes.includes(file.type)) {
                    if (fileHint) fileHint.style.color = 'red';
                    this.value = ''; // Reset input
                    return;
                }

                if (file.size > maxSize) {
                    if (fileHint) fileHint.innerText = 'File too large (Max 2MB)';
                    this.value = '';
                    return;
                }

                // If valid, show preview
                const reader = new FileReader();
                reader.onload = (e) => {
                    if (previewImg) {
                        previewImg.src = e.target.result;
                        previewImg.style.opacity = '1';
                    }
                };
                reader.readAsDataURL(file);

                // Reset hint color if successful
                if (fileHint) fileHint.style.color = '';
            }
        });
    }

    // 3. Form Submission Feedback
    const profileForm = document.querySelector('form[action*="update"]');
    if (profileForm) {
        profileForm.addEventListener('submit', () => {
            const submitBtn = profileForm.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';
                submitBtn.disabled = true;
            }
        });
    }
});

// 1. Put this at the VERY TOP of the file
function showFlash(message, category = 'danger') {
    const container = document.getElementById('alert-container');
    if (!container) return; // Safety check

    const alertId = 'alert-' + Date.now();
    const html = `
        <div id="${alertId}" class="alert alert-${category} alert-dismissible fade show shadow" role="alert" style="margin-bottom: 10px;">
            <i class="bi ${category === 'danger' ? 'bi-exclamation-triangle-fill' : 'bi-check-circle-fill'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', html);

    // Auto-remove after 4 seconds
    setTimeout(() => {
        const alertElement = document.getElementById(alertId);
        if (alertElement) {
            const bsAlert = new bootstrap.Alert(alertElement);
            bsAlert.close();
        }
    }, 4000);
}

document.addEventListener('DOMContentLoaded', function () {
    const chatForm = document.getElementById('chat-form');
    const chatWindow = document.getElementById('chat-window');
    const emojiBtn = document.getElementById('emoji-btn');
    const emojiPicker = document.getElementById('emoji-picker');

    // Only execute if the Chat Form exists on the current page
    if (chatForm) {
        const socket = io({
            transports: ['websocket', 'polling'],
            upgrade: true
        }); // Initialize Socket.IO connection
        const msgInput = document.getElementById('msg-input');
        const fileInput = document.getElementById('file-input');

        // --- 1. RECEIVE MESSAGE FROM SERVER ---
        socket.on('receive_community_msg', function (data) {
            const isCompany = data.role === 'company';

            // Generate File HTML if a file exists in the message
            let fileHtml = "";
            if (data.file_path) {
                const isImg = /\.(jpg|jpeg|png|gif|webp)$/i.test(data.file_path);
                if (isImg) {
                    fileHtml = `
                        <div class="mt-2">
                            <img src="${data.file_path}" class="img-fluid rounded-3 shadow-sm" style="max-height: 250px; cursor: pointer;" onclick="window.open(this.src)">
                        </div>`;
                } else {
                    fileHtml = `
                        <div class="mt-2 p-2 bg-dark bg-opacity-10 rounded border d-inline-block">
                            <a href="${data.file_path}" target="_blank" class="text-decoration-none d-flex align-items-center ${isCompany ? 'text-dark' : 'text-white'}">
                                <i class="bi bi-file-earmark-arrow-down-fill fs-4 me-2"></i>
                                <span class="small text-truncate" style="max-width: 150px;">${data.file_name}</span>
                            </a>
                        </div>`;
                }
            }

            // Construct full message bubble
            const roleParam = data.role === 'company' ? 'company' : 'individual';
            const profileUrl = `/profile/${roleParam}/${data.sender_member_id}`;

            const messageHtml = `
    <div class="msg-row ${isCompany ? 'row-right' : 'row-left'}">
        <div class="msg-bubble ${isCompany ? 'bubble-gold' : 'bubble-blue'}">
            <div class="msg-meta d-flex align-items-center ${isCompany ? 'justify-content-end' : 'justify-content-start'}">
                <a href="${profileUrl}"  class="msg-author-link d-flex align-items-center text-decoration-none" style="color: inherit;">
                    ${!isCompany ? `<img src="${data.avatar}" class="rounded-circle me-1" width="20" height="20">` : ''}
                    <span class="msg-author">${data.name}</span>
                    ${isCompany ? `<img src="${data.avatar}" class="rounded-circle ms-1" width="20" height="20">` : ''}
                </a>
            </div>
            <div class="msg-text">${data.message}</div>
            ${fileHtml}
            <div class="msg-time">${data.time}</div>
        </div>
    </div>
`;

            chatWindow.insertAdjacentHTML('beforeend', messageHtml);

            // Auto-scroll to bottom
            chatWindow.scrollTo({
                top: chatWindow.scrollHeight,
                behavior: 'smooth'
            });
        });

        // --- 2. SEND TEXT MESSAGE ---
        chatForm.onsubmit = function (e) {
            e.preventDefault();
            const message = msgInput.value.trim();
            if (message) {
                socket.emit('send_community_msg', { message: message });
                msgInput.value = '';
                msgInput.focus();
                if (emojiPicker) emojiPicker.classList.add('d-none');
            }
        };

        // --- 3. FILE UPLOAD LOGIC ---
        if (fileInput) {
            fileInput.onchange = async function () {
                if (!this.files[0]) return;

                const file = this.files[0];
                const fileName = file.name.toLowerCase();

                // Define allowed extensions
                const allowedExtensions = ['png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'zip', 'txt', 'rar'];
                const fileExtension = fileName.split('.').pop();

                // 1. Check Extension - Replaces the Security alert
                if (!allowedExtensions.includes(fileExtension)) {
                    showFlash(`<strong>Blocked:</strong> .${fileExtension} files are not allowed for security.`, "danger");
                    this.value = "";
                    return;
                }

                // 2. Check Size - Replaces the Size alert
                if (file.size > 10 * 1024 * 1024) {
                    showFlash("<strong>Large File:</strong> Maximum limit is 10MB.", "warning");
                    this.value = "";
                    return;
                }

                // ... (rest of your fetch/upload logic)


                const formData = new FormData();
                formData.append('file', file);

                try {
                    const response = await fetch('/chat/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const result = await response.json();

                    if (result.success) {
                        // Emit file info through Socket
                        socket.emit('send_community_msg', {
                            message: "",
                            file_path: result.file_path,
                            file_name: result.file_name,
                            file_public_id: result.file_public_id
                        });
                        this.value = ""; // Clear input
                    } else {
                        alert("Upload failed: " + result.error);
                    }
                } catch (error) {
                    console.error("Upload error:", error);
                }
            };
        }
        window.onbeforeunload = function () {
            socket.disconnect();
        };

        // --- 4. EMOJI PICKER LOGIC ---
        if (emojiBtn && emojiPicker) {
            emojiBtn.onclick = (e) => {
                e.stopPropagation();
                emojiPicker.classList.toggle('d-none');
            };

            emojiPicker.querySelectorAll('.emoji').forEach(emoji => {
                emoji.onclick = () => {
                    msgInput.value += emoji.innerText;
                    msgInput.focus();
                };
            });

            // Close picker when clicking anywhere else
            document.addEventListener('click', (e) => {
                if (!emojiPicker.contains(e.target) && !emojiBtn.contains(e.target)) {
                    emojiPicker.classList.add('d-none');
                }
            });
        }
    }
});

document.addEventListener('click', function (event) {
    const sidebar = document.getElementById('sidebarMenu');
    const toggleBtn = document.querySelector('.navbar-toggler'); // The "bars" button

    // Check if the sidebar is currently open (Bootstrap adds the 'show' class)
    const isSidebarOpen = sidebar.classList.contains('show');

    // 1. If the sidebar is open
    // 2. AND the click was NOT inside the sidebar
    // 3. AND the click was NOT on the toggle button (otherwise it opens and closes instantly)
    if (isSidebarOpen && !sidebar.contains(event.target) && !toggleBtn.contains(event.target)) {

        // Use Bootstrap's built-in collapse method to hide it nicely
        const bsCollapse = new bootstrap.Collapse(sidebar, {
            toggle: false
        });
        bsCollapse.hide();
    }
});

function checkNotifications() {
    fetch('/api/unread-notifications')
        .then(response => response.json())
        .then(data => {
            const badge = document.getElementById('notif-badge-sidebar');
            if (data.count > 0) {
                badge.classList.remove('d-none'); // Show the "!"
            } else {
                badge.classList.add('d-none');    // Hide it
            }
        })
        .catch(err => console.error('Error fetching notifications:', err));
}

// Check every 30 seconds
setInterval(checkNotifications, 30000);
// Check immediately on load
document.addEventListener('DOMContentLoaded', checkNotifications);