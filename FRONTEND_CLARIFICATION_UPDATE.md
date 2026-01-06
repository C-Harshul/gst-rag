# Frontend Update Guide: Clarification Feedback Loop

## Overview
The API now supports a clarification feedback loop. When the system needs clarification (e.g., "Which Act are you referring to?"), it will return a special response that your frontend should handle to maintain the conversation state.

## API Changes

### New Response Fields
The `QueryResponse` now includes three new optional fields:

```typescript
interface QueryResponse {
  answer: string;
  question: string;
  session_id: string;
  status: string;
  sources?: { [key: string]: number };
  
  // NEW FIELDS:
  requires_clarification: boolean;        // true if clarification is needed
  clarification_question?: string;        // The clarification question asked
  pending_question?: string;              // Original question awaiting clarification
}
```

### Session Management
- The API now returns a `session_id` that must be sent with subsequent requests
- Store the `session_id` and include it in all future API calls
- This maintains conversation context and clarification state

## Required Frontend Changes

### 1. Store Session ID

**Before:**
```javascript
const response = await fetch('/query', {
  method: 'POST',
  body: JSON.stringify({
    question: question,
    force_refresh: false
  })
});
```

**After:**
```javascript
let currentSessionId = null;  // Store at component/global level

const response = await fetch('/query', {
  method: 'POST',
  body: JSON.stringify({
    question: question,
    session_id: currentSessionId,  // Include session_id
    force_refresh: false
  })
});

const data = await response.json();

// Store session_id for future requests
if (data.session_id) {
  currentSessionId = data.session_id;
}
```

### 2. Handle Clarification State

**Store clarification state:**
```javascript
let pendingClarification = null;  // Store at component/global level

// After receiving response
if (data.requires_clarification) {
  pendingClarification = {
    question: data.pending_question,
    clarification: data.clarification_question
  };
} else {
  // Clear clarification state when we get a normal answer
  pendingClarification = null;
}
```

### 3. Display Clarification Indicators

**Visual indicators for clarification needed:**

```javascript
// When displaying the assistant's message
if (data.requires_clarification) {
  // Show a badge/indicator
  showClarificationBadge(data.clarification_question);
  
  // Update input placeholder
  updateInputPlaceholder(data.clarification_question);
  
  // Optionally highlight the message
  addClarificationStyling(messageElement);
}
```

**Example UI updates:**
```javascript
function displayMessage(answer, requiresClarification, clarificationQuestion) {
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message assistant';
  
  if (requiresClarification) {
    messageDiv.classList.add('clarification-needed');
    
    // Add clarification badge
    const badge = document.createElement('div');
    badge.className = 'clarification-badge';
    badge.textContent = '⚠️ Clarification Needed';
    messageDiv.appendChild(badge);
  }
  
  // Add message content
  const content = document.createElement('div');
  content.className = 'message-content';
  content.textContent = answer;
  messageDiv.appendChild(content);
  
  return messageDiv;
}
```

### 4. Update Input Placeholder

**When clarification is pending, update the input placeholder:**

```javascript
function updateInputForClarification(clarificationQuestion) {
  const input = document.getElementById('question-input');
  
  if (clarificationQuestion) {
    input.placeholder = `Please answer: ${clarificationQuestion}`;
    input.classList.add('clarification-pending');
  } else {
    input.placeholder = 'Ask your question about GST regulations...';
    input.classList.remove('clarification-pending');
  }
}
```

### 5. CSS Styling (Optional but Recommended)

**Add these styles for clarification indicators:**

```css
/* Clarification badge */
.clarification-badge {
  position: absolute;
  top: -8px;
  left: 10px;
  background: #ff9800;
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.75em;
  font-weight: 600;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  z-index: 1;
}

/* Highlight messages requiring clarification */
.message.clarification-needed {
  position: relative;
}

.message.clarification-needed .message-content {
  border: 2px solid #ff9800;
  background: #fff8e1;
}

/* Highlight input when clarification is pending */
#question-input.clarification-pending {
  border-color: #ff9800;
  background: #fff8e1;
}

#question-input.clarification-pending:focus {
  border-color: #ff9800;
  box-shadow: 0 0 0 3px rgba(255, 152, 0, 0.1);
}
```

## Complete Example Implementation

### React/Component Example

```javascript
// Component state
const [sessionId, setSessionId] = useState(null);
const [pendingClarification, setPendingClarification] = useState(null);

// API call function
async function sendQuery(question) {
  const response = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question: question,
      session_id: sessionId,
      force_refresh: false
    })
  });
  
  const data = await response.json();
  
  // Store session_id
  if (data.session_id) {
    setSessionId(data.session_id);
  }
  
  // Handle clarification state
  if (data.requires_clarification) {
    setPendingClarification({
      question: data.pending_question,
      clarification: data.clarification_question
    });
  } else {
    setPendingClarification(null);
  }
  
  return data;
}

// Render message component
function Message({ answer, requiresClarification, clarificationQuestion }) {
  return (
    <div className={`message ${requiresClarification ? 'clarification-needed' : ''}`}>
      {requiresClarification && (
        <div className="clarification-badge">
          ⚠️ Clarification Needed
        </div>
      )}
      <div className="message-content">{answer}</div>
    </div>
  );
}

// Input component
function QueryInput({ pendingClarification, onSubmit }) {
  const placeholder = pendingClarification
    ? `Please answer: ${pendingClarification.clarification}`
    : 'Ask your question about GST regulations...';
  
  return (
    <input
      type="text"
      placeholder={placeholder}
      className={pendingClarification ? 'clarification-pending' : ''}
      onKeyPress={(e) => {
        if (e.key === 'Enter') {
          onSubmit(e.target.value);
        }
      }}
    />
  );
}
```

### Vanilla JavaScript Example

```javascript
// Global state
let currentSessionId = null;
let pendingClarification = null;

// API call
async function sendQuery(question) {
  const requestBody = {
    question: question,
    force_refresh: false
  };
  
  // Include session_id if available
  if (currentSessionId) {
    requestBody.session_id = currentSessionId;
  }
  
  const response = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody)
  });
  
  const data = await response.json();
  
  // Store session_id
  if (data.session_id) {
    currentSessionId = data.session_id;
  }
  
  // Handle clarification
  if (data.requires_clarification) {
    pendingClarification = {
      question: data.pending_question,
      clarification: data.clarification_question
    };
    updateUIForClarification(data.clarification_question);
  } else {
    pendingClarification = null;
    resetUI();
  }
  
  return data;
}

// UI update functions
function updateUIForClarification(clarificationQuestion) {
  const input = document.getElementById('question-input');
  input.placeholder = `Please answer: ${clarificationQuestion}`;
  input.classList.add('clarification-pending');
}

function resetUI() {
  const input = document.getElementById('question-input');
  input.placeholder = 'Ask your question about GST regulations...';
  input.classList.remove('clarification-pending');
}

// Display message
function displayMessage(answer, requiresClarification) {
  const messagesDiv = document.getElementById('messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `message assistant ${requiresClarification ? 'clarification-needed' : ''}`;
  
  if (requiresClarification) {
    const badge = document.createElement('div');
    badge.className = 'clarification-badge';
    badge.textContent = '⚠️ Clarification Needed';
    messageDiv.appendChild(badge);
  }
  
  const content = document.createElement('div');
  content.className = 'message-content';
  content.textContent = answer;
  messageDiv.appendChild(content);
  
  messagesDiv.appendChild(messageDiv);
}
```

## User Flow

1. **User asks ambiguous question:**
   - "What is section 17(5) of GST act"
   - Frontend sends to API with session_id (or null for first request)

2. **API responds with clarification:**
   ```json
   {
     "answer": "Section 17(5) exists in multiple GST Acts... Which Act are you referring to?",
     "requires_clarification": true,
     "clarification_question": "Which Act are you referring to?",
     "pending_question": "What is section 17(5) of GST act",
     "session_id": "abc-123-def"
   }
   ```

3. **Frontend updates UI:**
   - Shows clarification badge on message
   - Updates input placeholder: "Please answer: Which Act are you referring to?"
   - Highlights input field

4. **User responds:**
   - "CGST Act"
   - Frontend sends to API with same session_id

5. **API processes combined question:**
   - Internally combines: "What is section 17(5) of CGST Act"
   - Returns final answer
   - `requires_clarification: false`

6. **Frontend resets UI:**
   - Removes clarification indicators
   - Resets placeholder
   - Shows final answer

## Important Notes

1. **Session ID is critical** - Always store and send it with requests
2. **Clarification state is per-session** - Each session maintains its own clarification state
3. **Clarifications expire** - After 5 minutes of inactivity, pending clarifications are cleared
4. **User can continue conversation** - After clarification, normal conversation continues with the same session_id

## Testing Checklist

- [ ] Session ID is stored and sent with requests
- [ ] Clarification state is detected and stored
- [ ] UI shows clarification indicators when needed
- [ ] Input placeholder updates for clarification
- [ ] User can respond to clarification
- [ ] System processes clarification response correctly
- [ ] UI resets after clarification is resolved
- [ ] Multiple clarifications in sequence work correctly
- [ ] Session persists across page refreshes (if using localStorage)

## API Endpoint

**POST** `/query`

**Request:**
```json
{
  "question": "string",
  "session_id": "string (optional)",
  "collection_name": "string (optional)",
  "force_refresh": false
}
```

**Response:**
```json
{
  "answer": "string",
  "question": "string",
  "session_id": "string",
  "status": "success",
  "sources": { "Handbook": 2, "Bare-Law": 3 },
  "requires_clarification": false,
  "clarification_question": null,
  "pending_question": null
}
```

## Questions?

If you need help implementing any part of this, refer to the reference implementation in:
- `frontend/app.js` - Complete JavaScript implementation
- `frontend/style.css` - CSS styling for clarification indicators


