// API Configuration
const API_URL = 'http://localhost:8002'; // Change to your API URL if different

// Session management
let currentSessionId = null;
let pendingClarification = null;
let currentUsername = null;

// Initialize: Check for stored username or show modal
function initializeApp() {
    // Check if username is stored in localStorage
    const storedUsername = localStorage.getItem('gst_username');
    
    if (storedUsername) {
        currentUsername = storedUsername;
        showMainApp();
    } else {
        showUsernameModal();
    }
}

function showUsernameModal() {
    const modal = document.getElementById('username-modal');
    const mainContainer = document.getElementById('main-container');
    
    if (modal) {
        modal.style.display = 'flex';
    }
    if (mainContainer) {
        mainContainer.style.display = 'none';
    }
}

function showMainApp() {
    const modal = document.getElementById('username-modal');
    const mainContainer = document.getElementById('main-container');
    const usernameDisplay = document.getElementById('username-display');
    
    if (modal) {
        modal.style.display = 'none';
    }
    if (mainContainer) {
        mainContainer.style.display = 'flex';
    }
    if (usernameDisplay && currentUsername) {
        usernameDisplay.textContent = currentUsername;
    }
}

// Handle username form submission
const usernameForm = document.getElementById('username-form');
if (usernameForm) {
    usernameForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const usernameInput = document.getElementById('username-input');
        const username = usernameInput.value.trim();
        
        if (username) {
            currentUsername = username;
            localStorage.setItem('gst_username', username);
            showMainApp();
        }
    });
}

// Handle change user button
const changeUserBtn = document.getElementById('change-user-btn');
if (changeUserBtn) {
    changeUserBtn.addEventListener('click', () => {
        localStorage.removeItem('gst_username');
        currentUsername = null;
        currentSessionId = null;
        pendingClarification = null;
        showUsernameModal();
    });
}

// Initialize app on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

// DOM Elements
const form = document.getElementById('query-form');
const questionInput = document.getElementById('question-input');
const messagesDiv = document.getElementById('messages');
const submitBtn = document.getElementById('submit-btn');
const btnText = document.getElementById('btn-text');
const btnSpinner = document.getElementById('btn-spinner');

// Remove welcome message when user starts typing
questionInput.addEventListener('focus', () => {
    const welcomeMsg = messagesDiv.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
});

// Handle form submission
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const question = questionInput.value.trim();
    if (!question) return;
    
    // Remove welcome message if still present
    const welcomeMsg = messagesDiv.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
    
    // Add user message
    addMessage(question, 'user');
    questionInput.value = '';
    
    // Disable form and show loading
    setLoading(true);
    
    try {
        const requestBody = {
            question: question,
            force_refresh: false
        };
        
        // Include session_id if we have one
        if (currentSessionId) {
            requestBody.session_id = currentSessionId;
        }
        
        // Include username if we have one
        if (currentUsername) {
            requestBody.username = currentUsername;
        }
        
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get response');
        }
        
        const data = await response.json();
        
        // Store session_id for future requests
        if (data.session_id) {
            currentSessionId = data.session_id;
        }
        
        // Handle clarification state
        if (data.requires_clarification) {
            pendingClarification = {
                question: data.pending_question,
                clarification: data.clarification_question
            };
            updateClarificationUI(true);
            addMessage(data.answer, 'assistant', true);
        } else {
            // Clear clarification state if we got a normal answer
            if (pendingClarification) {
                pendingClarification = null;
                updateClarificationUI(false);
            }
            addMessage(data.answer, 'assistant', false);
        }
        
    } catch (error) {
        console.error('Error:', error);
        addMessage(
            `Error: ${error.message}. Please make sure the API server is running on ${API_URL}`,
            'error'
        );
    } finally {
        setLoading(false);
    }
});

function addMessage(text, type, isClarification = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    // Add clarification indicator class if needed
    if (isClarification) {
        messageDiv.classList.add('clarification-needed');
    }
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    // Format the text (preserve line breaks)
    const formattedText = text.split('\n').map(line => {
        if (line.trim() === '') return '<br>';
        return line;
    }).join('\n');
    
    content.innerHTML = formattedText.replace(/\n/g, '<br>');
    
    // Add clarification badge if needed
    if (isClarification) {
        const badge = document.createElement('div');
        badge.className = 'clarification-badge';
        badge.textContent = '⚠️ Clarification Needed';
        messageDiv.appendChild(badge);
    }
    
    messageDiv.appendChild(content);
    messagesDiv.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function updateClarificationUI(needsClarification) {
    if (needsClarification && pendingClarification) {
        // Update placeholder to indicate clarification is needed
        questionInput.placeholder = `Please answer: ${pendingClarification.clarification}`;
        questionInput.classList.add('clarification-pending');
    } else {
        // Reset placeholder
        questionInput.placeholder = 'Ask your question about GST regulations...';
        questionInput.classList.remove('clarification-pending');
    }
}

function setLoading(loading) {
    submitBtn.disabled = loading;
    questionInput.disabled = loading;
    btnText.style.display = loading ? 'none' : 'inline';
    btnSpinner.style.display = loading ? 'inline' : 'none';
    
    if (loading) {
        submitBtn.classList.add('loading');
    } else {
        submitBtn.classList.remove('loading');
    }
}

// Allow Enter to submit (Shift+Enter for new line)
questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.dispatchEvent(new Event('submit'));
    }
});

