# 🚀 Render Deployment Guide for Gmail OAuth Automation

This guide will help you deploy your **Eternal Gmail OAuth Automation** to Render cloud platform.

## 📋 Prerequisites

1. **Render Account**: Sign up at [render.com](https://render.com)
2. **GitHub Repository**: Your code needs to be in a GitHub repository
3. **Google OAuth Credentials**: Google Cloud Console project with OAuth setup
4. **Supabase Account**: For token storage (optional but recommended)
5. **Gmail Account**: The account you want to automate

## 🏗️ Architecture Overview

Your deployment will include:
- **Web Service**: FastAPI dashboard and API (`web_service.py`)
- **Background Worker**: Eternal automation engine (`worker.py`)
- **Redis**: Task queue and caching
- **PostgreSQL**: Optional database for extended storage

## 📁 File Structure

Your repository should have:
```
oauth-automation/
├── Dockerfile                    # Container configuration
├── render.yaml                   # Render services configuration
├── requirements.txt              # Python dependencies
├── web_service.py                # FastAPI web service
├── worker.py                     # Background automation worker
├── eternal_gmail_automation.py   # Core automation logic
├── python_oauth_automation.py    # Original automation script
├── env.production.template       # Environment variables template
└── DEPLOYMENT_GUIDE.md           # This guide
```

## 🔧 Step 1: Environment Variables Setup

### Required Environment Variables

Set these in your Render dashboard for BOTH the web service and worker:

#### 🔐 Gmail OAuth Configuration
```bash
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=https://YOUR_APP_NAME.onrender.com/oauth-callback.html
```

#### 📧 Gmail Account Credentials
```bash
GMAIL_EMAIL=midasportal1234@gmail.com
GMAIL_PASSWORD=your_gmail_password_here
```

#### 🗄️ Supabase Configuration
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
```

#### ⚙️ Application Configuration
```bash
ENVIRONMENT=production
PORT=8080
CHROME_BIN=/usr/bin/google-chrome-stable
CHROMEDRIVER_DIR=/usr/local/bin
DISPLAY=:99
```

## 🚀 Step 2: Deploy to Render

### Option A: Using render.yaml (Recommended)

1. **Push to GitHub**: Ensure all files are in your GitHub repository

2. **Create New Service**: 
   - Go to Render Dashboard
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Select the repository with your code

3. **Configure Blueprint**:
   - Render will automatically detect `render.yaml`
   - Review the services that will be created:
     - `gmail-oauth-automation` (Web Service)
     - `gmail-automation-worker` (Worker Service)
     - `gmail-automation-redis` (Redis)
     - `gmail-automation-postgres` (PostgreSQL)

4. **Set Environment Variables**:
   - For each service, add the environment variables listed above
   - **Important**: Set `sync: false` variables manually in Render dashboard

5. **Deploy**: Click "Create Services"

### Option B: Manual Service Creation

If you prefer to create services manually:

#### 1. Create Web Service
- **Name**: `gmail-oauth-automation`
- **Runtime**: Docker
- **Repository**: Your GitHub repo
- **Dockerfile Path**: `./Dockerfile`
- **Start Command**: `python3 web_service.py`
- **Plan**: Starter ($7/month)

#### 2. Create Worker Service
- **Name**: `gmail-automation-worker`
- **Runtime**: Docker
- **Repository**: Your GitHub repo
- **Dockerfile Path**: `./Dockerfile`
- **Start Command**: `python3 worker.py`
- **Plan**: Starter ($7/month)

#### 3. Create Redis Service
- **Name**: `gmail-automation-redis`
- **Plan**: Starter (Free)

#### 4. Connect Services
- Add `REDIS_URL` environment variable to both web and worker services
- Set it to the Redis connection string from the Redis service

## 📊 Step 3: Verify Deployment

### Health Checks

1. **Web Service Health**: 
   ```
   https://YOUR_APP_NAME.onrender.com/health
   ```
   Should return:
   ```json
   {
     "status": "healthy",
     "timestamp": "2024-01-15T10:30:00Z",
     "service": "gmail-oauth-automation",
     "version": "1.0.0"
   }
   ```

2. **Dashboard Access**:
   ```
   https://YOUR_APP_NAME.onrender.com/
   ```

3. **API Documentation**:
   ```
   https://YOUR_APP_NAME.onrender.com/docs
   ```

### Monitor Logs

1. **Web Service Logs**: Check Render dashboard → Web Service → Logs
2. **Worker Logs**: Check Render dashboard → Worker Service → Logs
3. **Redis Logs**: Check Render dashboard → Redis Service → Logs

## 🔄 Step 4: Start Automation

### Option A: Auto-Start (Recommended)

If you set the `GMAIL_PASSWORD` environment variable, the automation will start automatically when deployed.

### Option B: Manual Start

1. Go to your dashboard: `https://YOUR_APP_NAME.onrender.com/`
2. Click "Start Automation"
3. Enter your Gmail password when prompted

## 📈 Step 5: Monitor Operations

### Dashboard Features

- ✅ **Real-time Status**: Running/stopped status
- 📊 **Cycle Count**: Number of completed cycles
- ⏰ **Next Cycle Time**: When the next processing will occur
- 📝 **Recent Activity**: Last 10 automation cycles
- ❌ **Error Monitoring**: Recent errors and issues

### API Endpoints

- `GET /status` - Current automation status
- `GET /cycles` - Recent cycle history
- `GET /logs` - Application logs
- `POST /start` - Start automation
- `POST /stop` - Stop automation

### Expected Behavior

Once running, you should see:
```
🔄 Starting automation cycle #1
✅ OAuth completed successfully
✅ Gmail connection confirmed
📅 Setting date filter to last 20 minutes...
⏰ Time range processed: 14:30 - 14:50
✅ Clicked Scan & Auto Process button
⏰ Next cycle scheduled for: 2025-01-15 15:10:00
⏳ Waiting 20 minutes until next cycle...
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Chrome/ChromeDriver Issues
**Error**: `Chrome binary not found`
**Solution**: 
- Ensure Dockerfile installs Chrome correctly
- Check `CHROME_BIN` environment variable is set to `/usr/bin/google-chrome-stable`

#### 2. OAuth Failures
**Error**: `OAuth authentication failed`
**Solutions**:
- Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct
- Ensure `GOOGLE_REDIRECT_URI` matches your Render domain
- Check Google Cloud Console OAuth configuration

#### 3. Password Authentication Issues
**Error**: `Password input failed`
**Solutions**:
- Verify `GMAIL_PASSWORD` is correct
- Enable "Less secure app access" in Gmail (if using basic auth)
- Use App Password instead of regular password

#### 4. Redis Connection Issues
**Error**: `Failed to connect to Redis`
**Solutions**:
- Ensure Redis service is running
- Check `REDIS_URL` environment variable
- Verify services are in the same region

### Debug Mode

To enable debug mode:
1. Set environment variable: `LOG_LEVEL=DEBUG`
2. Check detailed logs in Render dashboard
3. Use `/logs` endpoint for application logs

### Service Restart

If services become unresponsive:
1. Go to Render Dashboard
2. Find the problematic service
3. Click "Manual Deploy" to restart

## 🔒 Security Notes

### Environment Variables
- ❌ Never commit passwords or API keys to Git
- ✅ Always use Render's environment variable system
- ✅ Set sensitive variables with `sync: false` in render.yaml

### OAuth Security
- ✅ Use HTTPS redirect URIs only
- ✅ Regularly rotate client secrets
- ✅ Monitor OAuth usage in Google Cloud Console

### Browser Security
- ✅ Always run in headless mode in production
- ✅ Use containers to isolate browser processes
- ✅ Regularly update Chrome and ChromeDriver

## 💰 Cost Estimation

### Render Pricing (Monthly)
- **Web Service**: $7/month (Starter plan)
- **Worker Service**: $7/month (Starter plan)
- **Redis**: Free (Starter plan)
- **PostgreSQL**: Free (Starter plan, if used)

**Total**: ~$14/month for eternal Gmail automation

### Cost Optimization
- Both services can run on Starter plans
- Redis and PostgreSQL have free tiers
- Consider pausing services during maintenance

## 📞 Support

### Getting Help
1. **Render Support**: [render.com/support](https://render.com/support)
2. **Documentation**: Check logs and `/health` endpoint
3. **API Debug**: Use `/docs` for API testing

### Monitoring
- Set up Sentry for error tracking (optional)
- Use Render's built-in monitoring
- Monitor service health with `/health` endpoint

## 🎉 Success!

Once deployed, your Gmail automation will:
- ✅ Run **eternally** every 20 minutes
- ✅ **Auto-restart** on any errors
- ✅ **Never stop** unless manually stopped
- ✅ Process Gmail with **zero manual intervention**
- ✅ Provide **web dashboard** for monitoring
- ✅ Scale automatically with Render

Your automation is now **bulletproof** and running in the cloud! 🚀 