# SPARTA LLM Agent User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Theme System](#theme-system)
3. [DSMC Workflow](#dsmc-workflow)
4. [File Upload](#file-upload)
5. [Version Control](#version-control)
6. [Settings Management](#settings-management)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### First Launch
1. Start the server: `cd llm-chat-app && python app.py`
2. Open browser: `http://localhost:21000`
3. Default theme is dark mode (can be toggled)

### Interface Overview
- **Left Sidebar**: Conversation list and new chat button
- **Center Panel**: Chat messages and input area
- **Right Panel** (DSMC mode): Control panel with file monitor and logs
- **Top Header**: Model selector, RAG toggle, DSMC button, settings

## Theme System

### Switching Themes
1. Click the theme toggle button (🌙/☀️) in header
2. Theme automatically persists to localStorage
3. All components adapt instantly

### Color Schemes
**Dark Theme (Default)**:
- Background: Deep slate (#0f172a)
- Accents: Cyan/teal (#06b6d4)
- Text: Light gray (#f1f5f9)

**Light Theme**:
- Background: White (#ffffff)
- Accents: Deep teal (#0891b2)
- Text: Dark gray (#0f172a)

## DSMC Workflow

### Generating Input Files
1. Type your request in natural language:
   - "生成一个3D超音速流输入文件,高度80km"
   - "Create SPARTA input for hypersonic re-entry"

2. AI generates SPARTA input file using templates and validation

3. Control panel appears with:
   - Working directory path
   - Generated files list
   - Input file preview

### Using Templates
1. Click "DSMC参数设置" button
2. Select from preset templates:
   - Hypersonic Flow (Re-entry)
   - Vacuum Chamber
   - Atmospheric Flight
   - Shock Tube
   - Custom

3. Adjust parameters as needed
4. Real-time validation provides feedback

### Running Simulations
1. Configure run parameters in control panel:
   - CPU Cores (1-128)
   - Max Steps (100-100000)
   - Memory Limit (GB)
   - Max Fix Attempts (0-10)

2. Click "运行仿真"
3. Monitor progress:
   - Header shows step count
   - Logs stream in real-time
   - Status tracker updates

4. On completion:
   - Results saved automatically
   - New iteration created in version history

## File Upload

### Upload and Run Directly
1. Click file upload button (📎)
2. Select SPARTA input file (.in, .sparta)
3. System validates file automatically
4. Choose handling mode:

**Reference Mode (📚)**:
- Extracts parameters to form
- Use as template for new generation
- Modify and regenerate

**Direct Run Mode (🚀)**:
- Configure run parameters
- Execute immediately
- Creates new session

### Upload Validation
- Green border: File is valid ✅
- Yellow border: Warnings (may still run) ⚠️
- Red border: Errors (must fix before run) ❌

## Version Control

### Viewing Iterations
- Version history appears in control panel
- Each iteration shows:
  - Version number (v1, v2, ...)
  - Modification description
  - Status (✅ completed, ❌ failed, ⏳ running)
  - Timing information

### Managing Versions
**View**: See detailed information about iteration
**Restore**: Switch back to previous version as active
**Compare**: Side-by-side comparison of two iterations
**Delete**: Remove iteration (cannot delete active version)
**Stop**: Halt running simulation

### Comparing Iterations
1. Click "Compare" on any iteration
2. Select two versions to compare
3. View differences:
   - Metadata table (highlighted differences)
   - Input file diff (line-by-line)
   - Results comparison (if available)
4. Export comparison as Markdown report

## Settings Management

### Opening Settings
1. Click settings button (⚙️) in header
2. Settings panel opens with current configuration

### Configuration Sections

**API Configuration**:
- API URL: Endpoint for LLM service
- API Key: Authentication key (masked for security)
- LLM Model: Select model variant
- Test Connection: Validate credentials before saving

**Runtime Parameters**:
- Max Tokens: Maximum response length
- Temperature: Creativity level (0-1)
- Default Steps: Simulation step count
- Default Cores: CPU cores for parallel execution

**RAG Configuration**:
- Enable/disable RAG retrieval
- Top-K results count

### Saving Settings

**Runtime Save**:
- Saves to `settings.json`
- Effective immediately
- Reverts to .env defaults on restart

**Permanent Save**:
- Writes to `.env` file
- Persists across restarts
- Requires server reload to apply changes

## Troubleshooting

### Common Issues

**Simulation won't start**:
- Check DSMC mode is active
- Verify input file is valid (validation passes)
- Ensure no other simulation running in same session
- Check server logs for detailed errors

**SSE connection lost**:
- Check network connectivity
- Auto-reconnect attempts every 5s
- Refresh page if persistent
- Check browser console for errors (F12)

**Theme toggle not working**:
- Clear browser cache and localStorage
- Check JavaScript console for errors (F12)
- Verify themes.css is loaded
- Try hard refresh (Ctrl+Shift+R)

**Settings not saving**:
- Check file permissions on .env file
- Verify API endpoint is reachable (test connection)
- Review server logs for errors
- Ensure ConfigManager is initialized

**Version comparison not showing**:
- Verify both iterations exist
- Check that iteration files are present
- Review browser console for errors
- Try refreshing the page

**Logs not streaming**:
- Check SSE connection is established
- Verify simulation is actually running
- Check DSMC process status
- Review server logs

### Performance Issues

**Slow page load**:
- Check network connection
- Clear browser cache
- Reduce number of open tabs
- Check server resource usage

**Laggy log display**:
- Log truncation should limit to 1000 lines automatically
- Disable auto-scroll if performance issues
- Close other resource-heavy applications

### Getting Help
- Check application logs in control panel
- Review browser console (F12 → Console tab)
- Check server terminal output
- See known issues: `docs/bugs/known-issues.md`
- Report bugs on GitHub issues page

## Advanced Features

### Keyboard Shortcuts
- `Escape`: Close modal/panel
- `Enter`: Send message (in input field)
- `Ctrl+K`: Focus search (if available)

### Browser Support
- Chrome 120+: ✅ Full support
- Firefox 120+: ✅ Full support
- Safari 17+: ⚠️ Mostly supported
- Edge 120+: ✅ Full support (Chromium)

### Data Persistence
- Theme preference: localStorage
- Settings: settings.json or .env
- Session data: `data/dsmc_sessions/`
- Conversations: `data/conversations.json`
- Iteration history: Per-session directories

### Security Notes
- API keys are masked in UI (shown as ***)
- Keys stored in .env should have restricted permissions (chmod 600)
- Never commit .env to version control
- Use environment variables in production

## Tips & Best Practices

1. **Use Templates**: Start with presets, modify as needed
2. **Validate Early**: Check validation before running long simulations
3. **Save Iterations**: Keep useful versions for comparison
4. **Monitor Resources**: Watch CPU and memory during runs
5. **Test Connections**: Verify API before critical work
6. **Regular Backups**: Export important sessions
7. **Review Logs**: Check for warnings even if simulation completes

---

**Version**: 2.0.0
**Last Updated**: 2026-01-15
**Feedback**: Report issues on GitHub
