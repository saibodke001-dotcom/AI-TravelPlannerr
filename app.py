import os
import sqlite3
import certifi

if not os.environ.get("VERCEL"):
    import urllib3
    import requests
    # Bypass SSL verification for local development behind corporate proxies
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    old_request = requests.Session.request
    requests.Session.request = lambda self, method, url, **kwargs: old_request(self, method, url, **{**kwargs, 'verify': False})

os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = certifi.where()
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, g
from dotenv import load_dotenv
from google import genai
import markdown

# For PDF Generation
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from io import BytesIO

# Load environment variables
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_default_key")

# Gemini Configuration
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

client = genai.Client(api_key=api_key)
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not configured")

DATABASE = 'database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                budget TEXT,
                travelers INTEGER,
                travel_type TEXT,
                interests TEXT,
                itinerary_markdown TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute("INSERT OR IGNORE INTO users (id, username, email, password_hash) VALUES (1, 'Guest', 'guest@example.com', '')")
        db.commit()

# Initialize database on startup for serverless environments
init_db()

@app.before_request
def auto_login():
    session['user_id'] = 1
    session['username'] = 'Guest'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM trips WHERE user_id = ? ORDER BY created_at DESC", (session['user_id'],))
    trips = cursor.fetchall()
    return render_template('dashboard.html', trips=trips)

@app.route('/planner', methods=['GET', 'POST'])
def planner():
    if request.method == 'POST':
        source = request.form['source']
        destination = request.form['destination']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        budget = request.form['budget']
        travelers = request.form['travelers']
        travel_type = request.form['travel_type']
        interests = request.form.getlist('interests') # Multiple
        
        interests_str = ", ".join(interests)

        prompt = f"""
        Act as a professional travel planner. Create a detailed, day-by-day itinerary for a trip.
        Source: {source}
        Destination: {destination}
        Dates: {start_date} to {end_date}
        Budget Level: {budget}
        Number of Travelers: {travelers}
        Travel Type: {travel_type}
        Interests: {interests_str}

        Please include:
        1. A brief overview of the trip.
        2. Day-wise itinerary with morning, afternoon, and evening activities.
        3. Recommended tourist attractions.
        4. Suggested hotels/accommodations (for the specified budget).
        5. Best local restaurants and food to try.
        6. Estimated daily expenses and total trip budget breakdown.
        7. Local transportation suggestions.
        8. A short packing checklist.
        9. Weather recommendations and best time to visit.
        10. Safety tips.

        Format the response in Markdown with clear headings and bullet points. Make it engaging.
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt
            )
            itinerary_markdown = response.text
            
            # Save to database
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                INSERT INTO trips (user_id, source, destination, start_date, end_date, budget, travelers, travel_type, interests, itinerary_markdown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], source, destination, start_date, end_date, budget, travelers, travel_type, interests_str, itinerary_markdown))
            db.commit()
            trip_id = cursor.lastrowid
            
            return redirect(url_for('trip_details', trip_id=trip_id))
            
        except Exception as e:
            flash(f"Error generating itinerary: {str(e)}", "danger")
            return render_template('planner.html')

    return render_template('planner.html')

@app.route('/trip/<int:trip_id>')
def trip_details(trip_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, session['user_id']))
    trip = cursor.fetchone()
    
    if not trip:
        flash("Trip not found.", "danger")
        return redirect(url_for('dashboard'))
        
    itinerary_html = markdown.markdown(trip['itinerary_markdown'])
    return render_template('trip_details.html', trip=trip, itinerary_html=itinerary_html)

@app.route('/download-pdf/<int:trip_id>')
def download_pdf(trip_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, session['user_id']))
    trip = cursor.fetchone()
    
    if not trip:
        flash("Trip not found.", "danger")
        return redirect(url_for('dashboard'))

    # Generate PDF using ReportLab
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']
    
    elements = []
    
    # Title
    title = Paragraph(f"Trip to {trip['destination']}", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Details
    details = f"<b>Source:</b> {trip['source']}<br/>" \
              f"<b>Dates:</b> {trip['start_date']} to {trip['end_date']}<br/>" \
              f"<b>Budget:</b> {trip['budget']}<br/>" \
              f"<b>Travelers:</b> {trip['travelers']}<br/>" \
              f"<b>Type:</b> {trip['travel_type']}<br/>"
    elements.append(Paragraph(details, normal_style))
    elements.append(Spacer(1, 20))
    
    # We can do a rudimentary markdown-to-reportlab conversion by removing ## and * 
    # and applying appropriate paragraph styles, but for simplicity, we'll strip minimal markdown.
    md_text = trip['itinerary_markdown']
    lines = md_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 6))
            continue
            
        if line.startswith('###'):
            elements.append(Paragraph(line.replace('###', '').strip(), styles['Heading3']))
        elif line.startswith('##'):
            elements.append(Paragraph(line.replace('##', '').strip(), styles['Heading2']))
        elif line.startswith('#'):
            elements.append(Paragraph(line.replace('#', '').strip(), styles['Heading1']))
        elif line.startswith('* ') or line.startswith('- '):
            elements.append(Paragraph(line, normal_style)) # Bullet style mapping can be complex, just use normal
        else:
            # Escape special characters to prevent XML parse errors
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # Ensure even count for bold
            parts = line.split('**')
            formatted_line = ""
            if len(parts) % 2 == 0:
                # If unmatched pair, just ignore bolding to prevent crash
                formatted_line = line.replace('**', '')
            else:
                for i, part in enumerate(parts):
                    if i % 2 != 0:
                        formatted_line += f"<b>{part}</b>"
                    else:
                        formatted_line += part
                        
            # Ensure even count for italic (using single *)
            parts = formatted_line.split('*')
            final_line = ""
            if len(parts) % 2 == 0:
                final_line = formatted_line.replace('*', '')
            else:
                for i, part in enumerate(parts):
                    if i % 2 != 0:
                        final_line += f"<i>{part}</i>"
                    else:
                        final_line += part

            try:
                elements.append(Paragraph(final_line, normal_style))
            except Exception:
                # Fallback to plain text if parsing still fails
                import re
                clean_text = re.sub(r'<[^>]+>', '', final_line)
                elements.append(Paragraph(clean_text, normal_style))
            
    doc.build(elements)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    response = Response(pdf_bytes, content_type='application/pdf')
    response.headers['Content-Disposition'] = f'attachment; filename="itinerary_{trip["destination"].replace(" ", "_")}.pdf"'
    return response



@app.route('/explorer')
def explorer():
    # Pre-defined trending destinations
    destinations = [
        {"name": "Bali, Indonesia", "image": "bali.jpg", "desc": "Tropical paradise with beautiful beaches and rich culture."},
        {"name": "Paris, France", "image": "paris.jpg", "desc": "The city of light, famous for art, fashion, and the Eiffel Tower."},
        {"name": "Kyoto, Japan", "image": "kyoto.jpg", "desc": "Historic temples, stunning gardens, and traditional teahouses."},
        {"name": "Rome, Italy", "image": "rome.jpg", "desc": "Ancient history, incredible architecture, and world-class cuisine."},
        {"name": "New York, USA", "image": "newyork.jpg", "desc": "The city that never sleeps, with endless entertainment and iconic sights."}
    ]
    return render_template('explorer.html', destinations=destinations)

@app.route('/budget', methods=['GET', 'POST'])
def budget():
    estimation = None
    if request.method == 'POST':
        # Simple calculator
        days = int(request.form.get('days', 0))
        travelers = int(request.form.get('travelers', 0))
        style = request.form.get('style', 'medium')
        
        rates = {'low': 50, 'medium': 150, 'luxury': 400}
        daily_rate = rates.get(style, 150)
        
        total = days * travelers * daily_rate
        estimation = {
            'days': days,
            'travelers': travelers,
            'style': style.capitalize(),
            'total': total,
            'daily_per_person': daily_rate
        }
        
    return render_template('budget.html', estimation=estimation)

@app.route('/weather')
def weather():
    # A placeholder for weather information
    return render_template('weather.html')

@app.route('/profile')
def profile():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) FROM trips WHERE user_id = ?", (session['user_id'],))
    trip_count = cursor.fetchone()[0]
    
    return render_template('profile.html', user=user, trip_count=trip_count)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
