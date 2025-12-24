# BookClub - Quick Start Guide

## 🚀 Quick Start

### Using Docker (Recommended)

1. **Clone or download this project**

2. **Start the application**
   ```bash
   cd bookclub
   docker-compose up -d
   ```

3. **Access the application**
   - Open your browser to: http://localhost:8000
   - Create your first book club!

4. **Stop the application**
   ```bash
   docker-compose down
   ```

### Manual Setup (Without Docker)

1. **Install Python 3.11+**

2. **Install dependencies**
   ```bash
   cd bookclub
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the application**
   - Open your browser to: http://localhost:8000

## 📖 How to Use

### Creating a Book Club

1. Click "Create Club" from the homepage
2. Enter a name and optional description
3. You'll receive a unique 8-character club code
4. Share this code with your friends!

### Joining a Book Club

1. Click "Join Club" from the homepage
2. Enter the club code you received
3. Choose a display name
4. You're in! No account required.

### Adding Book Suggestions

1. Navigate to your club page
2. Fill out the "Suggest a Book" form
3. Add title, author, and why you think the club should read it

### Selecting the Next Book

1. Once you have multiple suggestions, click "Pick Random Book"
2. The app will randomly select from all non-vetoed suggestions
3. The selected book becomes your "Currently Reading" book

### Discussions

1. Click on any book to view discussions
2. Create discussion threads for different topics
3. Mark posts as spoilers to keep things safe for everyone
4. Participate in conversations with your club

## 🔧 Configuration

### Change the Port

Edit `docker-compose.yml`:
```yaml
ports:
  - "3000:8000"  # Change 3000 to your desired port
```

### Use PostgreSQL Instead of SQLite

1. Update `docker-compose.yml`:
   ```yaml
   environment:
     - DATABASE_URL=postgresql://user:password@postgres:5432/bookclub
   ```

2. Add a PostgreSQL service to `docker-compose.yml`

### Security

⚠️ **Important**: Change the SECRET_KEY in production!

Generate a secure key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Update in `docker-compose.yml` or create a `.env` file.

## 📱 Features Checklist

- [x] Create and join clubs with codes
- [x] Add book suggestions
- [x] Random book selection
- [x] Discussion threads
- [x] Spoiler protection
- [x] Session-based authentication
- [ ] Book cover images (coming soon)
- [ ] Reading progress tracking (coming soon)
- [ ] Voting system (coming soon)
- [ ] Email notifications (coming soon)

## 🐛 Troubleshooting

**Can't access on other devices?**
- Make sure port 8000 is open on your firewall
- Use your server's IP address instead of localhost

**Database errors?**
- The data directory must be writable
- Check file permissions: `chmod -R 755 data/`

**Cookie/session issues?**
- Clear your browser cookies
- Make sure cookies are enabled

## 🤝 Contributing

This is an open project! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Share your improvements

## 📝 License

TBD

---

**Happy Reading! 📚**
