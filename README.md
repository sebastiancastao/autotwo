# Gmail OAuth Automation

Automatically handles Google OAuth authentication for Gmail with eternal 20-minute processing cycles.

## 🌟 Features

- ✅ **Eternal Processing**: Runs every 20 minutes forever
- 🔄 **Auto-restart**: Never stops, automatically retries on errors
- 🤖 **Fully Automated**: Zero manual intervention required
- 🌐 **Cloud Ready**: Deploy to Render with one click
- 📊 **Web Dashboard**: Monitor automation via web interface
- 🔐 **Secure OAuth**: Handles Google OAuth authentication automatically
- 🛡️ **Error Resistant**: Continues working despite UI changes or network issues

## 🚀 Quick Start

### Local Usage (Original)

```bash
# Simple eternal automation
start_eternal_automation.bat

# Or directly with Python
python eternal_gmail_automation.py --password YOUR_PASSWORD
```

### Cloud Deployment (New!)

Deploy to Render for 24/7 operation:

1. **Fork this repository** to your GitHub account
2. **Go to [render.com](https://render.com)** and create account
3. **Create New Blueprint** and connect your GitHub repo
4. **Set environment variables** (see `env.production.template`)
5. **Deploy** - Your automation will run eternally in the cloud!

📖 **[Complete Deployment Guide](DEPLOYMENT_GUIDE.md)**

## 📊 Web Dashboard

Once deployed, access your dashboard at:
```
https://your-app-name.onrender.com/
```

Features:
- ✅ Real-time automation status
- 📈 Cycle count and timing
- 📝 Recent activity logs
- 🔄 Start/stop controls
- 📊 API documentation

## 🔧 Local Development

### Prerequisites
- Python 3.7+
- Chrome browser
- Gmail account

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.template env.local
# Edit env.local with your credentials

# Run locally
python python_oauth_automation.py --password YOUR_PASSWORD --workflow
```

## 🏗️ Architecture

### Local Mode
```
Desktop -> Chrome Browser -> Gmail OAuth -> Processing Loop
```

### Cloud Mode (Render)
```
Web Service (FastAPI) -> Background Worker -> Chrome Headless -> Gmail OAuth -> Eternal Processing
```

## 📁 Project Structure

```
oauth-automation/
├── 🐳 Dockerfile                    # Cloud container
├── ⚙️ render.yaml                   # Render deployment config
├── 📦 requirements.txt              # Dependencies
├── 🌐 web_service.py                # FastAPI dashboard & API
├── 🔄 worker.py                     # Background automation worker
├── ♾️ eternal_gmail_automation.py   # Eternal automation engine
├── 🤖 python_oauth_automation.py    # Original automation script
├── 🚀 start_eternal_automation.bat  # Local eternal startup
├── 📋 env.production.template       # Cloud environment template
└── 📖 DEPLOYMENT_GUIDE.md           # Complete deployment guide
```

## 🌊 Workflow Process

Every 20 minutes, the automation:

1. ✅ **Confirms Gmail connection** is active
2. 📅 **Sets date filter** to "last 20 minutes"
3. ⏰ **Extracts time range** (e.g., 14:30 - 14:50)
4. 🔄 **Clicks "Scan & Auto Process"** button
5. ⏳ **Waits 20 minutes** after end time
6. 🔁 **Repeats forever** (ETERNAL loop)

## 🛡️ Error Handling

The automation is **bulletproof** and handles:
- ❌ OAuth failures → Auto-retry every 5 minutes
- ❌ UI changes → Fallback to calculated times
- ❌ Network issues → Continue with next cycle
- ❌ Browser crashes → Restart and continue
- ❌ Any other error → Log and continue

**The automation NEVER stops working!**

## 🔒 Security

- 🔐 OAuth tokens stored securely in Supabase
- 🛡️ Environment variables for sensitive data
- 🚫 No hardcoded passwords in code
- ✅ Headless browser in cloud (no GUI exposure)
- 🔄 Automatic token refresh

## 💰 Cloud Costs

**Render Pricing** (Monthly):
- Web Service: $7/month
- Worker Service: $7/month
- Redis: Free
- PostgreSQL: Free

**Total: ~$14/month** for eternal automation

## 📊 Monitoring

### Cloud Dashboard
- 🟢 Service health status
- 📈 Processing cycle count
- ⏰ Next processing time
- 📝 Recent activity logs
- ❌ Error tracking

### API Endpoints
- `GET /health` - Service health check
- `GET /status` - Automation status
- `GET /cycles` - Processing history
- `POST /start` - Start automation
- `POST /stop` - Stop automation

## 🛠️ Troubleshooting

### Common Issues

**OAuth fails**: Check Google credentials and redirect URI
**Password fails**: Use App Password instead of regular password
**Browser issues**: Chrome/ChromeDriver version mismatch
**Cloud issues**: Check Render logs and environment variables

### Debug Mode
```bash
# Local debug
python eternal_gmail_automation.py --password YOUR_PASSWORD --debug

# Cloud debug
Set LOG_LEVEL=DEBUG in Render environment variables
```

## 📈 Scaling

### Single Account
- ✅ One automation per Gmail account
- ✅ Processes every 20 minutes eternally
- ✅ Zero maintenance required

### Multiple Accounts
- 🚀 Deploy multiple instances
- 🔧 Configure different environment variables
- 📊 Monitor all from separate dashboards

## 🎯 Use Cases

- 📧 **Email Processing**: Automated Gmail workflow processing
- 🔄 **Regular Tasks**: Any task that needs 20-minute intervals
- 🤖 **Business Automation**: Unattended business process automation
- 📊 **Data Collection**: Regular data gathering from Gmail
- 🚀 **Background Services**: Set-and-forget automation

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Make your changes
4. Test locally first
5. Submit a pull request

## 📄 License

This project is provided as-is for automation purposes.

## 🆘 Support

- 📖 **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Complete cloud setup
- 🌐 **[Dashboard](https://your-app.onrender.com/)** - Monitor your automation
- 📊 **[API Docs](https://your-app.onrender.com/docs)** - API reference
- 💬 **Issues** - Create GitHub issue for bugs

---

## 🎉 Ready to Deploy?

**[📖 Follow the Deployment Guide](DEPLOYMENT_GUIDE.md)** to get your eternal Gmail automation running in the cloud in under 10 minutes!

Your automation will run **forever** without any manual intervention. Set it up once, and let it work eternally! 🚀 