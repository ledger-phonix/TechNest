// This object keeps track of our selections without reloading
const formState = {
    profession: [],
    skills: [],
    services: []
};

document.addEventListener('DOMContentLoaded', () => {
    // 1. FIRST: Hydrate existing data from the database (for Update pages)
    hydrateFormState();

    // Check for profession elements
    if (document.getElementById('profession-input')) {
        initSearch('profession-input', 'profession-suggestions', 'profession-chip', 'selected-pro-id', 'profession', 1);
        renderUI('profession', 'profession-input', 'profession-suggestions', 'profession-chip', 'selected-pro-id', 1);
    }

    // Check for skills elements
    if (document.getElementById('skills-input')) {
        initSearch('skills-input', 'skills-suggestions', 'skills-chips', 'selected-skills-data', 'skills', 4);
        renderUI('skills', 'skills-input', 'skills-suggestions', 'skills-chips', 'selected-skills-data', 4);
    }

    // Check for services elements (Only on Company page)
    if (document.getElementById('services-input')) {
        initSearch('services-input', 'services-suggestions', 'services-chips', 'selected-service-ids', 'services', 6);
        renderUI('services', 'services-input', 'services-suggestions', 'services-chips', 'selected-service-ids', 6);
    }
    // 5. Trigger initial render so existing chips appear immediately
    renderUI('profession', 'profession-input', 'profession-suggestions', 'profession-chip', 'selected-pro-id', 1);
    renderUI('skills', 'skills-input', 'skills-suggestions', 'skills-chips', 'selected-skills-data', 4);
    renderUI('services', 'services-input', 'services-suggestions', 'services-chips', 'selected-service-ids', 6);

    // 6. Initialize File Uploads
    const profilePicInput = document.getElementById('profile_pic');
    if (profilePicInput) handleFileUpload(profilePicInput, '.file-hint');

    const logoInput = document.getElementById('company_logo');
    if (logoInput) handleFileUpload(logoInput, '.file-hint');
});

/**
 * Reads data attributes from the HTML to pre-fill formState
 */
function hydrateFormState() {
    // Hydrate Profession
    const profContainer = document.getElementById('profession-chip');
    if (profContainer) {
        const id = profContainer.getAttribute('data-initial-id');
        const name = profContainer.getAttribute('data-initial-name');
        if (id && name && id !== "None" && id !== "") {
            formState.profession = [{ id: parseInt(id), name: name }];
        }
    }

    // Hydrate Skills
    const skillsContainer = document.getElementById('skills-chips');
    if (skillsContainer) {
        const ids = skillsContainer.getAttribute('data-ids');
        const names = skillsContainer.getAttribute('data-names');
        if (ids && names) {
            const idsArr = ids.split(',');
            const namesArr = names.split(',');
            formState.skills = idsArr.map((id, index) => ({
                id: parseInt(id.trim()),
                name: namesArr[index].trim()
            })).filter(item => !isNaN(item.id));
        }
    }

    // Hydrate Services (for Companies)
    const servicesContainer = document.getElementById('services-chips');
    if (servicesContainer) {
        const sIds = servicesContainer.getAttribute('data-ids');
        const sNames = servicesContainer.getAttribute('data-names');
        if (sIds && sNames) {
            const idsArr = sIds.split(',');
            const namesArr = sNames.split(',');
            formState.services = idsArr.map((id, index) => ({
                id: parseInt(id.trim()),
                name: namesArr[index].trim()
            })).filter(item => !isNaN(item.id));
        }
    }
}

function initSearch(inputId, suggId, chipContainerId, hiddenId, type, limit) {
    const input = document.getElementById(inputId);
    const suggBox = document.getElementById(suggId);

    if (!input || !suggBox) return;

    input.addEventListener('input', async (e) => {
        const query = e.target.value.trim();
        if (query.length < 2) {
            suggBox.style.display = 'none';
            return;
        }

        try {
            const response = await fetch(`/api/get-suggestions?type=${type}&q=${query}`);
            if (!response.ok) throw new Error(`Server Error: ${response.status}`);
            const data = await response.json();

            if (data.length > 0) {
                const safeName = (name) => name.replace(/'/g, "\\'");
                suggBox.innerHTML = data.map(item => `
                    <div class="suggestion-item" onclick="selectItem('${type}', ${item.id}, '${safeName(item.name)}', '${inputId}', '${suggId}', '${chipContainerId}', '${hiddenId}', ${limit})">
                        ${item.name}
                    </div>
                `).join('');
                suggBox.style.display = 'block';
            } else {
                suggBox.style.display = 'none';
            }
        } catch (err) {
            console.error("Search error:", err);
        }
    });

    document.addEventListener('click', (e) => {
        if (input && !e.target.closest('.search-container')) {
            suggBox.style.display = 'none';
        }
    });
}

window.selectItem = function (type, id, name, inputId, suggId, chipContainerId, hiddenId, limit) {
    if (formState[type].some(item => item.id === id)) return;

    if (limit === 1) {
        formState[type] = [{ id, name }];
    } else if (formState[type].length < limit) {
        formState[type].push({ id, name });
    }

    renderUI(type, inputId, suggId, chipContainerId, hiddenId, limit);
};

window.removeChip = function (type, id, inputId, suggId, chipContainerId, hiddenId, limit) {
    formState[type] = formState[type].filter(item => item.id !== id);
    renderUI(type, inputId, suggId, chipContainerId, hiddenId, limit);
};

function renderUI(type, inputId, suggId, chipContainerId, hiddenId, limit) {
    const container = document.getElementById(chipContainerId);
    const hiddenInput = document.getElementById(hiddenId);
    const inputField = document.getElementById(inputId);

    if (!container || !hiddenInput || !inputField) return;

    container.innerHTML = formState[type].map(item => `
        <div class="chip">
            ${item.name}
            <i class="fas fa-times remove-icon" 
                onclick="removeChip('${type}', ${item.id}, '${inputId}', '${suggId}', '${chipContainerId}', '${hiddenId}', ${limit})"></i>
        </div>
    `).join('');

    hiddenInput.value = formState[type].map(item => item.id).join(',');

    if (formState[type].length >= limit) {
        inputField.style.display = 'none';
    } else {
        inputField.style.display = 'block';
        inputField.value = '';
    }

    const sBox = document.getElementById(suggId);
    if (sBox) sBox.style.display = 'none';
}
/**
 * @param {HTMLInputElement} inputElement - The file input
 * @param {string} hintSelector - Class for the status text
 * @param {string} previewId - ID of the img tag to update
 */
function handleFileUpload(inputElement, hintSelector, previewId = null) {
    if (!inputElement) return;

    // Robust container search for both Signup and Dashboard layouts
    const container = inputElement.closest('.form-group') || 
                      inputElement.closest('.profile-upload-container') || 
                      inputElement.closest('.file-upload-wrapper') ||
                      inputElement.parentElement;
                      
    const hint = container.querySelector(hintSelector);
    const originalHint = hint ? hint.textContent : "JPG, PNG or WEBP only.";
    const previewImg = previewId ? document.getElementById(previewId) : null;

    inputElement.addEventListener('change', function () {
        const file = this.files[0];
        const maxSize = 2 * 1024 * 1024; // 2MB calculation: $2 \times 1024 \times 1024$ bytes
        const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];

        if (file) {
            if (!allowedTypes.includes(file.type)) {
                // ERROR: Wrong Type
                updateStatus(hint, inputElement, `❌ Invalid format: ${file.type.split('/')[1].toUpperCase()}`, "#ff4d4d", previewImg);
            } else if (file.size > maxSize) {
                // ERROR: Too Big
                updateStatus(hint, inputElement, "❌ File too heavy! Max 2MB.", "#ff4d4d", previewImg);
            } else {
                // SUCCESS: Show filename and preview
                updateStatus(hint, inputElement, `✅ Selected: ${file.name}`, "#2ecc71", previewImg, file);
            }
        } else {
            // RESET: User cancelled or cleared
            if (hint) {
                hint.textContent = originalHint;
                hint.style.color = "";
            }
            if (previewImg) previewImg.style.borderColor = "";
        }
    });
}

function updateStatus(hintEl, inputEl, message, color, previewImg, file = null) {
    if (hintEl) {
        hintEl.textContent = message;
        hintEl.style.color = color;
    }

    // Feedback for the input or the preview border
    if (inputEl.offsetParent !== null) {
        // Visible input (Signup form)
        inputEl.style.borderColor = color;
    } else if (previewImg) {
        // Hidden input (Dashboard) - apply color to the image border instead
        previewImg.style.borderColor = color;
    }

    if (color === "#ff4d4d") {
        inputEl.value = ""; // Clear invalid file
    } else if (file && previewImg) {
        // Handle image preview for the dashboard
        const reader = new FileReader();
        reader.onload = (e) => {
            previewImg.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }
}
// function handleFileUpload(inputElement, hintSelector) {
//     const container = inputElement.closest('.form-group') || inputElement.parentElement;
//     const hint = container.querySelector(hintSelector);
//     const originalHint = hint ? hint.textContent : "JPG, PNG or WEBP only.";

//     inputElement.addEventListener('change', function () {
//         const file = this.files[0];
//         const maxSize = 2 * 1024 * 1024; // 2MB
//         const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];

//         if (file) {
//             if (!allowedTypes.includes(file.type)) {
//                 updateStatus(hint, inputElement, "❌ JPG, PNG or WEBP only!", "#ff4d4d");
//             } else if (file.size > maxSize) {
//                 updateStatus(hint, inputElement, "❌ File too heavy! Max 2MB.", "#ff4d4d");
//             } else {
//                 updateStatus(hint, inputElement, "✅ File accepted!", "#2ecc71");
//             }
//         } else {
//             if (hint) {
//                 hint.textContent = originalHint;
//                 hint.style.color = "";
//             }
//             inputElement.style.borderColor = "";
//         }
//     });
// }

// function updateStatus(hintEl, inputEl, message, color) {
//     if (hintEl) {
//         hintEl.textContent = message;
//         hintEl.style.color = color;
//     }
//     inputEl.style.borderColor = color;
//     if (color === "#ff4d4d") inputEl.value = "";
// }