# Visitor Feedback System

A comprehensive web application built with Flask that allows visitors to submit feedback, browse an archive of previous feedback, and provides administrators with powerful tools for feedback management and analysis.

![Feedback System Logo](https://via.placeholder.com/800x400?text=Visitor+Feedback+System)

## Features

### For Visitors
- **Submit Feedback** - Simple and intuitive form for submitting feedback
- **Browse Archive** - Public archive of submitted feedback with filtering capabilities
- **Responsive Design** - Fully responsive interface that works on all devices

### For Administrators
- **Secure Dashboard** - Password-protected admin area
- **Feedback Management** - View, analyze, and delete feedback entries
- **Export Options** - Export feedback to CSV or PDF formats
- **Sentiment Analysis** - Automatic sentiment classification (Positive, Neutral, Negative)
- **Statistics** - At-a-glance feedback metrics and trends

## Technologies Used

- **Backend**: Python, Flask
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML, CSS, Bootstrap 5, JavaScript
- **Authentication**: Session-based with werkzeug security
- **Analysis**: TextBlob for sentiment analysis
- **Data Export**: CSV, PDF generation

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/visitor-feedback-system.git
   cd visitor-feedback-system
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows
   venv\Scripts\activate
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Open your browser and navigate to: `http://127.0.0.1:5000`

## Requirements

```
flask==2.0.1
flask-sqlalchemy==2.5.1
textblob==0.15.3
pandas==1.3.3
werkzeug==2.0.1
```

## Usage

### Visitor Interface

1. **Submit Feedback**:
   - Fill out the form on the homepage
   - Provide your name, optional email, select a category, and write your message
   - Click "Submit Feedback"

2. **Browse Archive**:
   - Navigate to the Archive page
   - Use filters to sort by category, date range, or search terms
   - View sentiment analysis results alongside feedback entries

### Administrator Interface

1. **Login**:
   - Navigate to `/admin/login`
   - Default credentials: Username: `admin`, Password: `admin123`

2. **Dashboard Features**:
   - Overview statistics of feedback (total count, sentiment breakdowns)
   - Full database of all feedback entries
   - Options to view detailed messages and delete entries
   - Export data in CSV or PDF formats

## Configuration

The default configuration uses SQLite for simplicity. For production, it's recommended to:

1. Change the secret key in app.py
2. Update the admin credentials
3. Consider using a more robust database like PostgreSQL

## Screenshots

### Home Page
![Home Page](https://via.placeholder.com/800x400?text=Home+Page)

### Feedback Archive
![Feedback Archive](https://via.placeholder.com/800x400?text=Feedback+Archive)

### Admin Dashboard
![Admin Dashboard](https://via.placeholder.com/800x400?text=Admin+Dashboard)

## Security Notice

⚠️ **Important**: The default admin credentials (username: `admin`, password: `admin123`) are for demonstration purposes only. Please change them before deploying in a production environment.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Bootstrap for the responsive design framework
- TextBlob for natural language processing capabilities
- Flask community for the excellent web framework

---

Made with ❤️ for better visitor feedback management

Similar code found with 2 license types
