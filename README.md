# AI Travel Planner

A premium, modern AI-powered travel planner built using HTML, CSS, Python (Flask), SQLite, and the Google Gemini API.

## Features
- **AI Trip Planner**: Generate customized day-by-day itineraries using Gemini AI.
- **AI Chat Assistant**: Ask travel-related questions to the Gemini-powered chat assistant.
- **Budget Calculator**: Estimate travel expenses.
- **Weather Information**: View weather tips and recommendations.
- **Destination Explorer**: Discover trending places.
- **PDF Export**: Download itineraries as beautifully formatted PDFs.
- **User Authentication**: Secure login and registration.
- **Saved Trips**: Save and view your planned itineraries.
- **Dark/Light Mode**: Smooth, CSS-based theme switching.
- **Premium UI**: Glassmorphism, animations, responsive design.

## Setup Instructions

1. **Clone or Download the Repository**
2. **Create a Virtual Environment (Optional but recommended)**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. **Install Requirements**
   ```bash
   pip install -r requirements.txt
   ```
4. **Set up Environment Variables**
   - Rename `.env.example` to `.env`.
   - Add your Google Gemini API key to `.env`:
     ```env
     GEMINI_API_KEY=your_gemini_api_key
     FLASK_SECRET_KEY=a_random_secret_string
     ```
5. **Run the Application**
   ```bash
   python app.py
   ```
   The database (`database.db`) will be created automatically.
6. **Open in Browser**
   Navigate to `http://127.0.0.1:5000` to start exploring!
