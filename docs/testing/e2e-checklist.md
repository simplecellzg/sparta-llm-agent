# E2E Testing Checklist

## Theme System
- [ ] Page loads with default dark theme
- [ ] Theme toggle button switches to light theme
- [ ] Theme preference persists across page refreshes
- [ ] All UI components adapt to theme changes
- [ ] No visual glitches during theme transition

## DSMC Workflow
- [ ] User can request DSMC input generation
- [ ] LLM generates valid SPARTA input file
- [ ] Control panel appears with correct data
- [ ] Input file preview loads
- [ ] File list shows all necessary files
- [ ] Template selector works correctly
- [ ] Validation provides real-time feedback
- [ ] Atmospheric calculator updates form
- [ ] Run simulation button triggers execution
- [ ] Progress updates appear in real-time (SSE)
- [ ] Logs stream correctly
- [ ] Simulation completes successfully
- [ ] Version history updates

## File Upload
- [ ] Upload modal opens on file selection
- [ ] File validation runs automatically
- [ ] Validation errors display clearly
- [ ] Reference mode extracts parameters
- [ ] Direct run mode shows configuration options
- [ ] Direct run executes with custom parameters
- [ ] Both paths create proper session

## Version Control
- [ ] Version list shows all iterations
- [ ] Active version highlighted correctly
- [ ] View button shows iteration details
- [ ] Restore button switches active version
- [ ] Compare button opens comparison modal
- [ ] Comparison shows differences correctly
- [ ] Delete button removes iteration
- [ ] Cannot delete active iteration
- [ ] Export comparison downloads markdown

## Settings Management
- [ ] Settings panel opens correctly
- [ ] Current settings load and display
- [ ] API key masking works
- [ ] Visibility toggle reveals/hides key
- [ ] Test connection validates credentials
- [ ] Runtime save updates settings temporarily
- [ ] Permanent save writes to .env
- [ ] Settings persist after browser refresh
- [ ] Page reload applies permanent changes

## Real-Time Updates (SSE)
- [ ] SSE connection establishes on session start
- [ ] Heartbeat keeps connection alive
- [ ] Progress events update UI
- [ ] Completion events trigger notifications
- [ ] Error events show failure messages
- [ ] Connection recovers after network interruption
- [ ] Multiple tabs/clients receive updates

## Chat UI
- [ ] User messages align right
- [ ] Assistant messages align left
- [ ] Bubbles adapt to content size
- [ ] Markdown renders correctly
- [ ] Code blocks have syntax highlighting
- [ ] LaTeX formulas render with KaTeX
- [ ] Images display inline
- [ ] Conversation list updates

## Edge Cases
- [ ] Long file paths don't break layout
- [ ] Large log files scroll smoothly
- [ ] Many iterations don't slow down UI
- [ ] Network errors show user-friendly messages
- [ ] Invalid input shows clear validation errors
- [ ] Concurrent simulations handle correctly

## Performance
- [ ] Initial page load < 2s
- [ ] Theme toggle feels instant
- [ ] Modal open/close smooth (no jank)
- [ ] Log streaming doesn't freeze UI
- [ ] Large iteration lists render quickly

## Browser Compatibility
- [ ] Chrome latest - all features work
- [ ] Firefox latest - all features work
- [ ] Safari latest - all features work (if applicable)
- [ ] Edge latest - all features work

## Security
- [ ] API keys are masked in settings panel
- [ ] No sensitive data in browser console
- [ ] No XSS vulnerabilities in markdown rendering
- [ ] File paths are validated before use
- [ ] Command injection prevented in file operations

## Accessibility
- [ ] Keyboard navigation works for all controls
- [ ] Tab order is logical
- [ ] Focus indicators are visible
- [ ] ARIA labels present on interactive elements
- [ ] Screen reader friendly (basic support)

## Error Recovery
- [ ] App recovers from SSE connection loss
- [ ] Invalid API responses show clear errors
- [ ] File system errors display helpful messages
- [ ] Simulation failures report error details
- [ ] Network timeouts handled gracefully

## Data Persistence
- [ ] Theme preference saved to localStorage
- [ ] Settings saved to runtime or .env as configured
- [ ] Session data persists across page reloads
- [ ] Iteration history maintained correctly
- [ ] No data loss during normal operation

## Testing Notes

### How to Test
1. Start the Flask application: `cd llm-chat-app && python app.py`
2. Open browser to `http://localhost:21000`
3. Work through each section systematically
4. Mark items as completed (✓) or failed (✗)
5. Note any bugs or issues in the section below

### Bug Reports
Use this format for any issues found:

```
Bug #1: [Short description]
Steps to reproduce:
1. ...
2. ...
Expected: ...
Actual: ...
Severity: [Critical/High/Medium/Low]
```

### Test Environment
- Browser: [Chrome/Firefox/Safari/Edge]
- Version: [Browser version]
- OS: [Linux/Mac/Windows]
- Date: [Test date]
- Tester: [Name]

### Sign-off
- [ ] All critical features tested
- [ ] All bugs documented
- [ ] No critical issues blocking release
- [ ] Ready for production deployment

Tester signature: ________________  Date: ________
