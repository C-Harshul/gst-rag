// API Configuration
const API_URL = 'http://localhost:8002'; // Change to your API URL if different

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
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                force_refresh: false
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to get response');
        }
        
        const data = await response.json();
        addMessage(data.answer, 'assistant');
        
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

function addMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    
    const content = document.createElement('div');
    content.className = 'message-content';
    
    // Format the text (preserve line breaks)
    const formattedText = text.split('\n').map(line => {
        if (line.trim() === '') return '<br>';
        return line;
    }).join('\n');
    
    content.innerHTML = formattedText.replace(/\n/g, '<br>');
    
    messageDiv.appendChild(content);
    messagesDiv.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
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

