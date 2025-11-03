# Railway Deployment Guide

## 🎓 DevOps Concepts Explained

### 1. **Environment Variables**
**What:** Configuration stored outside your code  
**Why:** Security (no passwords in code), flexibility (same code works in dev/prod)  
**How:** Railway sets `DATABASE_URL`, `SECRET_KEY`, etc. automatically

### 2. **WSGI Server (Gunicorn)**
**What:** Production web server that runs Django  
**Why:** Django's dev server (`runserver`) is slow and unsafe for production  
**How:** Gunicorn handles multiple requests efficiently

### 3. **Static Files (WhiteNoise)**
**What:** CSS, JS, images that don't change  
**Why:** Django doesn't serve static files efficiently in production  
**How:** `collectstatic` gathers files, WhiteNoise serves them fast

### 4. **Database Connection Pooling**
**What:** Reusing database connections instead of creating new ones  
**Why:** Faster, less resource-intensive  
**How:** `conn_max_age=600` in settings

### 5. **Build Process**
**What:** Steps to prepare your app for deployment  
**How:** Railway runs `collectstatic` automatically (see `railway.json`)

---

## 📋 Pre-Deployment Checklist

- [x] `requirements.txt` created
- [x] `Procfile` created (tells Railway how to start app)
- [x] `railway.json` created (build configuration)
- [x] Settings.py updated for production
- [x] Environment variables configured
- [x] Static files configured (WhiteNoise)

---

## 🚀 Step-by-Step Deployment

### Step 1: Push Code to GitHub

```bash
# Initialize git if not done
git init
git add .
git commit -m "Prepare for Railway deployment"

# Create GitHub repo, then:
git remote add origin https://github.com/YOUR_USERNAME/nestquest.git
git push -u origin main
```

**DevOps Concept:** Version Control
- Your code lives in Git
- Railway watches GitHub for changes
- Auto-deploys on push (CI/CD)

---

### Step 2: Sign Up for Railway

1. Go to https://railway.app
2. Sign up with GitHub (free tier includes $5 credit)
3. Dashboard appears

**Cost:** Free $5 credit → ~1 month free → $5/month after

---

### Step 3: Create New Project

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose your `nestquest` repository
4. Railway detects Django automatically

**DevOps Concept:** Platform Detection
- Railway reads your files (`requirements.txt`, `Procfile`)
- Automatically knows it's a Python/Django app
- Sets up build environment

---

### Step 4: Add PostgreSQL Database

1. In your project, click "+ New"
2. Select "Database" → "Add PostgreSQL"
3. Railway creates database automatically

**DevOps Concept:** Database as a Service
- Railway manages PostgreSQL for you
- Creates `DATABASE_URL` automatically
- No manual database setup needed

---

### Step 5: Configure Environment Variables

Railway automatically sets:
- `DATABASE_URL` (from PostgreSQL service)
- `PORT` (port to listen on)
- `RAILWAY_ENVIRONMENT` (production)

**You need to set manually:**
1. Go to your service → "Variables"
2. Add:
   ```
   SECRET_KEY=your-random-secret-key-here
   DEBUG=False
   ALLOWED_HOSTS=your-app.railway.app,*.railway.app
   ```

**Generate SECRET_KEY:**
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**DevOps Concept:** Secrets Management
- Sensitive data stored as environment variables
- Never commit secrets to Git
- Different values for dev vs prod

---

### Step 6: Deploy

Railway automatically:
1. Clones your repo
2. Installs dependencies (`pip install -r requirements.txt`)
3. Runs build command (`collectstatic`)
4. Starts your app (`gunicorn`)
5. Exposes it to the internet

**Watch the build logs:**
- Click on your service
- See "Deployments" tab
- View logs in real-time

---

### Step 7: Run Migrations

After first deployment:

1. Go to your service → "Variables"
2. Click "Add Variable" → "Add Service Variable"
3. In Railway CLI or web console:
   ```bash
   railway run python manage.py migrate
   ```

**Or use Railway's web terminal:**
1. Service → "Deployments" → Click deployment
2. "View Logs" → Terminal tab
3. Run: `python manage.py migrate`

**DevOps Concept:** Database Migrations
- Schema changes need to run on production DB
- Migrations are versioned (Git tracks them)
- Run `migrate` after each deployment if schema changed

---

### Step 8: Create Superuser (Optional)

```bash
railway run python manage.py createsuperuser
```

**DevOps Concept:** Admin Access
- Admin panel at `https://your-app.railway.app/admin/`
- Create superuser to manage data via Django admin

---

### Step 9: Get Your Public URL

1. Railway generates URL automatically: `https://your-app.up.railway.app`
2. Click on your service → "Settings"
3. Under "Domains", you'll see your public URL
4. Click to open in browser!

**DevOps Concept:** Load Balancing & SSL
- Railway handles HTTPS automatically
- Your app gets a free SSL certificate
- URLs are globally accessible

---

## 🔧 Post-Deployment

### Custom Domain (Optional)

1. Service → Settings → Domains
2. Add your domain (e.g., `nestquest.com`)
3. Update DNS records (Railway shows instructions)

---

### Monitoring

Railway dashboard shows:
- **Metrics:** CPU, Memory usage
- **Logs:** Real-time application logs
- **Deployments:** History of all deploys

**DevOps Concept:** Observability
- Monitor app health
- Debug issues via logs
- Track resource usage

---

## 🔄 Continuous Deployment (CI/CD)

**How it works:**
1. You push code to GitHub
2. Railway detects change
3. Automatically rebuilds and redeploys
4. Zero-downtime deployment (if configured)

**To trigger redeploy:**
```bash
git add .
git commit -m "Update feature"
git push
```
Railway deploys automatically!

---

## 🐛 Troubleshooting

### Build Fails
- Check logs for error messages
- Common: Missing dependency in `requirements.txt`
- Fix: Add missing package, push again

### App Crashes
- Check deployment logs
- Common: Missing environment variable
- Fix: Add variable in Railway dashboard

### Database Connection Error
- Verify `DATABASE_URL` is set
- Check PostgreSQL service is running
- Run migrations if needed

### Static Files Not Loading
- Ensure `collectstatic` ran (check build logs)
- Verify `STATIC_ROOT` exists
- Check WhiteNoise middleware is enabled

---

## 💰 Cost Breakdown

**Railway Hobby Plan:**
- **Free:** $5 credit (lasts ~1 month)
- **After:** $5/month for app + $5/month for database = **$10/month total**
- **Limits:** 512MB RAM, 1GB disk per service

**Optimize:**
- Use free tier initially
- Upgrade only when needed
- Monitor usage in dashboard

---

## 📚 Next Steps

1. **Set up cron jobs** for scraping (Railway Cron service)
2. **Add error tracking** (Sentry)
3. **Set up monitoring** (Railway Metrics)
4. **Configure backups** (Railway has automatic backups)

---

## 🎯 Key Takeaways

1. **Infrastructure as Code:** `railway.json` defines how to build
2. **12-Factor App:** Uses environment variables, stateless processes
3. **Platform as a Service:** Railway handles servers, you focus on code
4. **DevOps Automation:** Git push → Auto deploy → Live in minutes

---

## 🆘 Need Help?

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Check deployment logs first!



