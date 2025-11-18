# Playwright Service

Express service for browser automation using Playwright. Provides REST API for UI testing with video recording and screenshots.

## 📁 Structure

```
playwright-service/
├── src/
│   ├── app.js              # Express server
│   ├── routes/             # API endpoints
│   │   ├── healthRoutes.js
│   │   ├── testRoutes.js
│   │   └── index.js
│   ├── services/           # BaseService pattern (from PRO 2.0)
│   │   ├── base-service.js
│   │   └── README.md
│   ├── pages/              # Page object pattern
│   │   └── basePage.js
│   └── utils/
│       ├── browser-utils.js   # Browser initialization
│       ├── file-utils.js      # File operations
│       ├── media-utils.js     # Screenshots & videos
│       └── logger.js          # Timestamped logging
│
├── config/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── scripts/
│   ├── cleanup.sh          # Clean artifacts
│   ├── collect_logs.sh     # Collect logs
│   └── localrun.sh         # Start service
│
├── output/                 # Auto-generated artifacts
│   ├── screenshots/
│   ├── videos/
│   ├── logs/
│   └── attachments/
│
└── package.json
```

## Key Features

- ✅ **BaseService Pattern** - Automatic browser lifecycle & video recording
- ✅ **Timestamped Logs** - All logs include timestamps
- ✅ **Video Recording** - Automatic with descriptive filenames: `YYYY-MM-DD_HH-MM-SS_operation.webm`
- ✅ **Screenshots** - Captured at key points
- ✅ **Error Handling** - Error videos automatically saved for debugging
- ✅ **Stealth Mode** - Reduced bot detection

## 🚀 Quick Start

### 1. Start Service
```bash
cd config
docker-compose up -d
```

### 2. Health Check
```bash
curl http://localhost:3001/api/health
```

### 3. Stop Service
```bash
cd config
docker-compose down
```

### 4. Clean Artifacts
```bash
bash scripts/cleanup.sh
```

## 📊 Available Endpoints

### Health Check
```
GET /api/health
```

Returns service status and timestamp.

### Test Navigation
```
POST /api/test/navigate
Body: {
  "url": "https://example.com",
  "waitTime": 5000
}
```

Navigates to URL, captures screenshot and video.

## 🔨 Creating New Services

See `src/services/README.md` for the BaseService pattern documentation and examples.

Quick example:
```javascript
const automationFunction = async (browser, context, page, data) => {
  const basePage = new BasePage(context, page);
  await basePage.goto(data.url);
  // Your automation logic
  return { message: 'Success', data: {...} };
};

const result = await BaseService.execute(
  automationFunction,
  yourData,
  'operation_name'
);
```

## 📹 Artifacts

All artifacts are automatically saved in `output/`:

- **Videos**: `YYYY-MM-DD_HH-MM-SS_operation.webm`
- **Screenshots**: `operation_description_YYYY-MM-DD_HH-MM-SS.png`
- **Logs**: Collected via `scripts/collect_logs.sh`

## 🐛 Debugging

View real-time logs:
```bash
docker logs stripe-playwright-service -f
```

Collect logs to file:
```bash
bash scripts/collect_logs.sh
```

## ⚙️ Configuration

- **Port**: 3001 (external) → 3000 (internal)
- **Debug Mode**: Set `DEBUG_MODE=true` in docker-compose.yml
- **Output Directory**: Mounted as volume for persistence

---

**Pattern Origin**: BaseService from PRO 2.0 project

