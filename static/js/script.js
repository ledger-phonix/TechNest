const menuToggle = document.getElementById('mobile-menu');
const navMenu = document.getElementById('nav-menu');
const menuIcon = document.getElementById('menu-icon');

if (menuToggle) {
    menuToggle.addEventListener('click', () => {
        if (navMenu) navMenu.classList.toggle('active');

        if (menuIcon && navMenu) {
            if (navMenu.classList.contains('active')) {
                menuIcon.classList.remove('fa-bars');
                menuIcon.classList.add('fa-xmark');
            } else {
                menuIcon.classList.remove('fa-xmark');
                menuIcon.classList.add('fa-bars');
            }
        }
    });
}

const typedTextSpan = document.querySelector(".typed-text");
const textArray = ["Community", "Collaborative", "Helping", "Innovative"];
const typingDelay = 150;
const erasingDelay = 100;
const newTextDelay = 2000;
let textArrayIndex = 0;
let charIndex = 0;

function type() {
    // SAFETY CHECK: If the element doesn't exist on this page, exit the function
    if (!typedTextSpan) return;

    if (charIndex < textArray[textArrayIndex].length) {
        typedTextSpan.textContent += textArray[textArrayIndex].charAt(charIndex);
        charIndex++;
        setTimeout(type, typingDelay);
    } else {
        setTimeout(erase, newTextDelay);
    }
}

function erase() {
    // SAFETY CHECK: Exit if element is missing
    if (!typedTextSpan) return;

    if (charIndex > 0) {
        typedTextSpan.textContent = textArray[textArrayIndex].substring(0, charIndex - 1);
        charIndex--;
        setTimeout(erase, erasingDelay);
    } else {
        textArrayIndex++;
        if (textArrayIndex >= textArray.length) textArrayIndex = 0;
        setTimeout(type, typingDelay + 1100);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // Only start the animation if the element exists
    if (typedTextSpan && textArray.length) {
        setTimeout(type, newTextDelay + 250);
    }
});
// Function to handle scroll animations
function revealOnScroll() {
    const reveals = document.querySelectorAll(".reveal");

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add("active");
            }
        });
    }, {
        threshold: 0.15 // Triggers when 15% of the section is visible
    });

    reveals.forEach(element => {
        observer.observe(element);
    });
}

// Run once the DOM is loaded
document.addEventListener("DOMContentLoaded", revealOnScroll);
document.addEventListener("DOMContentLoaded", function () {
    const faqQuestions = document.querySelectorAll(".faq-question");

    faqQuestions.forEach(question => {
        question.addEventListener("click", () => {
            const faqItem = question.parentElement;

            // Optional: Close other open FAQ items (Solo Accordion mode)
            document.querySelectorAll(".faq-item").forEach(item => {
                if (item !== faqItem) {
                    item.classList.remove("active");
                }
            });

            // Toggle the clicked item
            faqItem.classList.toggle("active");
        });
    });
});

// signup page role base selection
document.addEventListener('DOMContentLoaded', () => {
    const roleRadios = document.querySelectorAll('input[name="role"]');
    const nameContainer = document.getElementById('dynamic-name-container');

    if (nameContainer) {
        roleRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                if (e.target.value === 'company') {
                    nameContainer.innerHTML = `
                        <div class="form-group">
                            <label for="company_name">Company Name</label>
                            <input type="text" id="company_name" name="company_name" required placeholder="TechNest Solutions Ltd.">
                        </div>`;
                } else {
                    nameContainer.innerHTML = `
                        <div class="form-row">
                            <div class="form-group">
                                <label for="fname">First Name</label>
                                <input type="text" id="fname" name="fname" required placeholder="John">
                            </div>
                            <div class="form-group">
                                <label for="lname">Last Name</label>
                                <input type="text" id="lname" name="lname" required placeholder="Doe">
                            </div>
                        </div>`;
                }
            });
        });
    }
});
// signup page and password validation
document.addEventListener("DOMContentLoaded", () => {
    const pwd = document.getElementById('password');
    const confirmPwd = document.getElementById('confirm-password');
    const strengthBar = document.getElementById('strength-bar');
    const matchText = document.getElementById('match-text');
    const submitBtn = document.getElementById('submit-btn');
    const toggles = document.querySelectorAll('.toggle-password');

    // --- CRITICAL FIX: Only run if we are actually on the Signup page ---
    if (!pwd || !confirmPwd) {
        return; // Exit the function early if password fields aren't found
    }

    // 1. Dual Eye Toggle
    toggles.forEach(eye => {
        eye.addEventListener('click', () => {
            const targetId = eye.getAttribute('data-target');
            const input = document.getElementById(targetId);
            if (input) {
                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);
                eye.classList.toggle('fa-eye-slash');
            }
        });
    });

    // inside your success logic in your other JS files.
    // 2. Comprehensive Validation Function
    function validatePasswords() {
        const val = pwd.value;
        const confVal = confirmPwd.value;
        let score = 0;

        const requirements = {
            length: val.length >= 8,
            uppercase: /[A-Z]/.test(val),
            lowercase: /[a-z]/.test(val),
            number: /[0-9]/.test(val),
            special: /[^A-Za-z0-9]/.test(val)
        };

        // Update Checklist
        Object.keys(requirements).forEach(id => {
            const el = document.getElementById(id);
            // SAFETY CHECK: Only update if the checklist element exists
            if (el) {
                if (requirements[id]) {
                    el.classList.add('valid');
                    score++;
                } else {
                    el.classList.remove('valid');
                }
            }
        });

        // Update Strength Bar (Safety check for strengthBar)
        if (strengthBar) {
            strengthBar.className = "";
            if (score <= 2) strengthBar.classList.add('weak');
            else if (score <= 4) strengthBar.classList.add('good');
            else if (score === 5) strengthBar.classList.add('strong');
            strengthBar.style.width = (score * 20) + "%";
        }

        // Check Match
        if (matchText && confVal.length > 0) {
            if (val === confVal && score === 5) {
                matchText.textContent = "Passwords match and are strong!";
                matchText.className = "status-text match-success";
                if (submitBtn) submitBtn.disabled = false;
            } else {
                matchText.textContent = val !== confVal ? "Passwords do not match" : "Password not strong enough";
                matchText.className = "status-text match-fail";
                if (submitBtn) submitBtn.disabled = true;
            }
        }
    }

    pwd.addEventListener('input', validatePasswords);
    confirmPwd.addEventListener('input', validatePasswords);
});

// opt verification script
// 1. Auto-focus jumping logic for the 6 boxes
const inputs = document.querySelectorAll('.otp-field');
const fullOtpInput = document.getElementById('full-otp');

inputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
        if (e.target.value.length === 1 && index < inputs.length - 1) {
            inputs[index + 1].focus();
        }
        combineOtp();
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && !e.target.value && index > 0) {
            inputs[index - 1].focus();
        }
    });
});

function combineOtp() {
    let code = "";
    inputs.forEach(input => code += input.value);
    fullOtpInput.value = code;
}
// 2. 5-Minute Countdown Timer
const countdownEl = document.getElementById('countdown');
// ONLY start the timer if the element exists on the current page
if (countdownEl) {
    let time = 300; // 5 minutes in seconds (5 * 60)

    const timer = setInterval(() => {
        let minutes = Math.floor(time / 60);
        let seconds = time % 60;
        seconds = seconds < 10 ? '0' + seconds : seconds;

        countdownEl.innerHTML = `${minutes}:${seconds}`;
        time--;

        if (time < 0) {
            clearInterval(timer);
            countdownEl.innerHTML = "Expired";
            countdownEl.style.color = "red";
        }
    }, 1000);
}


// load more button functionality
document.addEventListener('DOMContentLoaded', function () {
    // 1. Members Initialization
    if (document.getElementById('load-more-members-btn')) {
        setupLoadMore('load-more-members-btn', 'members-grid-container', '/load-more-members', 20);
    }

    // 2. Companies Initialization
    if (document.getElementById('load-more-companies-btn')) {
        setupLoadMore('load-more-companies-btn', 'companies-grid-container', '/load-more-companies', 20);
    }

    // 3. Jobs Initialization
    if (document.getElementById('load-more-jobs-btn')) {
        setupLoadMore('load-more-jobs-btn', 'jobs-grid-container', '/load-more-jobs', 20);
    }
});

function setupLoadMore(btnId, containerId, apiUrl, limit) {
    const btn = document.getElementById(btnId);
    const container = document.getElementById(containerId);
    
    // Use Number() to catch the "0" or "NaN" issue
    const totalCount = Number(btn.getAttribute('data-total')) || 0;
    const currentOffset = Number(btn.getAttribute('data-offset')) || 0;

    // console.log(`[${btnId}] Status -> Total in DB: ${totalCount}, Current Offset: ${currentOffset}`);

    // if (totalCount <= currentOffset && totalCount !== 0)
    if (totalCount <= currentOffset)
         {
        // console.log(`[${btnId}] Hiding: All data already loaded.`);
        btn.style.display = 'none';
        return;
    }

    btn.addEventListener('click', function () {
        const offset = parseInt(this.getAttribute('data-offset'));
        // console.log(`[${btnId}] Requesting data from ${apiUrl} with offset ${offset}`);

        this.disabled = true;

        fetch(`${apiUrl}?offset=${offset}`)
            .then(response => response.text())
            .then(html => {
                if (html.trim().length > 10) {
                    container.insertAdjacentHTML('beforeend', html);
                    const nextOffset = offset + limit;
                    this.setAttribute('data-offset', nextOffset);
                    this.disabled = false;

                    if (nextOffset >= totalCount) {
                        this.style.display = 'none';
                    }
                } else {
                    // console.log(`[${btnId}] Server returned empty HTML.`);
                    this.style.display = 'none';
                }
            })
            .catch(err => {
                console.error(`[${btnId}] Fetch Error:`, err);
                this.style.display = 'none';
            });
    });
}


/**
 * TechNest Text Area Counter -
 */
const initTextCounters = () => {
    const textareas = document.querySelectorAll('.counted-text');

    // Debugging: This will tell us exactly what the script sees
    // console.log(`[TechNest] Found ${textareas.length} counters to initialize.`);

    textareas.forEach((textarea) => {
        if (textarea.dataset.counterInitialized) return;

        // Using closest('.form-group') matches your HTML perfectly
        const parent = textarea.closest('.form-group');
        const counterSpan = parent ? parent.querySelector('.current') : null;

        if (counterSpan) {
            const updateCount = () => {
                const length = textarea.value.length;
                const max = textarea.getAttribute('maxlength') || 200;

                counterSpan.textContent = length;

                // Style logic
                if (length >= max) {
                    counterSpan.style.color = "#ff4b2b"; // Red if at limit
                    counterSpan.style.fontWeight = "bold";
                } else {
                    counterSpan.style.color = "#007fff"; // TechNest Blue
                    counterSpan.style.fontWeight = "normal";
                }
            };

            textarea.addEventListener('input', updateCount);
            textarea.dataset.counterInitialized = "true";
            updateCount(); // Initial check
        }
    });
};
// This tells the browser: "Wait until the HTML is loaded, then run the code"
document.addEventListener('DOMContentLoaded', () => {
    initTextCounters();
});