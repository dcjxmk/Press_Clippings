# Deployment Instructions

## Server Setup

1. Install required system packages:
```bash
sudo apt update
sudo apt install python3-venv nginx supervisor
```

2. Create and prepare project directory:
```bash
sudo mkdir -p /var/www/press_clippings
sudo chown www-data:www-data /var/www/press_clippings
```

3. Copy your project files to `/var/www/press_clippings`

4. Set up Python environment:
```bash
cd /var/www/press_clippings
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. Create log directory:
```bash
mkdir logs
sudo chown -R www-data:www-data logs
```

6. Configure Nginx:
```bash
# Edit the server_name in the Nginx config to match your domain
sudo cp nginx/press_clippings.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/press_clippings.conf /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

7. Make the management script executable:
```bash
chmod +x manage.py
```

## Using the Management Script

The `manage.py` script provides an easy way to manage the Press Clippings service:

- Start the service: `./manage.py start`
- Stop the service: `./manage.py stop`
- Restart the service: `./manage.py restart`
- Check service status: `./manage.py status`

## Monitoring

- Check Gunicorn status: `./manage.py status`
- View application logs: `tail -f logs/error.log`
- View access logs: `tail -f logs/access.log`
- Nginx error logs: `sudo tail -f /var/log/nginx/error.log`

## Performance Monitoring

To monitor application performance:

1. Install monitoring tools:
```bash
pip install psutil newrelic
```

2. Monitor system resources:
```bash
top -p $(pgrep -d',' gunicorn)
```

3. Check memory usage:
```bash
ps aux | grep gunicorn
```

## SSL Setup (Optional)

To enable HTTPS:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

## Maintenance

- Restart application: `./manage.py restart`
- Reload Nginx: `sudo systemctl reload nginx`
- Update application:
  ```bash
  cd /var/www/press_clippings
  source venv/bin/activate
  git pull  # if using git
  pip install -r requirements.txt
  ./manage.py restart
  ```

## Troubleshooting

1. If the service fails to start:
   - Check logs: `tail -f logs/error.log`
   - Verify permissions: `sudo chown -R www-data:www-data /var/www/press_clippings`
   - Check Python environment: `source venv/bin/activate`

2. If Nginx returns 502 Bad Gateway:
   - Check if Gunicorn is running: `./manage.py status`
   - Verify Nginx configuration: `sudo nginx -t`
   - Check Nginx logs: `sudo tail -f /var/log/nginx/error.log`

3. For performance issues:
   - Monitor CPU/Memory: `top -p $(pgrep -d',' gunicorn)`
   - Check Gunicorn worker status in logs
   - Adjust worker count in gunicorn_config.py if needed