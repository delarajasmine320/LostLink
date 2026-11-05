LOSTLINK STARTER - WINDOWS / XAMPP / VS CODE

A. DATABASE
1. Start Apache and MySQL in XAMPP.
2. Open http://localhost/phpmyadmin
3. Select Import, choose schema.sql from this project, then click Import.
   You can also open schema.sql and execute it in phpMyAdmin's SQL tab.

B. PYTHON
Open this folder in VS Code. Open Terminal > New Terminal, then run:
  python -m venv venv
  venv\Scripts\activate
  pip install -r requirements.txt

C. DATABASE SETTINGS
Open config.py. Defaults assume XAMPP MySQL:
  host=127.0.0.1, user=root, password blank, database=lostlink
If your MySQL root account has a password, set MYSQL_PASSWORD in config.py.

D. RUN
  python app.py
Open http://127.0.0.1:5000

E. MAKE YOUR ACCOUNT AN ADMIN
1. Register through the website.
2. In phpMyAdmin select database lostlink and open the SQL tab.
3. Run this query, replacing the email:
  UPDATE users SET role='admin' WHERE email='your-email@example.com';

FEATURES IN THIS STARTER
- Registration and login with password hashing
- Student / staff / admin roles (staff/admin can review claims)
- Lost and found item reports with optional image upload
- Browse and search published item reports
- Claim requests and staff approval/rejection
- Basic user notifications and dashboard

IMPORTANT
- Change SECRET_KEY in config.py to a long random value.
- This is a local development starter, not production-ready.
- Do not expose Flask debug mode to the public internet.
- Before school LAN deployment, configure firewall/network access and use a proper production WSGI server.
- Add CSRF protection, rate limiting, audit logging, backups, and stronger admin provisioning before real deployment.
- Public item descriptions should not reveal secret ownership details.
