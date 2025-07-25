# Gmail Processing Workflow

This script now includes an automated Gmail processing workflow that runs continuously after OAuth completion.

## Features

The workflow automatically:
1. ✅ Confirms Gmail connection is successful (checks for "Disconnect" button)
2. 📅 Sets date filter to "last 20 minutes"
3. ⏰ Extracts and saves the start/end time range
4. 🔄 Clicks "Scan & Auto Process" button
5. ⏳ Waits 20 minutes after the end time
6. 🔁 Repeats the entire process

## Usage

### Basic OAuth Only (Original Functionality)
```bash
python python_oauth_automation.py --password your_password
```

### OAuth + Continuous Gmail Processing Workflow
```bash
python python_oauth_automation.py --password your_password --workflow
```

### Additional Options
```bash
# Run with debug mode for more detailed logs
python python_oauth_automation.py --password your_password --workflow --debug

# Run in headless mode (no browser window)
python python_oauth_automation.py --password your_password --workflow --headless

# Use a different port
python python_oauth_automation.py --password your_password --workflow --port 8081
```

## How the Workflow Works

### Step 1: OAuth Completion
- Script performs normal Gmail OAuth authentication
- Saves access tokens to Supabase database
- If `--workflow` flag is used, keeps browser open for processing

### Step 2: Connection Confirmation
- Checks that "Connect to Gmail" button changed to "Disconnect"
- Confirms the OAuth connection was successful

### Step 3: Date Filter Setup
- Automatically finds and clicks date filter controls
- Selects "last 20 minutes" option
- Supports various UI variations and languages

### Step 4: Time Range Extraction
- Captures the actual start and end times from the filter
- Falls back to calculated times if UI extraction fails
- Format: HH:MM (24-hour format)

### Step 5: Process Execution
- Finds and clicks "Scan & Auto Process" button
- Initiates Gmail processing for the selected time range

### Step 6: Scheduling Next Cycle
- Calculates next run time (20 minutes after end time)
- Waits until the scheduled time
- Provides progress updates during wait

### Step 7: Continuous Loop
- Repeats the entire process automatically
- Handles errors gracefully with retries
- Can be stopped with Ctrl+C

## Example Output

```
🚀 Starting Gmail OAuth automation...
✅ OAuth completed successfully - tokens saved to Supabase!
🔄 Starting Gmail processing workflow...

🔄 Starting processing cycle #1
✅ Gmail connection confirmed successful
📅 Setting date filter to last 20 minutes...
⏰ Time range processed: 14:30 - 14:50
✅ Clicked Scan & Auto Process button
⏰ Next cycle scheduled for: 2025-01-15 15:10:00
⏳ Waiting 20 minutes until next cycle...

🔄 Starting processing cycle #2
...
```

## Error Handling

The workflow includes robust error handling:
- **Connection Issues**: Stops if Gmail disconnect button not found
- **UI Changes**: Falls back to calculated times if date filter UI changes
- **Processing Errors**: Retries after 5 minutes on errors
- **User Interruption**: Clean shutdown with Ctrl+C

## Stopping the Workflow

- **Graceful Stop**: Press `Ctrl+C` to stop after current cycle
- **Force Stop**: Press `Ctrl+C` twice for immediate termination
- **Browser**: Workflow will close browser automatically when stopped

## Troubleshooting

### Common Issues

1. **"Could not find disconnect button"**
   - OAuth may have failed
   - Check that Gmail connection was successful in the web interface

2. **"Could not find 'last 20 minutes' option"**
   - Web interface may have changed
   - Workflow will continue with calculated times

3. **"Could not find Scan & Auto Process button"**
   - Button text or location may have changed
   - Check the web interface manually

### Debug Mode

Run with `--debug` flag for detailed logs:
```bash
python python_oauth_automation.py --password your_password --workflow --debug
```

This will:
- Keep browser open longer for inspection
- Show detailed element search logs
- Provide more verbose error messages

## Configuration

### Environment Variables
All OAuth and Supabase configuration is loaded from `env.local`:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET` 
- `GOOGLE_REDIRECT_URI`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

### Time Settings
- **Processing Window**: 20 minutes (hardcoded)
- **Cycle Interval**: 20 minutes after end time
- **Error Retry**: 5 minutes
- **Progress Updates**: Every minute during wait

## Security Notes

- Tokens are automatically saved to Supabase with expiration tracking
- Browser stays open only for workflow duration
- All credentials are loaded from environment files
- Password is only used for initial authentication

## Advanced Usage

### Custom Scheduling
To modify the 20-minute interval, edit the `calculate_next_run_time` method in `python_oauth_automation.py`:

```python
# Add 30 minutes instead of 20
next_run = end_time + timedelta(minutes=30)
```

### Custom Filters
To use different time filters, modify the `last_20_min_selectors` in `set_date_filter_last_20_minutes` method.

## System Requirements

- Python 3.7+
- Chrome browser
- ChromeDriver (auto-managed)
- Active internet connection
- Supabase account (for token storage)
- Gmail account with appropriate permissions 