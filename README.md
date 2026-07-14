# My Safety App 🛡️

A comprehensive safety and crime reporting web application designed to help users stay safe, report incidents, and access emergency services. Built with FastAPI backend and modern web technologies, featuring a responsive dark/light theme interface.

## 🌟 Features

### 🗺️ Interactive Safety Map
- Real-time crime data visualization
- Heat map showing crime density
- Safe area identification
- Location-based safety recommendations
- Interactive markers with detailed crime information

### 📊 Crime Reporting System
- **Report Crime**: Submit detailed crime reports with photos and evidence
- **Missing Person Reports**: Report and search for missing individuals
- **Wanted Criminals**: View and report wanted criminals database
- **Evidence Upload**: Support for multiple media files (images, videos)

### 🚨 Emergency Features
- **Panic Button**: Quick emergency alert system
- **Emergency Contacts**: Direct access to police and emergency services
- **Real-time Notifications**: Instant alerts for nearby incidents

### 👤 User Management
- **Secure Authentication**: Login and registration system
- **User Profiles**: Personalized user experience
- **Session Management**: Secure user sessions

### 💬 Communication
- **User Chatbox**: Community communication system
- **Report Status Tracking**: Track investigation progress
- **Anonymous Reporting**: Option for anonymous crime reporting

## 👥 Collaborators

We appreciate the contributions from our amazing team members:

| Contributor | Role | GitHub Profile |
|-------------|------|----------------|
| [Musfique Ahmed](https://github.com/Musfique-Ahmed) | Lead Developer | [@Musfique-Ahmed](https://github.com/Musfique-Ahmed) |
| [Tasfiya Binte Karim](https://github.com/TasfiyaBintaKarim) | Frontend Developer | [@TasfiyaBintaKarim](https://github.com/TasfiyaBintaKarim) |
| [Farhan Tarek Jamee](https://github.com/collaborator2) | Backend Developer | [@Farhan-Jamee](https://github.com/Farhan-Jamee) |
| [Sayma Talukdar](https://github.com/saymaaTalukder) | UI/UX Designer, Frontend Developer | [@saymaaTalukder](https://github.com/saymaaTalukder) |

<!-- Add more collaborators as needed -->

## 🛠️ Technologies Used

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **Python 3.8+**: Core backend language
- **Uvicorn**: ASGI server for FastAPI
- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: Database ORM (if applicable)

### Frontend
- **HTML5**: Semantic markup
- **CSS3**: Custom styling with CSS variables
- **JavaScript (ES6+)**: Interactive functionality
- **Tailwind CSS**: Utility-first CSS framework
- **Lucide Icons**: Modern icon library
- **Leaflet.js**: Interactive maps
- **Chart.js**: Data visualization

### Design Features
- **Responsive Design**: Mobile-first approach
- **Dark/Light Theme**: Automatic and manual theme switching
- **Modern UI/UX**: Clean and intuitive interface
- **Accessibility**: WCAG compliant design

## 📁 Project Structure

```
My-Safety-App/
├── main.py                     # FastAPI backend server
├── static/
│   ├── index.html              # Main dashboard
│   ├── login.html              # User authentication
│   ├── signup.html             # User registration
│   ├── missing_person.html     # Missing persons page
│   ├── report_crime.html       # Crime reporting form
│   ├── report_missing_person.html # Missing person form
│   ├── user_chatbox.html       # Community chat
│   ├── wanted_criminals.html   # Wanted criminals database
│   └── assets/
│       ├── css/
│       ├── js/
│       └── images/
├── requirements.txt            # Python dependencies
└── README.md
```

## 🚀 Getting Started

### Prerequisites
- **Python 3.8+**
- **pip** (Python package manager)
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/My-Safety-App.git
   cd My-Safety-App
   ```

2. **Install Python dependencies**
   ```bash
   pip install fastapi uvicorn
   # Or if you have requirements.txt:
   pip install -r requirements.txt
   ```

3. **Start the FastAPI backend server**
   ```bash
   # Run the FastAPI server
   python main.py
   
   # Or using uvicorn directly
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the application**
   ```
   Open http://localhost:8000 in your browser
   ```

### Quick Start
1. Copy `.env.example` to `.env` and set a real `JWT_SECRET` (≥32 random bytes).
2. Run `python scripts/run_migration_and_db_test.py` to apply migrations 001–004 and verify the schema.
3. Run `python main.py` to start the backend server
4. Open http://localhost:8000 in your browser
5. Create an account or login
6. Explore the interactive map
7. Report incidents or search for missing persons
8. Use the panic button for emergencies

## 🔐 Authentication

All write endpoints (POST/PUT/DELETE on `/api/admin/*`, `/api/chat/*`, panic button, etc.) require a JWT bearer token. Public read endpoints (e.g. `GET /api/crimes`, `GET /api/wanted-criminals`, `GET /api/missing-persons`) are still open.

Tokens are HS256-signed with `JWT_SECRET` and expire after `JWT_EXPIRES_MINUTES` (default 120). The login response includes the token; the frontend stores it in `localStorage.auth_token` and the shared `static/assets/js/api-base.js` wrapper attaches it to every fetch automatically.

### Token usage
```
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"hunter2"}'

curl http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer <token>"
```

## 📄 Admin sub-app (`/admin-api`)

`main_admin.py` is mounted under `/admin-api`. Legacy CRUD paths that live only in that file (e.g. `/api/admin/admin-activity-log`, `/api/admin/api-logs`) are reachable as `/admin-api/api/admin/...`. The default admin dashboard calls only endpoints that exist in `main.py`, so no client changes are required.

## 🔧 Backend API

The FastAPI backend (`main.py`) provides:

### API Endpoints
- **Authentication**: Login/logout/register endpoints
- **Crime Reports**: CRUD operations for crime data
- **Missing Persons**: Missing person report management
- **User Management**: User profile and session handling
- **File Upload**: Media file upload for evidence
- **Real-time Data**: WebSocket connections for live updates

### API Documentation
Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Example API Usage
```python
# Example FastAPI endpoint structure in main.py
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="My Safety App API")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return {"message": "My Safety App API"}

@app.post("/api/report-crime")
async def report_crime(crime_data: dict):
    # Process crime report
    return {"status": "success"}
```

### Pagination

List endpoints (`GET /api/crimes`, `/api/admin/users`, `/api/admin/complaints`, `/api/admin/case-assignments`, `/api/admin/case-management`, `/api/admin/emergencies`, `/api/admin/activity-log`) accept `?limit=N&offset=M`. Default `limit=50`, max `200`. Responses include `total`, `limit`, and `offset`:

```json
{ "crimes": [...], "total": 137, "limit": 50, "offset": 0 }
```

## 🎨 Themes

The application supports both light and dark themes:

- **Light Theme**: Clean white background with gray accents
- **Dark Theme**: Deep dark backgrounds with purple accents
- **Auto Theme**: Follows system preference
- **Manual Toggle**: Switch themes with the toggle button

### Theme Colors
```css
/* Light Theme */
--bg-light: #f3f4f6
--surface-light: #ffffff
--text-light: #1f2937

/* Dark Theme */
--bg-dark: #111827
--surface-dark: #1f2937
--text-dark: #f9fafb

/* Accent Colors */
--accent-purple: #8b5cf6
--accent-blue: #3b82f6
--accent-green: #10b981
```

## 📱 Responsive Design

The application is fully responsive and optimized for:
- **Desktop**: Full-featured interface with sidebar navigation
- **Tablet**: Adapted layout with collapsible menus
- **Mobile**: Touch-optimized interface with mobile navigation

## 🔐 Security Features

- **FastAPI Security**: Built-in security features
- **Input Validation**: Server-side and client-side validation
- **Secure Authentication**: JWT token-based authentication
- **Session Management**: Secure user session handling
- **Data Privacy**: Anonymous reporting options
- **CORS Protection**: Cross-origin request security

## 🗺️ Map Features

- **Interactive Map**: Powered by Leaflet.js
- **Crime Markers**: Visual crime incident markers
- **Heat Maps**: Crime density visualization
- **Location Services**: GPS-based location detection
- **Custom Markers**: Different icons for different crime types

## 📊 Data Visualization

- **Crime Statistics**: Interactive charts and graphs
- **Trend Analysis**: Crime pattern visualization
- **Area Comparison**: Safety statistics by location
- **Real-time Updates**: Live data updates via WebSocket

## 🚀 Deployment

### Local Development
```bash
# Start development server
python main.py
```

### Production Deployment
```bash
# Using Gunicorn
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker

# Using Docker (create Dockerfile)
docker build -t my-safety-app .
docker run -p 8000:8000 my-safety-app
```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Code Style
- Follow PEP 8 for Python code
- Use semantic HTML
- Follow CSS naming conventions
- Write clean, commented JavaScript
- Ensure responsive design
- Test across browsers

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

If you need help or have questions:
- Create an issue on GitHub
- Contact: anikmushfik@gmail.com
- API Documentation: http://localhost:8000/docs

## 🙏 Acknowledgments

- **FastAPI** for the powerful backend framework
- **Leaflet.js** for interactive maps
- **Tailwind CSS** for utility-first styling
- **Lucide Icons** for beautiful icons
- **Chart.js** for data visualization
- Community contributors and testers

## 📈 Roadmap

### Upcoming Features
- [ ] Real-time notifications via WebSocket
- [ ] Mobile app version
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Integration with emergency services APIs
- [ ] Offline functionality
- [x] JWT auth + bcrypt password hashing
- [x] Pagination on list endpoints
- [x] DB schema documented as migrations (002/003/004)
- [ ] User authentication with OAuth

### Version History
- **v1.0.0**: Initial release with FastAPI backend and core features
- **v1.1.0**: Added dark theme support
- **v1.2.0**: Enhanced mobile responsiveness and API improvements

---

**Stay Safe! 🛡️**

Built with ❤️ using FastAPI and modern web technologies.

For more information about the API, start the server and visit http://localhost:8000/docs
