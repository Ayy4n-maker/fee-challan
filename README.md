# IESC Fee Management & Challan System

A Flask web application integrated with **Firebase Firestore** for managing student records, generating fee challans, tracking fee payments (Paid, Unpaid, Overdue), and ready for deployment on **Vercel**.

---

## 🌟 Features

- **Role-Based Portals**:
  - **Admin Dashboard**: Analytics on total students, total revenue received, paid/unpaid payment breakdown, and late fees collected.
  - **Staff Portal**: Full student management and challan generation tools.
- **Student Management**: Add, update, view, and remove student profiles.
- **Challan Generation**:
  - Individual or bulk challan generation.
  - Automatically calculates due dates (10 days from issue).
  - Print-ready printable A4 fee challan layout (Student & School copies).
- **Fee Payment Tracking**: Filter records by status (`ALL`, `PAID`, `UNPAID`, `OVERDUE`), mark payments as paid or reverse payments.
- **Cloud Database (Firebase Firestore)**: Real-time, cloud-hosted data storage compatible with serverless cloud hosting like Vercel.

---

## 📁 Project Structure

```text
Fee-challan-system/
├── app.py                   # Main Flask application & route handlers
├── firebase_config.py       # Firebase Admin SDK initialization helper
├── vercel.json              # Vercel serverless configuration
├── requirements.txt         # Dependencies (Flask, firebase-admin, gunicorn)
├── static/                  # Static assets (logos, CSS)
└── templates/               # Jinja2 HTML templates
    ├── index.html           # Staff home portal
    ├── admin.html           # Admin dashboard
    ├── admin_login.html     # Admin login screen
    ├── staff_login.html     # Staff login screen
    ├── role_selection.html  # Landing page
    ├── students.html        # Student list page
    ├── add_student.html     # Student creation form
    ├── update_student.html  # Student edit form
    ├── generate_challan_list.html # Select student for challan
    ├── challan_form.html    # Challan customized form
    ├── generate_challan.html# Printable A4 challan page
    ├── all_challans.html    # Bulk challan preview page
    └── fee_payments.html    # Payment ledger & tracking page
```

---

## 🚀 Local Setup Instructions

### 1. Prerequisites
- Python 3.8+ installed
- Firebase account with a Firestore Database enabled

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/Ayy4n-maker/Fee-challan-system.git
cd Fee-challan-system
pip install -r requirements.txt
```

### 3. Firebase Setup
1. Go to [Firebase Console](https://console.firebase.google.com/).
2. Create a project and enable **Firestore Database**.
3. Go to **Project Settings** → **Service Accounts** → Click **Generate new private key**.
4. Save the downloaded `.json` file into your project folder as `serviceAccountKey.json`.

### 4. Run the Application
```bash
python app.py
```
Open `http://127.0.0.1:5000` in your web browser.

---

## 🌐 Deploying to Vercel

1. Push your repository to GitHub (Make sure your `serviceAccountKey.json` is **not** committed — `.gitignore` handles this automatically).
2. Go to [Vercel](https://vercel.com/) and import your `Fee-challan-system` repository.
3. In Vercel **Environment Variables**, add:
   - `FIREBASE_CREDENTIALS_JSON`: Copy and paste the entire raw JSON text content of your `serviceAccountKey.json`.
   - `SECRET_KEY`: (Optional) Custom Flask secret key.
   - `ADMIN_USERNAME` & `ADMIN_PASSWORD`: (Optional) Credentials for admin login.
   - `STAFF_USERNAME` & `STAFF_PASSWORD`: (Optional) Credentials for staff login.
4. Click **Deploy**.

---

## 🔐 Credentials (Default Local Development)

- **Admin Login**: `admin` / `admin123`
- **Staff Login**: `staff` / `staff123`
