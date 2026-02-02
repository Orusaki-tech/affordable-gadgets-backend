# Multi-Application Deployment Guide

Complete guide for deploying all three applications of the Affordable Gadgets platform.

## Application Architecture

The platform consists of three separate applications:

1. **Django Backend** (`/` - root directory)
   - REST API server
   - Database management
   - Authentication
   - Payment processing

2. **E-commerce Frontend** (`frontend_inventory_and_orders/shwari-phones/`)
   - Next.js application
   - Customer-facing website
   - Product browsing, cart, checkout

3. **Admin Frontend** (`frontend_inventory_and_orders/inventory-management-frontend/`)
   - React Create React App
   - Admin dashboard
   - Inventory management
   - Order management

## Deployment Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Production Setup                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐    ┌──────────────┐   ┌───────────┐ │
│  │   Backend    │    │  E-commerce  │   │   Admin   │ │
│  │   (Django)   │◄────┤  (Next.js)   │   │  (React)  │ │
│  │              │    │              │   │           │ │
│  │ Railway/     │    │   Vercel     │   │  Vercel/  │ │
│  │ Heroku       │    │              │   │  Netlify  │ │
│  └──────────────┘    └──────────────┘   └───────────┘ │
│         │                    │                  │        │
│         └────────────────────┴──────────────────┘        │
│                    (API Calls)                           │
└─────────────────────────────────────────────────────────┘
```

## Deployment Order

**Important**: Deploy in this order to ensure dependencies are met:

1. **Backend First** (Django)
   - Deploy backend API
   - Get production API URL
   - Verify API is accessible

2. **Frontends Second** (Both can deploy in parallel)
   - Deploy e-commerce frontend
   - Deploy admin frontend
   - Both need backend URL for environment variables

## Phase 1: Backend Deployment

### 1.1 Prerequisites

- PostgreSQL database (Supabase Session Pooler recommended for Render/IPv4)
- Cloudinary account for media storage
- Railway or Heroku account

### 1.2 Setup Steps

1. **Create Railway/Heroku Project**
   - Create new project
   - Connect GitHub repository
   - Add PostgreSQL service

2. **Configure Environment Variables**

   Set these in Railway/Heroku dashboard:

   ```env
   # Django Settings
   DJANGO_ENV=production
   SECRET_KEY=<generate-strong-key>
   DEBUG=False
   ALLOWED_HOSTS=your-api-domain.railway.app,yourdomain.com
   
   # Database (Supabase Session Pooler recommended)
   DATABASE_URL=postgresql://postgres.<project>:<password>@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require
   # Optional: if DATABASE_URL is not set
   DB_NAME=<from-postgres-service>
   DB_USER=<from-postgres-service>
   DB_PASSWORD=<from-postgres-service>
   DB_HOST=<from-postgres-service>
   DB_PORT=5432
   
   # CORS - CRITICAL: Include both frontend domains
   CORS_ALLOWED_ORIGINS=https://your-ecommerce-domain.com,https://your-admin-domain.com,https://www.your-ecommerce-domain.com
   
   # Cloudinary
   CLOUDINARY_CLOUD_NAME=<your-cloud-name>
   CLOUDINARY_API_KEY=<your-api-key>
   CLOUDINARY_API_SECRET=<your-api-secret>
   
   # Pesapal (if using)
   PESAPAL_CONSUMER_KEY=<your-consumer-key>
   PESAPAL_CONSUMER_SECRET=<your-consumer-secret>
   PESAPAL_ENVIRONMENT=live
   PESAPAL_CALLBACK_URL=https://your-ecommerce-domain.com/payment/callback/
   PESAPAL_IPN_URL=https://your-api-domain.railway.app/api/inventory/pesapal/ipn/
   ```

3. **Deploy Backend**
   - Trigger deployment
   - Monitor build logs
   - Wait for successful deployment

4. **Post-Deployment Setup**
   ```bash
   # Run migrations
   python manage.py migrate
   
   # Collect static files
   python manage.py collectstatic --noinput
   ```

5. **Verify Backend**
   - Test API endpoint: `https://your-api-domain.railway.app/api/v1/public/products/`
   - Check CORS headers in response
   - Verify database connectivity

### 1.3 Get Backend URL

Note your backend URL - you'll need it for frontend deployments:
```
https://your-api-domain.railway.app
```

## Phase 2: E-commerce Frontend Deployment (shwari-phones)

### 2.1 Prerequisites

- Backend deployed and accessible
- Vercel account
- Backend API URL

### 2.2 Setup Steps

1. **Import to Vercel**
   - Go to [Vercel Dashboard](https://vercel.com/dashboard)
   - Click "Add New Project"
   - Import GitHub repository

2. **Configure Project Settings**
   - **Framework Preset**: Next.js
   - **Root Directory**: `frontend_inventory_and_orders/shwari-phones`
   - **Build Command**: `npm run build` (auto-detected)
   - **Output Directory**: `.next` (auto-detected)

3. **Set Environment Variables**
   ```
   NEXT_PUBLIC_API_BASE_URL=https://your-api-domain.railway.app
   NEXT_PUBLIC_BRAND_CODE=AFFORDABLE_GADGETS
   NEXT_PUBLIC_BRAND_NAME=Affordable Gadgets
   NODE_ENV=production
   ```

4. **Deploy**
   - Click "Deploy"
   - Monitor build logs
   - Note deployment URL

### 2.3 Verify Deployment

- [ ] Homepage loads
- [ ] Products display
- [ ] API calls succeed (check browser console)
- [ ] Cart functionality works
- [ ] Checkout flow works

## Phase 3: Admin Frontend Deployment (inventory-management-frontend)

### 3.1 Prerequisites

- Backend deployed and accessible
- Vercel or Netlify account
- Backend API URL

### 3.2 Setup Steps

1. **Import to Vercel/Netlify**
   - Go to platform dashboard
   - Import GitHub repository

2. **Configure Project Settings**

   **For Vercel:**
   - **Framework Preset**: Create React App
   - **Root Directory**: `frontend_inventory_and_orders/inventory-management-frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `build`

   **For Netlify:**
   - **Base directory**: `frontend_inventory_and_orders/inventory-management-frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `build`

3. **Set Environment Variables**
   ```
   REACT_APP_API_BASE_URL=https://your-api-domain.railway.app/api/inventory
   ```

4. **Deploy**
   - Trigger deployment
   - Monitor build logs
   - Note deployment URL

### 3.3 Verify Deployment

- [ ] Login page loads
- [ ] Can authenticate
- [ ] Dashboard loads
- [ ] API calls succeed
- [ ] Admin features work

## Phase 4: CORS Configuration

### 4.1 Update Backend CORS

After both frontends are deployed, update backend CORS:

1. **Get Frontend URLs**
   - E-commerce: `https://your-ecommerce-domain.com`
   - Admin: `https://your-admin-domain.com`

2. **Update Backend Environment Variable**
   ```
   CORS_ALLOWED_ORIGINS=https://your-ecommerce-domain.com,https://your-admin-domain.com,https://www.your-ecommerce-domain.com
   ```

3. **Redeploy Backend** (if needed)
   - Update environment variable
   - Trigger redeployment

### 4.2 Verify CORS

Test CORS from both frontends:
- Open browser console on e-commerce site
- Make API call - should succeed
- Open browser console on admin site
- Make API call - should succeed

## Phase 5: Custom Domains (Optional)

### 5.1 Backend Domain

1. Add custom domain in Railway/Heroku
2. Update DNS records
3. Update `ALLOWED_HOSTS` environment variable
4. Update `CORS_ALLOWED_ORIGINS` if needed

### 5.2 Frontend Domains

**E-commerce Frontend:**
1. Add custom domain in Vercel
2. Update DNS records
3. Update `NEXT_PUBLIC_API_BASE_URL` if backend domain changed

**Admin Frontend:**
1. Add custom domain in Vercel/Netlify
2. Update DNS records
3. Update `REACT_APP_API_BASE_URL` if backend domain changed

### 5.3 Update Backend CORS

After adding custom domains, update backend:
```
CORS_ALLOWED_ORIGINS=https://your-ecommerce-domain.com,https://admin.yourdomain.com,https://www.your-ecommerce-domain.com
```

## Environment Variables Summary

### Backend (Django)
```env
DJANGO_ENV=production
SECRET_KEY=<strong-secret-key>
DEBUG=False
ALLOWED_HOSTS=<api-domain>,<custom-domain>
DB_NAME=<postgres-db-name>
DB_USER=<postgres-user>
DB_PASSWORD=<postgres-password>
DB_HOST=<postgres-host>
DB_PORT=5432
CORS_ALLOWED_ORIGINS=<ecommerce-domain>,<admin-domain>
CLOUDINARY_CLOUD_NAME=<cloud-name>
CLOUDINARY_API_KEY=<api-key>
CLOUDINARY_API_SECRET=<api-secret>
PESAPAL_CONSUMER_KEY=<consumer-key>
PESAPAL_CONSUMER_SECRET=<consumer-secret>
PESAPAL_ENVIRONMENT=live
PESAPAL_CALLBACK_URL=<ecommerce-domain>/payment/callback/
PESAPAL_IPN_URL=<api-domain>/api/inventory/pesapal/ipn/
```

### E-commerce Frontend (Next.js)
```env
NEXT_PUBLIC_API_BASE_URL=<backend-api-url>
NEXT_PUBLIC_BRAND_CODE=AFFORDABLE_GADGETS
NEXT_PUBLIC_BRAND_NAME=Affordable Gadgets
NODE_ENV=production
```

### Admin Frontend (React CRA)
```env
REACT_APP_API_BASE_URL=<backend-api-url>/api/inventory
```

## Deployment Checklist

### Backend
- [ ] PostgreSQL database created
- [ ] All environment variables set
- [ ] Deployed successfully
- [ ] Migrations run
- [ ] Static files collected
- [ ] API accessible
- [ ] CORS configured

### E-commerce Frontend
- [ ] Repository connected to Vercel
- [ ] Root directory configured
- [ ] Environment variables set
- [ ] Deployed successfully
- [ ] Homepage loads
- [ ] API calls work
- [ ] Custom domain configured (optional)

### Admin Frontend
- [ ] Repository connected to platform
- [ ] Root directory configured
- [ ] Environment variables set
- [ ] Deployed successfully
- [ ] Login works
- [ ] API calls work
- [ ] Custom domain configured (optional)

### Post-Deployment
- [ ] All applications accessible
- [ ] CORS working for both frontends
- [ ] Authentication works
- [ ] Database operations work
- [ ] Media uploads work (Cloudinary)
- [ ] Payment processing works (if applicable)
- [ ] Monitoring set up

## Troubleshooting

### Backend Issues

**Database Connection Errors**
- Verify database credentials
- Check database service is running
- Verify network connectivity

**CORS Errors**
- Check `CORS_ALLOWED_ORIGINS` includes both frontend domains
- Verify no trailing slashes in CORS origins
- Check backend logs for CORS errors

**Static Files Not Loading**
- Run `python manage.py collectstatic --noinput`
- Check `STATIC_ROOT` configuration
- Verify static files service

### E-commerce Frontend Issues

**API Connection Errors**
- Verify `NEXT_PUBLIC_API_BASE_URL` is correct
- Check backend is accessible
- Verify CORS configuration

**Build Errors**
- Check build logs in Vercel
- Verify all environment variables are set
- Check for TypeScript errors

### Admin Frontend Issues

**API Connection Errors**
- Verify `REACT_APP_API_BASE_URL` includes `/api/inventory` path
- Check backend is accessible
- Verify CORS configuration

**Build Errors**
- Check build logs
- Verify environment variables are set
- Check for missing dependencies

**Routing Issues (404 on refresh)**
- Configure SPA routing (redirect to index.html)
- Check server configuration

## Security Checklist

### Backend
- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` from environment
- [ ] `ALLOWED_HOSTS` restricts to production domains
- [ ] CORS only allows frontend domains
- [ ] HTTPS enforced
- [ ] Secure cookies enabled
- [ ] Security headers present

### Frontends
- [ ] HTTPS enforced
- [ ] No sensitive data in client code
- [ ] Environment variables properly set
- [ ] API tokens stored securely

## Monitoring and Maintenance

### Error Tracking
- Set up Sentry for all three applications
- Configure alerts for critical errors

### Logging
- Monitor backend logs in Railway/Heroku
- Monitor frontend build logs
- Set up log aggregation if needed

### Database Backups
- Set up automated PostgreSQL backups
- Test restore procedures
- Document backup schedule

### Updates
1. Make changes in development
2. Test thoroughly
3. Commit and push to repository
4. Platforms auto-deploy
5. Run migrations if needed
6. Verify deployment

## Rollback Procedures

### Backend
- Revert to previous deployment in Railway/Heroku
- Or redeploy previous git commit/tag

### Frontends
- Revert to previous deployment in Vercel/Netlify
- Or redeploy previous git commit/tag

## Support and Documentation

- **Backend Deployment**: See [DEPLOYMENT.md](./DEPLOYMENT.md)
- **E-commerce Frontend**: See [frontend_inventory_and_orders/shwari-phones/README.md](./frontend_inventory_and_orders/shwari-phones/README.md)
- **Admin Frontend**: See [frontend_inventory_and_orders/inventory-management-frontend/DEPLOYMENT.md](./frontend_inventory_and_orders/inventory-management-frontend/DEPLOYMENT.md)
- **Production Checklist**: See [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md)

## Quick Reference

### Deployment URLs
- Backend: `https://your-api-domain.railway.app`
- E-commerce: `https://your-ecommerce-domain.com`
- Admin: `https://your-admin-domain.com`

### Key Environment Variables
- Backend: `CORS_ALLOWED_ORIGINS` (must include both frontends)
- E-commerce: `NEXT_PUBLIC_API_BASE_URL`
- Admin: `REACT_APP_API_BASE_URL`

### Deployment Order
1. Backend → Get API URL
2. E-commerce Frontend → Use API URL
3. Admin Frontend → Use API URL
4. Update Backend CORS → Include both frontend domains

