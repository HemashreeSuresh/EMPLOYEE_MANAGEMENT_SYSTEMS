# Employee Management System (Flask + RBAC)

## Tech Stack
- Backend: Flask
- Frontend: HTML, CSS, Bootstrap 5, Chart.js
- Database: SQLite locally, hosted PostgreSQL on Vercel
- ORM: SQLAlchemy
- Auth: Session based
- Password Hashing: werkzeug.security

## Roles
- Admin
- HR
- Manager
- Employee

## Local Development
1. Open terminal in the project root `employee-management`.
2. Create a virtual environment:
   - `python -m venv venv`
3. Activate environment:
   - Windows PowerShell: `./venv/Scripts/activate`
4. Install dependencies:
   - `pip install -r requirements.txt`
5. Run the backend:
   - `python backend/app.py`
6. Open browser:
   - `http://127.0.0.1:5000`

## Deploying on Vercel
1. Connect the repository to Vercel.
2. Use the default build settings from `vercel.json`.
3. Add environment variables in Vercel Project Settings:
   - `SECRET_KEY` (required)
   - `DATABASE_URL` (optional for hosted DB)
4. Push to GitHub and let Vercel build the project.

## Sample Logins
- Admin: `admin / admin123`
- HR: `hr / hr123`
- Manager: `manager / manager123`
- Employee: `employee / employee123`

## Notes
- Database tables are auto-created on first run.
- The app uses `DATABASE_URL` when provided, otherwise it falls back to local SQLite.
- For Vercel, set `DATABASE_URL` and `SECRET_KEY` in Project Settings -> Environment Variables.
- Old schema is auto-rebuilt for compatibility in this demo setup.
- Uploaded files are stored in `static/uploads/`.

## REST API (JSON + JWT)
- Base path: `/api`
- Login: `POST /api/auth/login` with JSON body `{"username":"...","password":"..."}`
- Use token in header: `Authorization: Bearer <token>`
- Health: `GET /api/health`
- Employees:
  - `GET /api/employees`
  - `GET /api/employees/<id>`
  - `POST /api/employees`
  - `PUT /api/employees/<id>`
  - `DELETE /api/employees/<id>`
- Tasks:
  - `GET /api/tasks`
  - `POST /api/tasks`
  - `PUT /api/tasks/<id>`
  - `DELETE /api/tasks/<id>`

The UI remains session-based, and task update forms now also support Fetch API when `localStorage.ems_api_token` is available.
