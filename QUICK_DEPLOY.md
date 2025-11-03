# 🚀 Quick Railway Deployment Checklist

## Files Created/Modified

✅ **requirements.txt** - Python dependencies (includes gunicorn, whitenoise)
✅ **Procfile** - Tells Railway how to start your app
✅ **railway.json** - Build configuration
✅ **settings.py** - Updated for production (env vars, database URL, static files)
✅ **.gitignore** - Prevents committing secrets/files

---

## Before You Deploy

### 1. Test Locally (Optional but Recommended)

```bash
# Install new dependencies
pip install -r requirements.txt

# Collect static files (test if it works)
python manage.py collectstatic --noinput

# Test with production settings
DEBUG=False python manage.py runserver
```

---

### 2. Push to GitHub

```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

---

## Railway Setup (15 minutes)

### Step 1: Sign Up
1. Go to https://railway.app
2. Click "Start a New Project"
3. Sign in with GitHub

### Step 2: Create Project
1. "New Project" → "Deploy from GitHub repo"
2. Select your `nestquest` repository
3. Railway auto-detects Django ✅

### Step 3: Add Database
1. In project, click "+ New"
2. "Database" → "Add PostgreSQL"
3. Database created automatically ✅

### Step 4: Set Environment Variables
1. Click on your Django service (the web one)
2. Go to "Variables" tab
3. Add these:

```
SECRET_KEY=<generate with command below>
DEBUG=False
ALLOWED_HOSTS=*.railway.app,localhost
```

**Generate SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 5: Deploy!
1. Railway automatically deploys when you connect repo
2. Watch the build logs (wait 2-3 minutes)
3. Check for errors

### Step 6: Run Migrations
1. Click on your service
2. Go to "Variables" tab
3. Click "Add Variable" → "Raw"
4. Or use Railway CLI:
   ```bash
   railway run python manage.py migrate
   ```

### Step 7: Get Your URL
1. Click on service → "Settings"
2. Under "Domains" → Your public URL!
3. Example: `https://nestquest-production.up.railway.app`

---

## What Railway Does Automatically

✅ Detects Django from `requirements.txt`  
✅ Installs all dependencies  
✅ Runs `collectstatic` (from `railway.json`)  
✅ Starts Gunicorn server  
✅ Provides `DATABASE_URL` automatically  
✅ Creates HTTPS URL  
✅ Auto-redeploys on git push  

---

## After Deployment

### Check Your Site
Visit your Railway URL - should see your property listings!

### Admin Panel
- URL: `https://your-app.railway.app/admin/`
- Create superuser: `railway run python manage.py createsuperuser`

### Run Your Scraping Scripts

```bash
# On Railway (via CLI or web terminal)
railway run python manage.py scrape_property24_images \
  --start-url "https://www.property24.co.ke/houses-to-rent-in-kileleshwa-s14529" \
  --start-page 1 --max-pages 3 --headless

railway run python manage.py update_property_details --listing-page 1 --headless
```

---

## Cost

- **First Month:** FREE ($5 credit)
- **After:** $5/month (app) + $5/month (database) = **$10/month**
- **Free tier ends:** When you use $5 credit (~1 month of light usage)

---

## Troubleshooting

**Build fails?**
- Check logs in Railway dashboard
- Common: Missing package in `requirements.txt`

**App crashes?**
- Check deployment logs
- Common: Missing environment variable

**Database error?**
- Verify `DATABASE_URL` exists (Railway sets automatically)
- Run migrations: `railway run python manage.py migrate`

---

## Next Steps

1. ✅ Deploy to Railway (you're here!)
2. 🔄 Set up automatic scraping (Railway Cron)
3. 📊 Add monitoring (Railway Metrics)
4. 🌐 Add custom domain (optional)

---

## Key DevOps Learnings

1. **Infrastructure as Code:** `railway.json` defines build
2. **12-Factor App:** Uses environment variables
3. **CI/CD:** Git push → Auto deploy
4. **Platform as a Service:** Railway handles servers

---

Need help? Check `DEPLOYMENT.md` for detailed explanations!



