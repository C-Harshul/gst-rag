# Frontend Implementation: Expandable Details Block

## Overview
The LLM response format has been updated to include expandable details blocks for simple factual questions. The frontend needs to detect, parse, and display these blocks appropriately.

## Response Format Structure

### For Simple Factual Questions:
```
Brief Insight: [2-4 sentence answer]

[EXPANDABLE_DETAILS_START]
📖 Exact Provisions from Bare-Law Book

"[exact quoted clause]" [1] - Page 15, Line 3
"[another quoted clause]" [1] - Page 15, Line 5
[EXPANDABLE_DETAILS_END]

References:
[1] Bare-Law Book - Document: bare-law.pdf, Page: 15, Line: 3-5
```

## Detection Logic

### Step 1: Check if response contains expandable block
Look for the markers:
- `[EXPANDABLE_DETAILS_START]` - marks the beginning
- `[EXPANDABLE_DETAILS_END]` - marks the end

### Step 2: Parse the response
1. **Extract the brief answer**: Everything before `[EXPANDABLE_DETAILS_START]`
2. **Extract expandable content**: Everything between `[EXPANDABLE_DETAILS_START]` and `[EXPANDABLE_DETAILS_END]`
3. **Extract references**: Everything after `[EXPANDABLE_DETAILS_END]` (if present)

## Implementation Requirements

### Display Behavior:
1. **Always show**: The brief insight/answer (content before `[EXPANDABLE_DETAILS_START]`)
2. **Collapsible/Expandable**: The content between the markers should be in an expandable section
3. **Show references**: Display the References section (if present) after the expandable block

### UI/UX Suggestions:
- Add a clickable button/link like "📖 View Exact Provisions from Bare-Law Book" or "Show Details"
- Use a collapsible/accordion component
- Show a visual indicator (arrow, chevron, etc.) that changes when expanded/collapsed
- Style the expandable section differently (e.g., indented, different background color, border)

## Example Implementation (Pseudocode)

```javascript
function parseResponse(responseText) {
    const expandableStart = '[EXPANDABLE_DETAILS_START]';
    const expandableEnd = '[EXPANDABLE_DETAILS_END]';
    
    if (responseText.includes(expandableStart) && responseText.includes(expandableEnd)) {
        // Split the response into parts
        const startIndex = responseText.indexOf(expandableStart);
        const endIndex = responseText.indexOf(expandableEnd);
        
        const briefAnswer = responseText.substring(0, startIndex).trim();
        const expandableContent = responseText.substring(
            startIndex + expandableStart.length,
            endIndex
        ).trim();
        const references = responseText.substring(endIndex + expandableEnd.length).trim();
        
        return {
            hasExpandable: true,
            briefAnswer: briefAnswer,
            expandableContent: expandableContent,
            references: references
        };
    } else {
        // No expandable block, return full response
        return {
            hasExpandable: false,
            fullResponse: responseText
        };
    }
}

function renderResponse(parsed) {
    if (parsed.hasExpandable) {
        // Render brief answer
        renderBriefAnswer(parsed.briefAnswer);
        
        // Render expandable section
        renderExpandableSection(parsed.expandableContent);
        
        // Render references
        renderReferences(parsed.references);
    } else {
        // Render full response normally
        renderFullResponse(parsed.fullResponse);
    }
}
```

## Example HTML Structure

```html
<div class="response">
    <!-- Brief Answer (always visible) -->
    <div class="brief-answer">
        [Brief insight text here]
    </div>
    
    <!-- Expandable Section -->
    <details class="expandable-details">
        <summary>
            <strong>📖 View Exact Provisions from Bare-Law Book</strong>
        </summary>
        <div class="expandable-content">
            [Content between EXPANDABLE_DETAILS_START and END]
        </div>
    </details>
    
    <!-- References (if present) -->
    <div class="references">
        [References section]
    </div>
</div>
```

## CSS Styling Suggestions

```css
.brief-answer {
    margin-bottom: 15px;
    font-size: 1.1em;
    line-height: 1.6;
}

.expandable-details {
    margin: 15px 0;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background: #f8f9fa;
}

.expandable-details summary {
    padding: 12px;
    cursor: pointer;
    font-weight: 600;
    color: #667eea;
    user-select: none;
}

.expandable-details[open] {
    background: #ffffff;
}

.expandable-content {
    padding: 15px;
    border-top: 1px solid #e0e0e0;
}

.references {
    margin-top: 20px;
    padding-top: 15px;
    border-top: 1px solid #e0e0e0;
    font-size: 0.9em;
    color: #666;
}
```

## Edge Cases to Handle

1. **Missing markers**: If only one marker is present, treat as regular response
2. **Multiple blocks**: If multiple expandable blocks exist, handle each separately
3. **Empty expandable content**: Still show the expandable section but indicate it's empty
4. **No brief answer**: If response starts with `[EXPANDABLE_DETAILS_START]`, show a default message
5. **Markers in wrong order**: Validate that START comes before END

## Testing Examples

### Test Case 1: Response with expandable block
```
Input: "Brief Insight: GST registration is mandatory for businesses above threshold.

[EXPANDABLE_DETAILS_START]
📖 Exact Provisions from Bare-Law Book

\"Section 22(1) states...\" [1] - Page 15, Line 3
[EXPANDABLE_DETAILS_END]

References:
[1] Bare-Law Book - Document: gst-act.pdf, Page: 15, Line: 3"
```

### Test Case 2: Response without expandable block
```
Input: "This is a regular response without any expandable sections."
```

## Notes

- The markers are case-sensitive: `[EXPANDABLE_DETAILS_START]` and `[EXPANDABLE_DETAILS_END]`
- The content between markers may include newlines, quotes, and special characters
- The brief answer should preserve formatting (line breaks, etc.)
- The expandable content should preserve formatting and citations

