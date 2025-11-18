# Handling Long Agent Responses in Slack

## Problem
When the AI agent generates a detailed analysis (like your 15KB example), Slack has limitations:
- **3,000 character limit** per text block
- **50 blocks max** per message
- **~40KB total message size** limit

Your agent response was being truncated, causing important information to be lost.

## Solution Implemented

### 1. **Intelligent Summary Extraction**
```python
extract_executive_summary(agent_analysis)
```
- Automatically extracts key sections (Executive Summary, Root Cause, Critical Findings)
- Preserves the most important information up front
- Limits summary to ~1,800 characters to leave room for other content

### 2. **Smart Display Logic**
For responses **≤ 2,000 characters**: Show full analysis
For responses **> 2,000 characters**: Show summary with indicators

### 3. **Full Analysis Storage**
- Complete agent response stored in DynamoDB
- Length indicator shown: "📄 Full analysis: 15,234 characters"
- Data persists for 24 hours (TTL)

### 4. **"View Full Analysis" Button**
New interactive button that:
- Appears when analysis is truncated
- Shows full analysis in ephemeral message (only visible to user who clicked)
- Automatically chunks long responses into manageable blocks
- Splits at paragraph boundaries to preserve readability

## How It Works

### In the Alert Message:
```
╔════════════════════════════════════════╗
║ 🚨 ALERT: Domain Alert - nghuy.link    ║
╟────────────────────────────────────────╢
║ 🤖 AI Agent Analysis (Summary):        ║
║                                        ║
║ EXECUTIVE SUMMARY                      ║
║ ROOT CAUSE: DNS records deleted...     ║
║ CRITICAL FINDINGS                      ║
║ [Key sections preserved]               ║
╟────────────────────────────────────────╢
║ 📄 Full analysis: 15,234 characters    ║
║ Complete details stored in DynamoDB    ║
╟────────────────────────────────────────╢
║ [✅ Approve] [❌ Dismiss] [📄 View Full]║
╚════════════════════════════════════════╝
```

### When User Clicks "View Full Analysis":
- Ephemeral message appears (only to that user)
- Shows complete analysis in properly chunked sections
- Splits intelligently at section boundaries
- Includes total character count

## Code Changes

### lambda_ping_monitor.py
1. **Added**: `extract_executive_summary()` - Extracts key sections
2. **Enhanced**: `store_alert_data()` - Logs analysis length
3. **Improved**: `send_slack_notification()` - Smart truncation with "View Full" button

### lambda_approval_handler.py
1. **Added**: Handler for `view_full_analysis` action
2. **Features**:
   - Retrieves full analysis from DynamoDB
   - Chunks into 2,900 character blocks
   - Splits at line boundaries for readability
   - Returns as ephemeral message

## Benefits

✅ **No Information Loss** - Full analysis always available
✅ **Better UX** - Summary shows key info immediately
✅ **Scalable** - Handles analysis of any length
✅ **Clean Messages** - Alert card stays concise
✅ **On-Demand Detail** - Users can view full analysis when needed
✅ **Smart Chunking** - Splits at natural boundaries, not mid-sentence

## Example with Your Agent Response

Your agent response (~15KB) will now:

1. **Alert shows**:
   - Executive Summary section
   - Root Cause Analysis
   - Critical Findings table
   - Indicator: "📄 Full analysis: 15,234 characters"
   - Three buttons: Approve, Dismiss, View Full

2. **Click "View Full Analysis"**:
   - Ephemeral message with ~5-6 properly formatted blocks
   - All sections preserved: Investigation Plan, Service Status, Configuration Analysis, CloudTrail events, etc.
   - Easy to read with proper formatting

## Testing

Test with long response:
```powershell
# The agent response from agent_response.txt will now be handled properly
.\test-approval-workflow.ps1 -StackName "domain-monitor-approval"
```

Then in Slack:
1. You'll see a clean summary in the alert
2. Click "📄 View Full Analysis" to see everything
3. The ephemeral message will show the complete 15KB response in readable chunks

## Configuration

No configuration needed! The system automatically:
- Detects response length
- Extracts summaries for long responses
- Adds "View Full" button when needed
- Chunks responses intelligently

## Future Enhancements

Potential improvements:
- Export to file (for very long responses)
- Searchable analysis archive
- Analysis comparison across alerts
- AI-powered summary with Claude
