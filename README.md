# DASS Flask App

## Prerequisites
- Python 3.8+
- pip (Python package manager)
- Virtual environment (recommended)

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/ismiabbas/dass-flask-app.git
   cd dass-flask-app
   ```

2. Create and activate a virtual environment:
   ```bash
   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate

   # On Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

To start the Flask development server:
```bash
flask run
```
Or alternatively:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Additional Notes
- Ensure all dependencies are installed before running
- For production, use a production WSGI server like Gunicorn
- Set appropriate environment variables for sensitive configurations